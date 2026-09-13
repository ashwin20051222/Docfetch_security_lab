"""Centralized configuration. Every knob is an environment variable.

Secrets are never read into the browser; this module is backend-side only.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = "DocFetch Security Lab"
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_base_url: str = Field(default="", alias="API_BASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    version: str = "0.1.0"

    # Database
    database_url: str = Field(default="sqlite:///./data/docfetch.db", alias="DATABASE_URL")
    data_dir: str = Field(default="./data", alias="DATA_DIR")

    # Document handling
    max_download_size: int = Field(default=104_857_600, alias="MAX_DOWNLOAD_SIZE")
    max_upload_size: int = Field(default=52_428_800, alias="MAX_UPLOAD_SIZE")
    download_ttl_days: int = Field(default=14, alias="DOWNLOAD_TTL_DAYS")
    fetch_timeout_seconds: float = Field(default=25.0, alias="FETCH_TIMEOUT_SECONDS")
    max_redirects: int = Field(default=5, alias="MAX_REDIRECTS")

    # Rate limiting
    rate_limit_per_minute: int = Field(default=30, alias="RATE_LIMIT_PER_MINUTE")
    download_rate_per_minute: int = Field(default=60, alias="DOWNLOAD_RATE_PER_MINUTE")

    # Security lab
    authorized_lab_targets: str = Field(
        default="http://127.0.0.1:9101,http://127.0.0.1:9102,http://127.0.0.1:9103",
        alias="AUTHORIZED_LAB_TARGETS",
    )
    lab_test_timeout_seconds: float = Field(default=20.0, alias="LAB_TEST_TIMEOUT_SECONDS")
    lab_admin_token: str = Field(default="", alias="LAB_ADMIN_TOKEN")

    # Observable URLs for the health page
    deployed_web_url: str = Field(default="", alias="DEPLOYED_WEB_URL")

    @property
    def authorized_targets(self) -> list[str]:
        return [u.strip() for u in self.authorized_lab_targets.split(",") if u.strip()]

    @property
    def data_root(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def documents_dir(self) -> Path:
        p = self.data_root / "documents"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def thumbs_dir(self) -> Path:
        p = self.data_root / "thumbs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def reports_dir(self) -> Path:
        p = self.data_root / "reports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()