from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.log import request_id_var
from app.core.rate_limit import client_key

log = logging.getLogger("docfetch.middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id and record latency for every request."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        log.info(
            "%s %s -> %s (%sms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response