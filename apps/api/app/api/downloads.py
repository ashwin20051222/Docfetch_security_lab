from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Download
from app.schemas import DownloadRecord

from .router import api

router = APIRouter(tags=["downloads"])


@api.get("/downloads", response_model=list[DownloadRecord])
def list_downloads(db: Session = Depends(get_db)) -> list[DownloadRecord]:
    rows = db.scalars(select(Download).order_by(Download.downloaded_at.desc()).limit(100)).all()
    return [DownloadRecord.model_validate(r) for r in rows]