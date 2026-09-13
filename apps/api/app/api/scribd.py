"""Scribd downloader API — mirrors the scribsave.net flow exactly.

submit → status polling → fetch downloads → download pdf/pptx.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.errors import DocumentNotFoundError
from app.services import scribd as svc

log = logging.getLogger("docfetch.api.scribd")

router = APIRouter(prefix="/api", tags=["scribd"])


class SubmitRequest(BaseModel):
    url: str = Field(..., description="Scribd document URL")
    format: str | None = Field(default=None, description="hint (pdf|pptx); auto-detected anyway")


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@router.post("/submit", status_code=202)
async def submit_download(payload: SubmitRequest) -> dict:
    task = svc.submit(payload.url)
    asyncio.create_task(svc.run_job(task.id))
    return {
        "task_id": task.id,
        "status": task.status,
        "message": "Download queued.",
    }


@router.get("/status/{task_id}")
async def task_status(task_id: str) -> dict:
    task = svc.get_task(task_id)
    if task is None:
        return _error_response(404, "TASK_NOT_FOUND", "Task not found.")
    return {
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "stage": task.stage,
        "item_id": task.item_id,
        "error": task.error,
    }


@router.get("/item/{item_id}")
async def item_meta(item_id: str) -> dict:
    item = svc.get_item(item_id)
    if item is None:
        return _error_response(404, "ITEM_NOT_FOUND", "Item not found or expired.")
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "author": item.author,
        "page_count": item.page_count,
        "url": item.url,
        "error": item.error,
    }


def _format_entry(item: svc.ScribdItem, fmt: str) -> dict:
    path = item.pdf_path if fmt == "pdf" else item.pptx_path
    ready = path is not None and path.exists()
    size_bytes = path.stat().st_size if ready else 0
    return {
        "ready": ready,
        "size_bytes": size_bytes,
        "filename": f"{svc._safe_file_stem(item.title)}.{fmt}" if ready else None,
        "url": f"/api/download/{fmt}/{item.id}",
    }


@router.get("/item/{item_id}/downloads")
async def item_downloads(item_id: str) -> dict:
    item = svc.get_item(item_id)
    if item is None:
        return _error_response(404, "ITEM_NOT_FOUND", "Item not found or expired.")
    return {
        "item_id": item.id,
        "pdf": _format_entry(item, "pdf"),
        "pptx": _format_entry(item, "pptx"),
    }


@router.post("/item/{item_id}/formats/{fmt}/generate", status_code=202)
async def generate_format(item_id: str, fmt: str) -> dict:
    item = svc.get_item(item_id)
    if item is None:
        return _error_response(404, "ITEM_NOT_FOUND", "Item not found or expired.")
    if fmt not in ("pdf", "pptx"):
        return _error_response(422, "INVALID_FORMAT", "Supported formats: pdf, pptx.")

    if fmt == "pptx":
        if item.pptx_path is not None and item.pptx_path.exists():
            return {"item_id": item.id, "format": fmt, "status": "ready"}
        if item.pptx_busy:
            return {"item_id": item.id, "format": fmt, "status": "running"}
        asyncio.create_task(svc.generate_pptx(item.id))
        return {"item_id": item.id, "format": fmt, "status": "running"}

    # pdf is always produced during processing.
    if item.pdf_path is not None and item.pdf_path.exists():
        return {"item_id": item.id, "format": fmt, "status": "ready"}
    return _error_response(409, "FORMAT_NOT_READY", "PDF is not ready yet.")


@router.get("/download/pdf/{item_id}")
async def download_pdf(item_id: str, request: Request) -> FileResponse:
    item = svc.get_item(item_id)
    if item is None:
        return _error_response(404, "ITEM_NOT_FOUND", "Item not found or expired.")
    if item.pdf_path is None or not item.pdf_path.exists():
        return _error_response(409, "FORMAT_NOT_READY", "PDF is not ready yet.")
    filename = svc._safe_file_stem(item.title)
    return FileResponse(
        item.pdf_path,
        media_type="application/pdf",
        content_disposition_type="attachment",
        filename=f"{filename}.pdf",
    )


@router.get("/download/pptx/{item_id}")
async def download_pptx(item_id: str, request: Request) -> FileResponse:
    item = svc.get_item(item_id)
    if item is None:
        return _error_response(404, "ITEM_NOT_FOUND", "Item not found or expired.")
    if item.pptx_path is None or not item.pptx_path.exists():
        return _error_response(
            409,
            "FORMAT_NOT_READY",
            "PPTX is not generated yet. Call POST /api/item/{id}/formats/pptx/generate first.",
        )
    filename = svc._safe_file_stem(item.title)
    return FileResponse(
        item.pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        content_disposition_type="attachment",
        filename=f"{filename}.pptx",
    )


__all__ = ["router"]