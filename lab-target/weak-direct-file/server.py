"""weak-direct-file: protected files are served from guessable static paths (port 9103).

No authorization at all: the raw file bytes are retrievable directly by path.
This demonstrates the "document is reachable by direct file path" failure mode
that a document-fetching tool can hit even when the visible paywall is bypassed.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../shared")

from common import App, html_response, json_response, make_app, pdf_response

PROTECTED_PATHS = {"/document.pdf", "/protected/research.pdf", "/files/doc.pdf"}

app = App(
    {
        "/health": (False, lambda h: json_response(h, 200, {"status": "ok"})),
        # Direct static file paths -- served with no authorization (vulnerable).
        "/document.pdf": (False, pdf_response),
        "/protected/research.pdf": (False, pdf_response),
        "/files/doc.pdf": (False, pdf_response),
        "/api/document": (False, pdf_response),
        "/labs/page": (
            False,
            lambda h: html_response(
                h,
                b"<html><body><p>public marketing page</p></body></html>",
            ),
        ),
        "/": (
            False,
            lambda h: html_response(
                h,
                b"<html><body><h1>Weak Direct File</h1></body></html>",
            ),
        ),
    }
)

if __name__ == "__main__":
    import http.server
    import socketserver

    from common import make_app

    port = int(os.environ.get("PORT", "9103"))
    with socketserver.TCPServer(("0.0.0.0", port), make_app(app)) as httpd:
        print(f"weak-direct-file listening on http://0.0.0.0:{port}", flush=True)
        httpd.serve_forever()