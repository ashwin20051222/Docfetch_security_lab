from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import AuditEvent

log = logging.getLogger("docfetch.audit")


def record_audit(
    db: Session,
    event_type: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
    request_id: str | None = None,
) -> None:
    """Persist a structured audit event. Never logs credentials or bodies."""
    try:
        db.add(
            AuditEvent(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=_redact(detail),
                request_id=request_id,
            )
        )
        db.commit()
    except Exception:  # audit failure must never break the request
        db.rollback()
        log.exception("audit_write_failed type=%s", event_type)


_REDACT_KEYS = {"authorization", "cookie", "set-cookie", "token", "password", "x-api-key"}


def _redact(detail: dict | None) -> dict | None:
    if not detail:
        return detail
    out: dict = {}
    for k, v in detail.items():
        if isinstance(v, dict):
            out[k] = _redact(v)
        elif isinstance(v, str) and k.lower() in _REDACT_KEYS:
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out