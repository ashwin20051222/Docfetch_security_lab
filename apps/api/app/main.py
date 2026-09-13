from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.errors import ApiError
from app.core.log import setup_logging
from app.core.middleware import RequestContextMiddleware

settings = get_settings()
setup_logging(settings.log_level)

log = logging.getLogger("docfetch")

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "DocFetch Security Lab backend — public document retrieval with SSRF-safe "
        "fetching, real PDF validation, and an authorized local security lab."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lab tool; auth via API token when configured
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_payload(getattr(request.state, "request_id", None)),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected server error occurred.",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


from app.database import init_db
from app.api.router import api, include_all  # noqa: E402


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_default_lab_targets()
    log.info("startup complete env=%s", settings.app_env)


def seed_default_lab_targets() -> None:
    """Register any allowlisted targets that are not yet stored.

    Only hosts present in AUTHORIZED_LAB_TARGETS are ever registered
    automatically; nothing is fabricated.
    """
    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import LabTarget

    defaults = [
        {
            "name": "Lab: Secure Paywall",
            "base_url": "http://127.0.0.1:9101",
            "profiles": ["auth-enforcement", "header-hardening"],
            "env": "local",
            "auth": "token",
            "description": "Server enforces authorization before serving protected content (expected 403 without credentials).",
        },
        {
            "name": "Lab: Weak Client-Side Paywall",
            "base_url": "http://127.0.0.1:9102",
            "profiles": ["client-side-access-control"],
            "env": "local",
            "auth": "none",
            "description": "The UI hides protected content but the lab server fails to enforce authorization server-side.",
        },
        {
            "name": "Lab: Weak Direct File Access",
            "base_url": "http://127.0.0.1:9103",
            "profiles": ["direct-file-access", "header-hardening"],
            "env": "local",
            "auth": "none",
            "description": "The lab server exposes a protected synthetic document without proper authorization.",
        },
    ]

    allowlist = {u.rstrip("/").lower() for u in settings.authorized_targets}
    with SessionLocal() as db:
        for d in defaults:
            if d["base_url"].rstrip("/").lower() not in allowlist:
                continue  # deployment owner removed this default
            exists = db.scalar(
                select(LabTarget).where(LabTarget.base_url == d["base_url"])
            )
            if exists:
                continue
            db.add(
                LabTarget(
                    name=d["name"],
                    base_url=d["base_url"],
                    environment_type=d["env"],
                    auth_status=d["auth"],
                    allowed_test_profiles=d["profiles"],
                    authorized=True,
                    enabled=True,
                    description=d["description"],
                )
            )
        db.commit()


include_all()
app.include_router(api)