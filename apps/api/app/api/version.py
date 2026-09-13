from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

from .router import api

router = APIRouter(tags=["version"])
settings = get_settings()


@api.get("/version")
def version():
    from app.core.rate_limit import default_rules

    rules = default_rules()
    return {
        "name": settings.app_name,
        "version": settings.version,
        "app_env": settings.app_env,
        "auth_configured": bool(settings.lab_admin_token),
        "rate_limits": {k: v.limit for k, v in rules.items()},
    }