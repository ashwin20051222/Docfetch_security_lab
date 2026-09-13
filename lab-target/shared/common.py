"""Shared plumbing for the DocFetch Security Lab training targets.

The three targets under lab-target/ reproduce a real vulnerability class on
an endpoint the deployment owner controls locally (ports 9101/9102/9103).
Each target serves the same real sample document but with a *different*
authorization posture, so the lab engine's findings reflect genuinely
observed server behavior -- nothing here is fabricated.

Only stdlib is used so the targets run with zero dependencies:
    python3 server.py   (or: PYTHONPATH=.. python3 ...)
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler

SHARED_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(SHARED_DIR, "sample-document.pdf")
with open(PDF_PATH, "rb") as f:
    SAMPLE_PDF_BYTES = f.read()

# Authorization header the DocFetch Security Lab sends by default.
LAB_TOKEN = "Bearer lab-authorized"


def json_response(handler, status, payload, *, headers=None):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    for k, v in (headers or {}).items():
        handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)


def pdf_response(handler, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/pdf")
    handler.send_header("Content-Disposition", 'inline; filename="sample-document.pdf"')
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(SAMPLE_PDF_BYTES)))
    handler.end_headers()
    handler.wfile.write(SAMPLE_PDF_BYTES)


def html_response(handler, body: bytes, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_app(root_app):
    """Wrap an App instance in a BaseHTTPRequestHandler-compatible class."""
    class _Handler(BaseHTTPRequestHandler):
        server_version = "DocFetchLab/1.0"

        def do_GET(self):
            root_app.handle(self)

        def do_POST(self):
            root_app.handle(self)

        def log_message(self, fmt, *args):
            # keep the log line quiet for lab probing
            pass

    return _Handler


class App:
    """Declarative routing target: route -> (required_auth, responder)."""

    def __init__(self, routes: dict[str, tuple[bool, object]]):
        self.routes = routes

    def handle(self, handler):
        path = handler.path.split("?", 1)[0]
        route = self.routes.get(path)

        if route is None:
            json_response(handler, 404, {"error": "not_found", "path": handler.path})
            return

        requires_auth, responder = route
        if requires_auth:
            auth = handler.headers.get("Authorization", "")
            if auth != LAB_TOKEN:
                json_response(
                    handler,
                    403,
                    {"error": "forbidden", "reason": "missing_paywall_identity"},
                )
                return
        responder(handler)