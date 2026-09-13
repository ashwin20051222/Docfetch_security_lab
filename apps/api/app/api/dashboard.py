from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent, Document, Download, Finding, LabTarget, SecurityTest
from app.schemas import DashboardSummary

from .router import api

router = APIRouter(tags=["dashboard"])

_ACTIVITY_LABELS = {
    "document_analysis_completed": "Document analyzed and stored",
    "document_analysis_started": "Document analysis started",
    "document_uploaded": "File uploaded and validated",
    "document_download": "Document downloaded",
    "document_deleted": "Document deleted",
    "security_test_started": "Security test started",
    "security_test_completed": "Security test completed",
    "security_test_error": "Security test error",
    "finding_created": "Finding created",
    "report_generated": "Report generated",
    "target_created": "Lab target registered",
    "target_deleted": "Lab target removed",
    "target_enabled": "Lab target enabled",
}


@api.get("/dashboard/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)) -> DashboardSummary:
    documents_total = db.scalar(select(func.count(Document.id))) or 0
    uploads_total = db.scalar(
        select(func.count(Document.id)).where(Document.source == "upload")
    ) or 0
    downloads_total = db.scalar(select(func.count(Download.id))) or 0
    tests_total = db.scalar(select(func.count(SecurityTest.id))) or 0
    open_findings = db.scalar(
        select(func.count(Finding.id)).where(Finding.status == "open")
    ) or 0
    all_findings = db.scalar(select(func.count(Finding.id))) or 0
    targets_total = db.scalar(select(func.count(LabTarget.id))) or 0
    targets_reachable = db.scalar(
        select(func.count(LabTarget.id)).where(LabTarget.reachable.is_(True))
    ) or 0

    recent = db.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(8)
    ).all()

    return DashboardSummary(
        documents_total=documents_total,
        uploads_total=uploads_total,
        downloads_total=downloads_total,
        tests_total=tests_total,
        open_findings=open_findings,
        all_findings=all_findings,
        targets_total=targets_total,
        targets_reachable=targets_reachable,
        recent_activity=[
            {
                "kind": e.event_type,
                "summary": _ACTIVITY_LABELS.get(e.event_type, e.event_type),
                "created_at": e.created_at,
                "detail": e.detail or {},
            }
            for e in recent
        ],
    )