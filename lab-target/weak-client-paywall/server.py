"""weak-client-paywall: a paywall that is client-side only (port 9102).

The balance-hidden document is shipped to the browser in full regardless of
authorization; the "paywall" is a CSS overlay. A user who inspects the page
source sees the protected content. This is the vulnerability class described
in the project brief: the marker text and the full sample PDF are both
delivered without any server-side authorization decision.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../shared")

from common import App, json_response, make_app

_PAGE = b"""<!DOCTYPE html>
<html>
<head>
  <title>Monthly Energy Review</title>
  <style>
    .oc-paywall { z-index: 999; background: #fff; position: fixed; inset: 0; display: flex; }
  </style>
</head>
<body>
  <div class="oc-paywall">
    <div>Subscribe to keep reading.</div>
  </div>
  <main id="docfetch-protected-content">
    <h1>Monthly Energy Contract Annex</h1>
    <p>
      PETROCHEM-PLAN-2026-RESTRICTED-V3.pdf -- the full protected document,
      delivered to the browser before any server-side authorization check.
    </p>
    <p>Protected body: The legitimate monthly energy contract annex is 42 pages long.</p>
  </main>
</body>
</html>
"""

app = App(
    {
        # /labs/page delivers the full "protected" page to EVERYONE (vulnerable).
        "/labs/page": (False, lambda h: _serve_page(h)),
        "/reader": (False, lambda h: _serve_page(h)),
        "/": (False, lambda h: _serve_page(h)),
        # Direct file paths are also left wide open on this target.
        "/document.pdf": (False, lambda h: _serve_page(h)),
        "/protected/research.pdf": (False, lambda h: _serve_page(h)),
        "/files/doc.pdf": (False, lambda h: _serve_page(h)),
        "/api/document": (False, lambda h: _serve_page(h)),
        "/health": (False, lambda h: json_response(h, 200, {"status": "ok"})),
    }
)


def _serve_page(handler):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(_PAGE)))
    handler.end_headers()
    handler.wfile.write(_PAGE)


if __name__ == "__main__":
    import http.server
    import socketserver

    from common import make_app

    port = int(os.environ.get("PORT", "9102"))
    with socketserver.TCPServer(("0.0.0.0", port), make_app(app)) as httpd:
        print(f"weak-client-paywall listening on http://0.0.0.0:{port}", flush=True)
        httpd.serve_forever()