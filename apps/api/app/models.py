from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="ready")  # ready|failed|expired
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(24), default="download")  # download|upload
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    downloads: Mapped[list["Download"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Download(Base):
    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    bytes_transferred: Mapped[int] = mapped_column(Integer, default=0)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    document: Mapped["Document"] = relationship(back_populates="downloads")


class LabTarget(Base):
    __tablename__ = "lab_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    base_url: Mapped[str] = mapped_column(Text)
    environment_type: Mapped[str] = mapped_column(String(32), default="local")  # local|docker|network
    auth_status: Mapped[str] = mapped_column(String(32), default="none")  # none|token|header
    allowed_test_profiles: Mapped[list] = mapped_column(JSON, default=list)
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    tests: Mapped[list["SecurityTest"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class SecurityTest(Base):
    __tablename__ = "security_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_id: Mapped[str] = mapped_column(ForeignKey("lab_targets.id", ondelete="CASCADE"))
    profile: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="running")  # running|passed|failed|error
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    request_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    target: Mapped["LabTarget"] = relationship(back_populates="tests")
    finding: Mapped["Finding | None"] = relationship(
        back_populates="test", uselist=False, cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_id: Mapped[str] = mapped_column(ForeignKey("lab_targets.id", ondelete="CASCADE"))
    test_id: Mapped[str] = mapped_column(
        ForeignKey("security_tests.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(24))  # critical|high|medium|low|informational
    status: Mapped[str] = mapped_column(String(24), default="open")  # open|acknowledged|verified|fixed
    description: Mapped[str] = mapped_column(Text)
    expected_behavior: Mapped[str] = mapped_column(Text)
    observed_behavior: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    target: Mapped["LabTarget"] = relationship()
    test: Mapped["SecurityTest"] = relationship(back_populates="finding")


class SecurityReport(Base):
    __tablename__ = "security_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_id: Mapped[str | None] = mapped_column(
        ForeignKey("lab_targets.id", ondelete="SET NULL"), nullable=True
    )
    format: Mapped[str] = mapped_column(String(16), default="json")  # json|html
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


def default_expiry(days: int | None = None) -> datetime:
    ttl = days if days is not None else 14
    return _now() + timedelta(days=ttl)