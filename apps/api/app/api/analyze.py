from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.errors import ApiError, FetchFailedError
from app.database import get_db
from app.schemas import AnalyzeRequest, AnalyzeResult, DocumentOut
from app.services.document_engine import analyze_url

from .router import api

log = logging.getLogger("docfetch.api.analyze")
router = APIRouter(tags=["analyze"])


@api.post("/analyze", response_model=AnalyzeResult)
def analyze(body: AnalyzeRequest, request: Request, db: Session = Depends(get_db)) -> AnalyzeResult:
    from app.api.router import enforce_rate_limit

    enforce_rate_limit(request, "analyze")
    request_id = getattr(request.state, "request_id", None)

    record_audit(
        db,
        "document_analysis_started",
        entity_type="url",
        detail={"url": body.url[:256]},
        request_id=request_id,
    )

    try:
        doc = analyze_url(db, body.url, title_hint=body.title_hint)
        if doc is None:
            raise FetchFailedError(
                "The URL resolved but did not reference a retrievable PDF document.",
                code="DOCUMENT_NOT_FOUND",
            )
    except ApiError:
        db.rollback()
        raise

    record_audit(
        db,
        "document_analysis_completed",
        entity_type="document",
        entity_id=doc.id,
        detail={"status": doc.status},
        request_id=request_id,
    )
    return AnalyzeResult(
        document=DocumentOut.model_validate(doc),
        verdict="document_found",
    )