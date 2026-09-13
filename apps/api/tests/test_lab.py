"""Security Lab tests: target allowlisting, real test execution, findings,
report generation."""
from __future__ import annotations

import http.server
import threading
import time

import pytest

from app.core.errors import TargetNotAuthorizedError
from app.services.security_engine import (
    classify_finding,
    is_local_endpoint,
    run_security_test,
    should_authorize_external_target,
)


def test_external_target_requires_allowlist():
    assert not should_authorize_external_target(
        "https://random-third-party-site.example", []
    )
    assert should_authorize_external_target(
        "https://allowed.example",
        ["https://allowed.example", "http://127.0.0.1:9101"],
    )
    assert is_local_endpoint("http://127.0.0.1:9101")
    assert is_local_endpoint("http://localhost:9101")


_target_counter = 0

def _make_target(db, base_url, name=None, profiles=None):
    global _target_counter
    _target_counter += 1
    if name is None:
        name = f"test-target-{_target_counter}"
    from app.models import LabTarget  # noqa: PLC0415

    t = LabTarget(
        name=name,
        base_url=base_url,
        environment_type="local",
        auth_status="none",
        allowed_test_profiles=profiles or ["auth-enforcement", "client-side-access-control",
                                           "direct-file-access", "header-hardening"],
        authorized=not should_authorize_external_target(base_url, []) or is_local_endpoint(base_url),
        enabled=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _serve(handler_cls):
    import http.server  # noqa: PLC0415
    import socketserver  # noqa: PLC0415

    class S(http.server.HTTPServer):
        daemon_threads = True

    srv = S(("127.0.0.1", 0), handler_cls)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return f"http://127.0.0.1:{srv.server_address[1]}", srv


class _SecureHandler(http.server.BaseHTTPRequestHandler):
    """Enforces authorization: 403 without the lab token."""
    def do_GET(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer lab-authorized"):
            self.send_response(403)
            self.end_headers()
            return
        if self.path == "/document.pdf":
            body = b"%PDF-1.4\n%%EOF\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


class _WeakHandler(http.server.BaseHTTPRequestHandler):
    """Client-side paywall: serves protected content regardless of auth."""
    def do_GET(self):
        if self.path == "/labs/page":
            body = b"<html><div class='oc-paywall'>DOCFETCH-PROTECTED-CONTENT-MARKER</div></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def test_secure_paywall_passes_auth_enforcement(db_session):
    base, srv = _serve(_SecureHandler)
    target = _make_target(db_session, base)
    test = run_security_test(db_session, target, "auth-enforcement")
    srv.shutdown()
    assert test.status == "passed"
    assert test.finding is None
    assert test.response_summary["unauthorized_status"] == 403


def test_weak_paywall_creates_finding(db_session):
    base, srv = _serve(_WeakHandler)
    target = _make_target(db_session, base)
    test = run_security_test(db_session, target, "client-side-access-control")
    srv.shutdown()
    assert test.status == "failed"
    assert test.finding is not None
    assert test.finding.severity in ("high", "medium", "critical")
    assert test.finding.status == "open"
    assert "protected" in test.finding.title.lower() or "client-side" in test.finding.title.lower()


def test_finding_evidence_is_real(db_session):
    base, srv = _serve(_WeakHandler)
    target = _make_target(db_session, base)
    test = run_security_test(db_session, target, "client-side-access-control")
    srv.shutdown()
    evidence = test.finding.evidence or {}
    blocks = evidence.get("blocks", [])
    assert len(blocks) == 2
    assert blocks[0]["label"] == "AUTHORIZED LAB IDENTITY"
    assert blocks[1]["label"] == "UNAUTHORIZED"
    # Redaction check: authorization header shown redacted.
    assert blocks[0]["request"]["headers"]["Authorization"] == "[REDACTED]"


def test_report_refuses_before_any_test(db_session):
    from app.services.reporting import generate_report  # noqa: PLC0415

    target = _make_target(db_session, "http://127.0.0.1:9999")
    with pytest.raises(ValueError, match="No report available"):
        generate_report(db_session, target, "json")


def test_report_generated_after_real_test(db_session):
    from app.services.reporting import generate_report  # noqa: PLC0415

    base, srv = _serve(_SecureHandler)
    target = _make_target(db_session, base)
    run_security_test(db_session, target, "auth-enforcement")
    report = generate_report(db_session, target, "json")
    srv.shutdown()
    assert report.finding_count == 0
    assert report.format == "json"
    assert report.summary["executed_tests"] >= 1


def test_report_generated_with_findings(db_session):
    """A report built over recorded findings must embed remediation and real data."""
    from app.services.reporting import build_report_data, generate_report  # noqa: PLC0415

    import json

    base, srv = _serve(_WeakHandler)
    target = _make_target(db_session, base)
    run_security_test(db_session, target, "client-side-access-control")

    data = build_report_data(db_session, target)
    assert data["remediation"] == [f["recommendation"] for f in data["findings"]]
    report = generate_report(db_session, target, "json")
    srv.shutdown()
    assert report.finding_count >= 1
    assert report.summary["open_findings"] >= 1
    written = json.loads(report.path and __import__("pathlib").Path(report.path).read_text())
    assert written["remediation"] and all(r for r in written["remediation"])


def test_classify_auth_gap():
    finding = classify_finding("auth-enforcement", {
        "authorized": {"status": 200, "content_type": "application/pdf", "content_length": 10,
                       "security_headers": {}, "body_sha256": "a", "body_preview": ""},
        "unauthorized": {"status": 200, "content_type": "application/pdf", "content_length": 10,
                         "security_headers": {}, "body_sha256": "a", "body_preview": ""},
        "path": "/document.pdf", "content_exposed": True, "byte_identical": True,
    })
    assert finding is not None
    assert finding["severity"] == "critical"