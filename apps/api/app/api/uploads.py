from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit import record_audit
from app.core.errors import ApiError, FileTooLargeError
from app.database import get_db
from app.schemas import DocumentOut, UploadResult
from app.services.document_engine import store_upload, validate_upload_bytes

from .router import api

log = logging.getLogger("docfetch.api.uploads")
router = APIRouter(tags=["uploads"])
settings = get_settings()


@api.post("/uploads", response_model=UploadResult)
def upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> UploadResult:
    from app.api.router import enforce_rate_limit

    enforce_rate_limit(request, "upload")
    request_id = getattr(request.state, "request_id", None)

    suggested_name = file.filename or "document.pdf"

    data = bytearray()
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > settings.max_upload_size:
            raise FileTooLargeError(
                f"Uploaded file exceeds the {settings.max_upload_size} byte limit.",
                code="FILE_TOO_LARGE",
            )

    # Extension and browser MIME are never trusted; magic bytes rule.
    try:
        doc = store_upload(db, bytes(data), suggested_name)
    except ApiError:
        db.rollback()
        raise

    record_audit(
        db,
        "document_uploaded",
        entity_type="document",
        entity_id=doc.id,
        detail={"size_bytes": len(data), "source_filename": suggested_name[:120]},
        request_id=request_id,
    )
    return UploadResult(
        document=DocumentOut.model_validate(doc),
        verdict="document_stored",
    )