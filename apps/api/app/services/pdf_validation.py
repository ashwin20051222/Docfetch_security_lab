"""PDF signature, corruption and capability validation.

``is_pdf_magic`` enforces the %PDF- header. ``inspect_pdf`` opens the file
with PyMuPDF to detect corruption, encryption and page count. Only trusted
validated files are ever accepted.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from app.core.errors import InvalidDocumentError

PDF_MAGIC = b"%PDF-"


def is_pdf_magic(data: bytes) -> bool:
    return data[:1024].lstrip().startswith(PDF_MAGIC)


def inspect_pdf(data: bytes) -> dict[str, Any]:
    """Return non-fabricated PDF metadata, or raise InvalidDocumentError."""
    if not is_pdf_magic(data):
        raise InvalidDocumentError(
            "Not a PDF: missing %%PDF- signature.", "UNSUPPORTED_FORMAT"
        )
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise InvalidDocumentError(
            "The PDF is corrupted or unreadable and could not be parsed.",
            "CORRUPTED_DOCUMENT",
        ) from exc

    if doc.needs_pass or doc.is_encrypted:
        doc.close()
        raise InvalidDocumentError(
            "The PDF is encrypted or password-protected.",
            "ENCRYPTED_DOCUMENT",
        )

    meta = doc.metadata or {}
    info = {
        "title": (meta.get("title") or "").strip() or None,
        "author": (meta.get("author") or "").strip() or None,
        "page_count": doc.page_count if doc.is_pdf else 0,
        "encrypted": bool(doc.is_encrypted),
        "pinned": doc.is_pdf,
    }
    doc.close()
    if info["page_count"] <= 0:
        raise InvalidDocumentError("The PDF contains no readable pages.", "INVALID_DOCUMENT")
    return info


def raster_page_png(path: Path, page_index: int) -> bytes | None:
    """Rasterize a single page to PNG bytes (0-indexed page)."""
    try:
        doc = fitz.open(path)
        if page_index < 0 or page_index >= doc.page_count:
            doc.close()
            return None
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        png = pix.tobytes("png")
        doc.close()
        return png
    except Exception:
        return None


def write_thumbnail(path: Path, out: Path) -> None:
    """First page rasterized down to a thumbnail PNG."""
    png = raster_page_png(path, 0)
    if png is None:
        return
    try:
        out.write_bytes(png)
    except OSError:
        pass