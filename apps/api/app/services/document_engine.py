"""Document acquisition and validation.

Faithful to the "no fake data" rule: every Document row is created only
after a real fetch (or a real upload) passes validation. Nothing is
invented — encrypted/corrupt PDFs fail with a truthful error.
"""
from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import (
    FetchFailedError,
    InvalidDocumentError,
    InvalidURLError,
    SSRFDeniedError,
)
from app.models import Document, default_expiry
from app.security.ssrf import (
    FetchError,
    PUBLIC_POLICY,
    SSRFBlocked,
    fetch,
)
from app.services.pdf_validation import (
    inspect_pdf,
    is_pdf_magic,
    raster_page_png,
    write_thumbnail,
)

log = logging.getLogger("docfetch.document_engine")
settings = get_settings()

_PDF_MIME = "application/pdf"


def _safe_filename(meta: dict, source_url: str | None, title: str | None) -> str | None:
    if title:
        base = title.strip()
    elif source_url:
        base = (source_url.rstrip("/").rsplit("/", 1)[-1] or "document").split("?")[0]
        base = base.rsplit(".", 1)[0] if "." in base else base
    else:
        return None
    import re

    base = re.sub(r"[^\w\- ]+", "", base).strip() or "document"
    return f"{base[:90]}.pdf"


def analyze_url(db: Session, raw_url: str, title_hint: str | None = None) -> Document | None:
    """Fetch, validate and store a document from a public URL.

    Returns the stored Document, or ``None`` when the URL resolves but is
    not a downloadable document (callers communicate that faithfully).
    """
    url = raw_url.strip()
    if not url:
        raise InvalidURLError("URL is empty.")

    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidURLError("Only http:// and https:// URLs are supported.")

    try:
        resp = fetch(url, policy=PUBLIC_POLICY)
    except SSRFBlocked as exc:
        log.warning("ssrf_blocked url=%s reason=%s", url, exc.reason)
        raise SSRFDeniedError(exc.reason, code=exc.code) from exc
    except FetchError as exc:
        log.warning("fetch_error url=%s code=%s reason=%s", url, exc.code, exc.reason)
        raise FetchFailedError(exc.reason, code=exc.code) from exc

    if resp.status == 404:
        raise FetchFailedError("Source returned HTTP 404 (not found).", "DOCUMENT_NOT_FOUND")
    if resp.status == 401 or resp.status == 403:
        raise FetchFailedError(
            "The source requires authentication to read this document.",
            "ACCESS_RESTRICTED",
        )
    if resp.status >= 400:
        raise FetchFailedError(
            f"Source returned HTTP {resp.status}.",
            "SERVER_ERROR",
        )

    mime = resp.content_type
    if mime and not mime.startswith("application/pdf") and not mime.startswith(
        "application/octet-stream"
    ):
        if _looks_like_pdf_bytes(resp.body):
            pass  # content-type lied; magic bytes rule
        else:
            raise FetchFailedError(
                "The URL did not return a PDF document. Only PDF documents are supported.",
                code="UNSUPPORTED_FORMAT",
            )

    if not resp.body:
        raise FetchFailedError("The source returned an empty response.", "DOCUMENT_NOT_FOUND")

    return _store_bytes(
        db,
        data=resp.body,
        source_url=url,
        final_url=resp.final_url,
        title_hint=title_hint,
    )


def _looks_like_pdf_bytes(data: bytes) -> bool:
    return data[:1024].lstrip().startswith(b"%PDF-")


def validate_upload_bytes(data: bytes, suggested_name: str | None = None) -> None:
    """Validate untrusted upload bytes. Extension/browser MIME are ignored."""
    if len(data) == 0:
        raise InvalidDocumentError("Uploaded file is empty.")
    if len(data) > settings.max_upload_size:
        raise InvalidDocumentError(
            f"Uploaded file exceeds the {settings.max_upload_size} byte limit.",
            "FILE_TOO_LARGE",
        )
    if not is_pdf_magic(data):
        raise InvalidDocumentError(
            "The file does not start with a PDF signature. Only PDF documents are accepted.",
            "UNSUPPORTED_FORMAT",
        )
    try:
        inspect_pdf(data)
    except InvalidDocumentError:
        raise


def _store_bytes(
    db: Session,
    *,
    data: bytes,
    source_url: str | None,
    final_url: str | None = None,
    title_hint: str | None = None,
    suggested_name: str | None = None,
    source: str = "download",
) -> Document:
    sha256 = hashlib.sha256(data).hexdigest()
    info = inspect_pdf(data)

    if info["encrypted"]:
        raise InvalidDocumentError(
            "The PDF is encrypted or password-protected. Encrypted documents are refused.",
            "ENCRYPTED_DOCUMENT",
        )

    storage_path = settings.documents_dir / f"{sha256}.pdf"
    storage_path.write_bytes(data)

    title = info.get("title") or title_hint or None
    filename = _safe_filename(info, source_url, title or suggested_name)

    doc = Document(
        source_url=source_url,
        final_url=final_url or source_url,
        title=title,
        filename=filename,
        mime_type=_PDF_MIME,
        size_bytes=len(data),
        page_count=info["page_count"],
        sha256=sha256,
        status="ready",
        source=source,
        expires_at=default_expiry(settings.download_ttl_days),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        write_thumbnail(storage_path, settings.thumbs_dir / f"{doc.id}.png")
    except Exception as exc:  # thumbnails are advisory
        log.warning("thumbnail_failed doc=%s err=%s", doc.id, exc)

    log.info("document_stored id=%s sha256=%s pages=%s", doc.id, sha256, info["page_count"])
    return doc


def store_upload(db: Session, data: bytes, suggested_name: str | None) -> Document:
    validate_upload_bytes(data, suggested_name)
    return _store_bytes(
        db,
        data=data,
        source_url=None,
        final_url=None,
        suggested_name=suggested_name,
        source="upload",
    )


def resolve_storage_path(sha256: str) -> Path | None:
    p = settings.documents_dir / f"{sha256}.pdf"
    return p if p.exists() else None


def read_document_bytes(doc: Document) -> bytes:
    p = settings.documents_dir / f"{doc.sha256}.pdf"
    if not p.exists():
        raise FetchFailedError("Document bytes are no longer available on disk.", "STORAGE_MISSING")
    return p.read_bytes()


def storage_path_for(doc: Document) -> Path:
    return settings.documents_dir / f"{doc.sha256}.pdf"


def rasterize_page(doc: Document, page: int) -> bytes:
    path = storage_path_for(doc)
    png = raster_page_png(path, page)
    if png is None:
        raise InvalidDocumentError(f"Page {page} could not be rendered.", "RENDER_FAILED")
    return png


def thumbnail_path(doc: Document) -> Path:
    return settings.thumbs_dir / f"{doc.id}.png"


__all__ = ["analyze_url", "store_upload", "validate_upload_bytes", "read_document_bytes"]