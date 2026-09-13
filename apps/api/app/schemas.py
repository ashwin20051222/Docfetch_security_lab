from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=4, max_length=4096)
    title_hint: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_url: str | None = None
    final_url: str | None = None
    title: str | None = None
    filename: str | None = None
    mime_type: str
    size_bytes: int
    page_count: int | None = None
    sha256: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    source: str
    created_at: datetime
    expires_at: datetime | None = None


class AnalyzeResult(BaseModel):
    document: DocumentOut
    verdict: str  # "document_found" | "not_a_document" | "blocked" | "failed"


class UploadResult(BaseModel):
    document: DocumentOut
    verdict: str


class PreviewPage(BaseModel):
    page: int
    width: int
    height: int
    thumb_url: str
    image_url: str


class PreviewOut(BaseModel):
    document_id: str
    page_count: int
    pages: list[PreviewPage]


class DownloadRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    downloaded_at: datetime
    bytes_transferred: int
    user_agent: str | None = None


class DeleteResult(BaseModel):
    deleted: bool
    id: str


# ---------------------------------------------------------------------------
# Dashboard / health
# ---------------------------------------------------------------------------


class DashboardSummary(BaseModel):
    documents_total: int
    uploads_total: int
    downloads_total: int
    tests_total: int
    open_findings: int
    all_findings: int
    targets_total: int
    targets_reachable: int
    recent_activity: list[dict]


class HealthCheck(BaseModel):
    status: Literal["ok", "degraded", "error"]
    version: str
    uptime_seconds: float | None = None
    database: dict[str, Any]
    storage: dict[str, Any]
    timestamp: datetime


class VersionOut(BaseModel):
    name: str
    version: str
    app_env: str
    auth_configured: bool
    rate_limits: dict[str, int]


# ---------------------------------------------------------------------------
# Security Lab
# ---------------------------------------------------------------------------


class LabTargetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    base_url: str = Field(min_length=4, max_length=4096)
    environment_type: Literal["local", "docker", "network"] = "local"
    auth_status: Literal["none", "token", "header"] = "none"
    allowed_test_profiles: list[str] = Field(default_factory=list)
    description: str | None = None


class LabTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str
    environment_type: str
    auth_status: str
    allowed_test_profiles: list[str]
    authorized: bool
    enabled: bool
    description: str | None = None
    reachable: bool | None = None
    last_checked_at: datetime | None = None
    created_at: datetime


class SecurityTestCreate(BaseModel):
    target_id: str
    profile: str


class RequestEvidence(BaseModel):
    method: str
    url: str
    timestamp: str
    headers: dict[str, str] = Field(default_factory=dict, description="Redacted headers")
    body_summary: str | None = None


class ResponseEvidence(BaseModel):
    status: int
    content_type: str | None = None
    content_length: int | None = None
    security_headers: dict[str, str] = Field(default_factory=dict)
    body_sha256: str | None = None
    body_preview: str | None = None


class EvidenceBlock(BaseModel):
    label: str
    request: RequestEvidence
    response: ResponseEvidence


class SecurityTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str
    profile: str
    title: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    request_summary: dict[str, Any] | None = None
    response_summary: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    error_message: str | None = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str
    test_id: str
    title: str
    severity: str
    status: str
    description: str
    expected_behavior: str
    observed_behavior: str
    recommendation: str
    evidence: dict[str, Any] | None = None
    created_at: datetime


class FindingPatch(BaseModel):
    status: Literal["open", "acknowledged", "verified", "fixed"]
    recommendation: str | None = None


class ReportGenerate(BaseModel):
    target_id: str | None = None
    formats: list[Literal["json", "html"]] = Field(default_factory=lambda: ["json"])


class SecurityReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str | None = None
    format: str
    path: str | None = None
    summary: dict[str, Any] | None = None
    finding_count: int
    created_at: datetime


class TargetCheckOut(BaseModel):
    target_id: str
    reachable: bool
    checked_at: datetime


class TestProfileOut(BaseModel):
    name: str
    title: str
    description: str
    apply_to: list[str]  # environment types this profile applies to


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------


class ErrorOut(BaseModel):
    error: dict[str, Any]


class ActivityItem(BaseModel):
    id: str
    kind: str
    summary: str
    created_at: datetime
    meta: dict[str, Any] | None = None