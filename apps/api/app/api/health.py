from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.database import get_db
from app.models import AuditEvent, Document, Download, Finding, LabTarget, SecurityTest

from .router import api

router = APIRouter(tags=["health"])

_startup = time.time()
settings = get_settings()


@api.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    db_error: str | None = None
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        db_ok = False
        db_error = str(exc)

    storage_ok = True
    try:
        settings.documents_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.documents_dir / ".health-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:  # pragma: no cover
        storage_ok = False
        db_error = db_error or str(exc)

    status = "ok" if (db_ok and storage_ok) else "error"
    return {
        "status": status,
        "version": settings.version,
        "uptime_seconds": round(time.time() - _startup, 2),
        "database": {
            "status": "ok" if db_ok else "error",
            "error": db_error,
            "engine": "sqlite" if settings.is_sqlite else "postgres",
        },
        "storage": {
            "status": "ok" if storage_ok else "error",
            "path": str(settings.documents_dir),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }