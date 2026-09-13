from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit import record_audit
from app.core.errors import (
    ConflictError,
    DocumentNotFoundError,
    TargetNotAuthorizedError,
)
from app.database import get_db
from app.models import Finding, LabTarget, SecurityReport, SecurityTest
from app.schemas import (
    FindingOut,
    FindingPatch,
    LabTargetCreate,
    LabTargetOut,
    ReportGenerate,
    SecurityReportOut,
    SecurityTestCreate,
    SecurityTestOut,
    TargetCheckOut,
)
from app.services.reporting import generate_report
from app.services.security_engine import (
    PROFILE_LIST,
    is_local_endpoint,
    reachability_check,
    run_security_test,
    should_authorize_external_target,
)

from .router import api

log = logging.getLogger("docfetch.api.lab")
router = APIRouter(tags=["security-lab"])
settings = get_settings()


def _admin(request: Request) -> None:
    if settings.lab_admin_token:
        token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        if token != settings.lab_admin_token:
            raise TargetNotAuthorizedError(
                "A valid lab admin token is required for this Security Lab action.",
                code="AUTH_REQUIRED",
            )


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@api.post("/lab/targets", response_model=LabTargetOut)
def create_target(
    body: LabTargetCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> LabTargetOut:
    _admin(request)
    from app.api.router import enforce_rate_limit

    enforce_rate_limit(request, "lab")

    existing = db.scalar(select(LabTarget).where(LabTarget.name == body.name))
    if existing is not None:
        raise ConflictError(
            "A lab target with this name already exists. Use a distinct name "
            "(or delete the existing target first).",
            code="TARGET_NAME_TAKEN",
        )

    parsed = urlparse(body.base_url)
    if parsed.scheme not in ("http", "https"):
        raise TargetNotAuthorizedError(
            "Lab targets must use http:// or https://.", code="INVALID_TARGET_URL"
        )

    local = is_local_endpoint(body.base_url)
    allowlisted = should_authorize_external_target(body.base_url, settings.authorized_targets)
    if not local and not allowlisted:
        raise TargetNotAuthorizedError(
            "Target is not in the authorized security-test allowlist. "
            "External hosts must be added to AUTHORIZED_LAB_TARGETS by the deployment owner.",
            code="TARGET_NOT_ALLOWLISTED",
        )

    profiles = body.allowed_test_profiles or ["auth-enforcement", "header-hardening"]
    target = LabTarget(
        name=body.name,
        base_url=body.base_url.rstrip("/"),
        environment_type=body.environment_type,
        auth_status=body.auth_status,
        allowed_test_profiles=profiles,
        authorized=True,
        enabled=True,
        description=body.description,
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    record_audit(
        db,
        "target_created",
        entity_type="lab_target",
        entity_id=target.id,
        detail={
            "name": target.name,
            "base_url": target.base_url,
            "environment": target.environment_type,
            "local": local,
            "allowlisted": allowlisted,
        },
        request_id=getattr(request.state, "request_id", None),
    )
    return LabTargetOut.model_validate(target)


@api.get("/lab/targets", response_model=list[LabTargetOut])
def list_targets(db: Session = Depends(get_db)) -> list[LabTargetOut]:
    rows = db.scalars(select(LabTarget).order_by(LabTarget.name)).all()
    return [LabTargetOut.model_validate(t) for t in rows]


@api.delete("/lab/targets/{target_id}", response_model=dict)
def delete_target(target_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    _admin(request)
    target = db.get(LabTarget, target_id)
    if target is None:
        raise DocumentNotFoundError("Lab target not found.", code="TARGET_NOT_FOUND")
    name = target.name
    db.delete(target)
    db.commit()
    record_audit(
        db,
        "target_deleted",
        entity_type="lab_target",
        entity_id=target_id,
        detail={"name": name},
        request_id=getattr(request.state, "request_id", None),
    )
    return {"deleted": True, "id": target_id}


@api.post("/lab/targets/{target_id}/check", response_model=TargetCheckOut)
def check_target(target_id: str, db: Session = Depends(get_db)) -> TargetCheckOut:
    target = db.get(LabTarget, target_id)
    if target is None:
        raise DocumentNotFoundError("Lab target not found.", code="TARGET_NOT_FOUND")
    ok = reachability_check(db, target)
    return TargetCheckOut(
        target_id=target.id, reachable=ok, checked_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@api.post("/lab/tests", response_model=SecurityTestOut)
def run_test(
    body: SecurityTestCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> SecurityTestOut:
    _admin(request)
    from app.api.router import enforce_rate_limit

    enforce_rate_limit(request, "lab")
    target = db.get(LabTarget, body.target_id)
    if target is None:
        raise DocumentNotFoundError("Lab target not found.", code="TARGET_NOT_FOUND")

    token = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip() or None
    test = run_security_test(
        db,
        target,
        body.profile,
        admin_token=token,
        configured_admin_token=settings.lab_admin_token,
    )
    return SecurityTestOut.model_validate(test)


@api.get("/lab/tests", response_model=list[SecurityTestOut])
def list_tests(db: Session = Depends(get_db)) -> list[SecurityTestOut]:
    rows = db.scalars(
        select(SecurityTest)
        .order_by(SecurityTest.started_at.desc())
        .limit(100)
    ).all()
    return [SecurityTestOut.model_validate(t) for t in rows]


@api.get("/lab/tests/{test_id}", response_model=SecurityTestOut)
def get_test(test_id: str, db: Session = Depends(get_db)) -> SecurityTestOut:
    test = db.get(SecurityTest, test_id)
    if test is None:
        raise DocumentNotFoundError("Test not found.", code="TEST_NOT_FOUND")
    return SecurityTestOut.model_validate(test)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@api.get("/lab/findings", response_model=list[FindingOut])
def list_findings(db: Session = Depends(get_db)) -> list[FindingOut]:
    rows = db.scalars(
        select(Finding).order_by(Finding.created_at.desc()).limit(200)
    ).all()
    return [FindingOut.model_validate(f) for f in rows]


@api.get("/lab/findings/{finding_id}", response_model=FindingOut)
def get_finding(finding_id: str, db: Session = Depends(get_db)) -> FindingOut:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise DocumentNotFoundError("Finding not found.", code="FINDING_NOT_FOUND")
    return FindingOut.model_validate(finding)


@api.patch("/lab/findings/{finding_id}", response_model=FindingOut)
def update_finding(
    finding_id: str,
    body: FindingPatch,
    request: Request,
    db: Session = Depends(get_db),
) -> FindingOut:
    _admin(request)
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise DocumentNotFoundError("Finding not found.", code="FINDING_NOT_FOUND")
    finding.status = body.status
    if body.recommendation is not None:
        finding.recommendation = body.recommendation
    db.commit()
    db.refresh(finding)
    record_audit(
        db,
        "finding_updated",
        entity_type="finding",
        entity_id=finding.id,
        detail={"status": body.status},
        request_id=getattr(request.state, "request_id", None),
    )
    return FindingOut.model_validate(finding)


@api.delete("/lab/findings/{finding_id}", response_model=dict)
def delete_finding(finding_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    _admin(request)
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise DocumentNotFoundError("Finding not found.", code="FINDING_NOT_FOUND")
    db.delete(finding)
    db.commit()
    record_audit(
        db,
        "finding_deleted",
        entity_type="finding",
        entity_id=finding_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return {"deleted": True, "id": finding_id}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@api.post("/lab/reports", response_model=SecurityReportOut)
def generate_report_endpoint(
    body: ReportGenerate,
    request: Request,
    db: Session = Depends(get_db),
) -> SecurityReportOut:
    _admin(request)
    from app.api.router import enforce_rate_limit

    enforce_rate_limit(request, "lab")
    if body.target_id is None:
        raise DocumentNotFoundError("A target_id is required to generate a report.", "TARGET_REQUIRED")
    target = db.get(LabTarget, body.target_id)
    if target is None:
        raise DocumentNotFoundError("Lab target not found.", code="TARGET_NOT_FOUND")

    fmt = body.formats[0] if body.formats else "json"
    record = generate_report(db, target, fmt=fmt)
    return SecurityReportOut.model_validate(record)


@api.get("/lab/reports", response_model=list[SecurityReportOut])
def list_reports(db: Session = Depends(get_db)) -> list[SecurityReportOut]:
    rows = db.scalars(
        select(SecurityReport).order_by(SecurityReport.created_at.desc()).limit(100)
    ).all()
    return [SecurityReportOut.model_validate(r) for r in rows]


@api.get("/lab/reports/{report_id}", response_model=SecurityReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)) -> SecurityReportOut:
    report = db.get(SecurityReport, report_id)
    if report is None:
        raise DocumentNotFoundError("Report not found.", code="REPORT_NOT_FOUND")
    return SecurityReportOut.model_validate(report)


@api.get("/lab/reports/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db)):
    report = db.get(SecurityReport, report_id)
    if report is None:
        raise DocumentNotFoundError("Report not found.", code="REPORT_NOT_FOUND")
    if not report.path:
        raise DocumentNotFoundError("Report file is unavailable.", code="REPORT_MISSING")
    import os

    path = report.path
    if not os.path.exists(path):
        raise DocumentNotFoundError("Report file is unavailable on disk.", code="REPORT_MISSING")
    media = "application/json" if report.format == "json" else "text/html"
    return FileResponse(path, media_type=media, filename=os.path.basename(path))


@api.get("/lab/profiles")
def list_profiles():
    return {"profiles": PROFILE_LIST}