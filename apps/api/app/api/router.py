from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.errors import RateLimitedError
from app.core.rate_limit import client_key, default_rules, limiter

api = APIRouter(prefix="/api/v1")


def enforce_rate_limit(request: Request, rule_group: str) -> None:
    rules = default_rules()
    rule = rules.get(rule_group)
    if rule is None:
        return
    key = f"{rule.group}:{client_key(request)}"
    if not limiter.allow(key, limit=rule.limit):
        raise RateLimitedError(
            f"Rate limit reached for this endpoint (max {rule.limit} requests/minute).",
            code="RATE_LIMITED",
        )


def include_all() -> None:
    """Import route modules for their decorator side-effects on the shared ``api`` router."""
    from app.api import (  # noqa: F401
        analyze,
        dashboard,
        documents,
        downloads,
        health,
        lab,
        uploads,
        version,
    )