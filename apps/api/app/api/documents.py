from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.audit import record_audit
from app.core.errors import DocumentNotFoundError, InvalidDocumentError
from app.database import get_db
from app.models import Document, Download
from app.schemas import (
    DeleteResult,
    DocumentOut,
    PreviewOut,
    PreviewPage,
)
from app.services.document_engine import (
    read_document_bytes,
    rasterize_page,
    storage_path_for,
    thumbnail_path,
)

from .router import api

log = logging.getLogger("docfetch.api.documents")
router = APIRouter(tags=["documents"])
settings = get_settings()


def _get_doc_or_404(db: Session, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise DocumentNotFoundError("Document not found.", code="DOCUMENT_NOT_FOUND")
    return doc


@api.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    return DocumentOut.model_validate(_get_doc_or_404(db, document_id))


@api.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    docs = db.scalars(select(Document).order_by(Document.created_at.desc()).limit(100)).all()
    return [DocumentOut.model_validate(d) for d in docs]


def _safe_content_disposition(value: str) -> str:
    clean = re.sub(r"[^\w\-. ]+", "", value).strip().replace(" ", "_") or "document.pdf"
    return clean


@api.get("/documents/{document_id}/download")
def download_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    from app.api.router import enforce_rate_limit

    enforce_rate_limit(request, "download")
    doc = _get_doc_or_404(db, document_id)
    path = storage_path_for(doc)
    if not path.exists():
        raise DocumentNotFoundError(
            "Document bytes are no longer available on disk.", code="STORAGE_MISSING"
        )

    filename = _safe_content_disposition(doc.filename or f"{doc.id}.pdf")
    request_id = getattr(request.state, "request_id", None)
    ua = request.headers.get("user-agent")

    download = Download(
        document_id=doc.id,
        bytes_transferred=doc.size_bytes,
        user_agent=(ua or "")[:300] or None,
        request_id=request_id,
    )
    db.add(download)
    db.commit()

    record_audit(
        db,
        "document_download",
        entity_type="document",
        entity_id=doc.id,
        detail={"size_bytes": doc.size_bytes},
        request_id=request_id,
    )

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="attachment",
    )


@api.get("/documents/{document_id}/preview", response_model=PreviewOut)
def preview_document(document_id: str, db: Session = Depends(get_db)) -> PreviewOut:
    doc = _get_doc_or_404(db, document_id)
    pages = doc.page_count or 0
    return PreviewOut(
        document_id=doc.id,
        page_count=pages,
        pages=[
            PreviewPage(
                page=i + 1,
                width=800,
                height=1100,
                thumb_url=f"/api/v1/documents/{doc.id}/pages/{i}",
                image_url=f"/api/v1/documents/{doc.id}/pages/{i}",
            )
            for i in range(pages)
        ],
    )


@api.get("/documents/{document_id}/pages/{page}")
def render_page(document_id: str, page: int, db: Session = Depends(get_db)) -> Response:
    doc = _get_doc_or_404(db, document_id)
    if page < 1 or (doc.page_count and page > doc.page_count):
        raise InvalidDocumentError("Requested page is outside this document.", "PAGE_OUT_OF_RANGE")
    png = rasterize_page(doc, page - 1)
    return Response(content=png, media_type="image/png")


@api.delete("/documents/{document_id}", response_model=DeleteResult)
def delete_document(document_id: str, db: Session = Depends(get_db)) -> DeleteResult:
    doc = _get_doc_or_404(db, document_id)
    doc_id = doc.id
    path = storage_path_for(doc)

    db.query(Download).filter(Download.document_id == doc_id).delete()
    db.delete(doc)
    db.commit()

    thumb = thumbnail_path(doc)
    for p in (path, thumb):
        try:
            if p.exists():
                p.unlink()
        except OSError:
            log.warning("file_cleanup_failed path=%s", p)

    record_audit(db, "document_deleted", entity_type="document", entity_id=doc_id)
    return DeleteResult(deleted=True, id=doc_id)


__all__ = ["read_document_bytes"]