"""secure-paywall: the CORRECTLY secured training target (port 9101).

Server-side authorization is enforced on every protected resource:
an unauthenticated request receives HTTP 403 and no document bytes.
The DocFetch security lab should PASS its auth checks against this host.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../shared")

from common import App, html_response, json_response, make_app, pdf_response

app = App(
    {
        "/health": (False, lambda h: json_response(h, 200, {"status": "ok"})),
        # protected document endpoints -- must never serve bytes without a token
        "/document.pdf": (True, pdf_response),
        "/api/document": (True, pdf_response),
        "/protected/research.pdf": (True, pdf_response),
        "/files/doc.pdf": (True, pdf_response),
        "/labs/page": (
            False,
            lambda h: html_response(
                h,
                b"<html><body><div class='reader'>public marketing page</div></body></html>",
            ),
        ),
        "/reader": (
            False,
            lambda h: html_response(
                h,
                b"<html><body><div class='reader'>public marketing page</div></body></html>",
            ),
        ),
        "/": (
            False,
            lambda h: html_response(
                h,
                b"<html><body><h1>Secure Paywall</h1><p>All protected content is gated server-side.</p></body></html>",
            ),
        ),
    }
)

if __name__ == "__main__":
    import http.server
    import socketserver

    port = int(os.environ.get("PORT", "9101"))
    with socketserver.TCPServer(("0.0.0.0", port), make_app(app)) as httpd:
        print(f"secure-paywall listening on http://0.0.0.0:{port}", flush=True)
        httpd.serve_forever()