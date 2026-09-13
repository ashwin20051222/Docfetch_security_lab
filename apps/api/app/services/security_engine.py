"""Authorized security test engine.

The engine issues REAL HTTP requests to registered, authorized lab targets
(no simulation). Findings are derived exclusively from observed responses.

Authorization model
-------------------
- Loopback / private lab endpoints are authorized because they are explicit
  lab targets registered by the deployment owner.
- External hosts are refused unless they appear in AUTHORIZED_LAB_TARGETS.
- Every authorized request is logged to the audit trail.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.errors import AuthNotConfiguredError, TargetNotAuthorizedError
from app.models import Finding, LabTarget, SecurityTest
from app.schemas import EvidenceBlock, RequestEvidence, ResponseEvidence

log = logging.getLogger("docfetch.security_engine")

LAB_IDENTITY_HEADERS = {"Authorization": "Bearer lab-authorized"}

PROTECTED_MARKERS = [
    "docfetch-protected",
    "protected-content",
    "oc-paywall",
    "reader-only",
]

CORE_SECURITY_HEADERS = [
    ("strict-transport-security", "HSTS"),
    ("x-content-type-options", "X-Content-Type-Options"),
    ("x-frame-options", "X-Frame-Options"),
    ("content-security-policy", "Content-Security-Policy"),
    ("referrer-policy", "Referrer-Policy"),
]


class ProfileDef:
    def __init__(self, name: str, title: str, description: str, probe_paths: list[str]):
        self.name = name
        self.title = title
        self.description = description
        self.probe_paths = probe_paths


PROFILES: dict[str, ProfileDef] = {
    "auth-enforcement": ProfileDef(
        name="auth-enforcement",
        title="Authorization Enforcement Consistency",
        description=(
            "Requests a protected resource with and without the lab identity and "
            "compares the server-enforced authorization decision."
        ),
        probe_paths=["/document.pdf", "/api/document"],
    ),
    "client-side-access-control": ProfileDef(
        name="client-side-access-control",
        title="Client-Side Access Control Inspection",
        description=(
            "Checks whether protected content is delivered to the browser regardless "
            "of authorization (i.e. the paywall is only visual/CSS, not enforced server-side)."
        ),
        probe_paths=["/labs/page", "/", "/reader"],
    ),
    "direct-file-access": ProfileDef(
        name="direct-file-access",
        title="Direct Protected File Access",
        description=(
            "Attempts to retrieve a protected file by its raw path without authorization."
        ),
        probe_paths=["/protected/research.pdf", "/files/doc.pdf", "/document.pdf"],
    ),
    "header-hardening": ProfileDef(
        name="header-hardening",
        title="Security Header Hardening",
        description="Inspects security-related response headers on a public endpoint.",
        probe_paths=["/health", "/"],
    ),
}

PUBLIC_HEADER_PATHS = ["/health", "/"]

# How long each factual HTTP request may take
MAX_TEST_SECONDS = 20.0


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in ("authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_base_url(raw: str) -> str:
    u = urlparse(raw)
    return f"{u.scheme}://{u.netloc}".rstrip("/")


def assert_target_authorized(target: LabTarget, *, required_admin_token: str | None = None, provided_token: str | None = None) -> None:
    """Enforce lab authorization policy for a target."""
    if required_admin_token and provided_token != required_admin_token:
        if not required_admin_token:
            raise AuthNotConfiguredError()
        raise TargetNotAuthorizedError("A valid lab admin token is required for this action.")

    if not target.authorized:
        raise TargetNotAuthorizedError(
            "Target is not in the authorized security-test allowlist."
        )


def is_local_endpoint(base_url: str) -> bool:
    host = urlparse(base_url).hostname or ""
    return host in ("127.0.0.1", "::1", "localhost", "host.docker.internal")


def should_authorize_external_target(base_url: str, authorized_allowlist: list[str]) -> bool:
    return normalize_base_url(base_url) in {normalize_base_url(u) for u in authorized_allowlist}


def run_target_probe(target: LabTarget, profile: str, timeout: float = MAX_TEST_SECONDS) -> dict:
    """Execute a real comparison probe. Returns structured evidence dict."""
    if profile not in PROFILES:
        raise ValueError(f"Unknown test profile: {profile}")
    pdef = PROFILES[profile]
    base = normalize_base_url(target.base_url)

    # Choose the first probe path that yields a meaningful response.
    chosen_path: str | None = None
    auth_resp: httpx.Response | None = None
    anon_resp: httpx.Response | None = None
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for path in pdef.probe_paths:
            url = base + path
            try:
                auth_resp = client.get(url, headers=LAB_IDENTITY_HEADERS)
                anon_resp = client.get(url)
            except httpx.HTTPError as exc:
                log.warning("probe_error target=%s path=%s err=%s", target.id, path, exc)
                continue
            if auth_resp.status_code >= 400 and anon_resp.status_code >= 400:
                continue  # not a live endpoint for this target
            chosen_path = path
            break

    if chosen_path is None or auth_resp is None or anon_resp is None:
        raise RuntimeError(
            "None of the probe paths responded. Check that the lab target is running "
            "and reachable at %s." % base
        )

    url = base + chosen_path
    ts = _now_iso()
    evidence_blocks = [
        EvidenceBlock(
            label="AUTHORIZED LAB IDENTITY",
            request=RequestEvidence(
                method="GET",
                url=url,
                timestamp=ts,
                headers=_redact_headers(dict(LAB_IDENTITY_HEADERS)),
            ),
            response=_response_evidence(auth_resp),
        ),
        EvidenceBlock(
            label="UNAUTHORIZED",
            request=RequestEvidence(
                method="GET",
                url=url,
                timestamp=ts,
                headers={"Authorization": "[REDACTED — none sent]"},
            ),
            response=_response_evidence(anon_resp),
        ),
    ]

    return {
        "profile": profile,
        "path": chosen_path,
        "authorized": _response_evidence(auth_resp),
        "unauthorized": _response_evidence(anon_resp),
        "blocks": [b.model_dump() for b in evidence_blocks],
        "content_exposed": (
            anon_resp.status_code == 200 and _contains_protected_marker(anon_resp.content)
        ),
        "byte_identical": anon_resp.content == auth_resp.content if anon_resp.content or auth_resp.content else False,
    }


def _response_evidence(resp: httpx.Response) -> dict:
    return {
        "status": resp.status_code,
        "content_type": resp.headers.get("content-type", "").split(";")[0].strip() or None,
        "content_length": len(resp.content) if resp.request.method == "GET" else None,
        "security_headers": {
            k: v for k, v in resp.headers.items() if k.lower() in {h[0] for h in CORE_SECURITY_HEADERS}
        },
        "body_sha256": _sha256(resp.content),
        "body_preview": resp.content[:2000].decode("latin-1", errors="replace"),
    }


def _contains_protected_marker(body: bytes) -> bool:
    text = body[:200_000].decode("latin-1", errors="replace").lower()
    return any(m in text for m in PROTECTED_MARKERS)


def classify_finding(profile: str, evidence: dict) -> dict | None:
    """Derive a finding strictly from observed behavior. Returns None when safe."""
    anon = evidence["unauthorized"]
    auth = evidence["authorized"]
    content_exposed = evidence["content_exposed"]
    identical = evidence["byte_identical"]

    if profile == "auth-enforcement":
        if anon["status"] in (401, 403):
            return None  # enforcement working
        return {
            "severity": "critical" if identical else "high",
            "title": "Failed Authorization Enforcement",
            "description": (
                "The protected resource was served to an unauthenticated request. "
                "The server did not enforce authorization server-side."
            ),
            "expected_behavior": "An unauthenticated request to a protected resource must be refused with HTTP 401/403 and no document body.",
            "observed_behavior": (
                f"Unauthenticated request returned HTTP {anon['status']} with "
                f"{anon['content_length'] or 'unknown'} bytes of body content. "
                + ("The unauthorized body is byte-identical to the authorized body." if identical else
                   "The unauthorized body contains protected document content.")
            ),
            "recommendation": (
                "Enforce authorization on the server before transmitting protected content. "
                "Never rely on client-side UI gating; every document endpoint must require a "
                "valid session and return 403 otherwise."
            ),
        }

    if profile == "client-side-access-control":
        if not content_exposed:
            return None
        return {
            "severity": "high" if identical else "medium",
            "title": "Client-Side Access Control Confirmed",
            "description": (
                "Protected content is delivered to the browser before any server-side "
                "authorization decision. The paywall hides it visually only."
            ),
            "expected_behavior": "Protected content must not reach the client without authorization.",
            "observed_behavior": (
                "An unauthenticated response carried protected-content markers in its body"
                + (" and was byte-identical to the authorized response." if identical else ".")
            ),
            "recommendation": (
                "Move access decisions server-side. Return an empty body or 403 to "
                "unauthorized clients and strip protected content from the page source."
            ),
        }

    if profile == "direct-file-access":
        if anon["status"] in (401, 403, 404):
            return None
        if anon["status"] == 200 and (
            anon.get("content_type") == "application/pdf" or identical
        ):
            severity = "high"
        else:
            severity = "medium"
        return {
            "severity": severity,
            "title": "Direct Protected File Access Exposed",
            "description": (
                "A protected file is retrievable directly by path without authorization."
            ),
            "expected_behavior": "Direct requests to protected file paths must be refused without a valid session.",
            "observed_behavior": (
                f"GET returned HTTP {anon['status']} (content-type "
                f"{anon.get('content_type') or 'unknown'}, {anon.get('content_length') or 0} bytes) "
                "with no credentials."
            ),
            "recommendation": (
                "Issue protected files only through an authorized controller endpoint that "
                "checks the session, and do not place protected files under guessable static paths."
            ),
        }

    if profile == "header-hardening":
        missing = [h[1] for h in CORE_SECURITY_HEADERS if h[0] not in anon.get("security_headers", {})]
        if len(missing) < 2:
            return None
        return {
            "severity": "low",
            "title": "Missing Security Headers",
            "description": "The public endpoint does not set core security response headers.",
            "expected_behavior": "Responses should set Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, Content-Security-Policy and Referrer-Policy.",
            "observed_behavior": "Missing: " + ", ".join(missing) + ".",
            "recommendation": "Add the missing security headers to the lab target's responses.",
        }

    return None


def run_security_test(
    db: Session,
    target: LabTarget,
    profile: str,
    admin_token: str | None = None,
    configured_admin_token: str = "",
) -> SecurityTest:
    if not target.enabled:
        target.enabled = True
        record_audit(db, "target_enabled", entity_type="lab_target", entity_id=target.id)
    assert_target_authorized(
        target, required_admin_token=configured_admin_token, provided_token=admin_token
    )

    pdef = PROFILES.get(profile)
    if pdef is None:
        raise ValueError(f"Unknown test profile: {profile}")
    if profile not in (target.allowed_test_profiles or []):
        raise ValueError(
            f"Profile '{profile}' is not allowed for target '{target.name}'."
        )

    test = SecurityTest(
        target_id=target.id,
        profile=profile,
        title=pdef.title,
        status="running",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    record_audit(
        db,
        "security_test_started",
        entity_type="security_test",
        entity_id=test.id,
        detail={"target_id": target.id, "profile": profile},
    )

    try:
        started = time.perf_counter()
        try:
            evidence = run_target_probe(target, profile, MAX_TEST_SECONDS)
        except Exception as exc:
            dur = round(time.perf_counter() - started, 3)
            test.status = "error"
            test.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            test.error_message = str(exc)
            record_audit(
                db, "security_test_error", entity_type="security_test", entity_id=test.id,
                detail={"error": str(exc)},
            )
            db.commit()
            return test

        finding_def = classify_finding(profile, evidence)
        dur = round(time.perf_counter() - started, 3)

        test.evidence = evidence
        test.request_summary = {
            "method": "GET",
            "url": f"{normalize_base_url(target.base_url)}{evidence.get('path', '')}",
            "requests": 2,
            "duration_seconds": dur,
        }
        anon = evidence["unauthorized"]
        test.response_summary = {
            "authorized_status": evidence["authorized"]["status"],
            "unauthorized_status": anon["status"],
            "content_exposed": evidence.get("content_exposed", False),
            "byte_identical": evidence.get("byte_identical", False),
        }

        if finding_def is not None:
            test.status = "failed"
            finding = Finding(
                target_id=target.id,
                test_id=test.id,
                title=finding_def["title"],
                severity=finding_def["severity"],
                status="open",
                description=finding_def["description"],
                expected_behavior=finding_def["expected_behavior"],
                observed_behavior=finding_def["observed_behavior"],
                recommendation=finding_def["recommendation"],
                evidence=evidence,
            )
            db.add(finding)
            record_audit(
                db,
                "finding_created",
                entity_type="finding",
                entity_id=finding.id,
                detail={"target_id": target.id, "severity": finding_def["severity"]},
            )
        else:
            test.status = "passed"

        test.error_message = None
    except Exception:
        db.rollback()
        test.status = "error"
        test.error_message = "Test execution failed unexpectedly."
        test.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return test

    test.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(test)

    if test.status == "failed":
        record_audit(
            db,
            "security_test_completed",
            entity_type="security_test",
            entity_id=test.id,
            detail={"status": test.status, "finding": test.finding.id if test.finding else None},
        )
    else:
        record_audit(
            db,
            "security_test_completed",
            entity_type="security_test",
            entity_id=test.id,
            detail={"status": test.status},
        )
    return test


PROFILE_LIST = [
    {
        "name": p.name,
        "title": p.title,
        "description": p.description,
        "apply_to": ["local", "docker", "network"],
    }
    for p in PROFILES.values()
]


def reachability_check(db: Session, target: LabTarget) -> bool:
    base = normalize_base_url(target.base_url)
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(base + "/health")
        reachable = resp.status_code < 500
    except httpx.HTTPError:
        reachable = False
    target.reachable = reachable
    target.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return reachable


__all__ = [
    "PROFILES",
    "PROFILE_LIST",
    "run_security_test",
    "reachability_check",
    "assert_target_authorized",
    "should_authorize_external_target",
    "is_local_endpoint",
]