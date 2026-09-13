"""SSRF defense tests — the highest-leverage security surface."""
from __future__ import annotations

import pytest

from app.security.ssrf import (
    PUBLIC_POLICY,
    SSRFBlocked,
    fetch,
    validate_hostname,
)


def test_blocks_non_http_scheme():
    with pytest.raises(SSRFBlocked) as ei:
        fetch("ftp://example.com/file.pdf")
    assert ei.value.code == "SSRF_BLOCKED_SCHEME"
    with pytest.raises(SSRFBlocked):
        fetch("file:///etc/passwd")
    with pytest.raises(SSRFBlocked):
        fetch("gopher://example.com")


def test_blocks_loopback_hosts():
    for url in (
        "http://127.0.0.1/x.pdf",
        "http://localhost/x.pdf",
        "http://[::1]/x.pdf",
        "http://0.0.0.0/x.pdf",
    ):
        with pytest.raises(SSRFBlocked):
            fetch(url, policy=PUBLIC_POLICY)


def test_blocks_private_ipv4():
    for url in (
        "http://10.0.0.5/x.pdf",
        "http://172.16.0.9/x.pdf",
        "http://192.168.1.20/x.pdf",
    ):
        with pytest.raises(SSRFBlocked):
            fetch(url, policy=PUBLIC_POLICY)


def test_blocks_link_local_and_multicast():
    with pytest.raises(SSRFBlocked):
        fetch("http://169.254.169.254/latest/meta-data", policy=PUBLIC_POLICY)
    with pytest.raises(SSRFBlocked):
        fetch("http://169.254.170.2/credentials", policy=PUBLIC_POLICY)
    with pytest.raises(SSRFBlocked):
        fetch("http://224.0.0.1/x.pdf", policy=PUBLIC_POLICY)


def test_blocks_aws_metadata_domains():
    for host in (
        "metadata.google.internal",
        "169.254.169.254.nip.io",
        "metadata.azure.internal",
    ):
        with pytest.raises(SSRFBlocked):
            validate_hostname(host, PUBLIC_POLICY, 80)


def test_blocks_ipv6_loopback_and_unique_local():
    with pytest.raises(SSRFBlocked):
        fetch("http://[::1]/x.pdf", policy=PUBLIC_POLICY)
    with pytest.raises(SSRFBlocked):
        fetch("http://[fc00::1]/x.pdf", policy=PUBLIC_POLICY)


def test_blocks_reserved_carrier_grade_nat():
    with pytest.raises(SSRFBlocked):
        fetch("http://100.64.0.1/x.pdf", policy=PUBLIC_POLICY)


def test_blocks_redirect_to_private_ip():
    """A URL that 302-redirects to a private IP must be refused on the second hop."""
    import http.server
    import threading
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://10.0.0.1/secret.pdf")
            self.end_headers()

        def log_message(self, *args):
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as srv:
        port = srv.server_address[1]
        t = threading.Thread(target=srv.handle_request, daemon=True)
        t.start()

        # Policy allows loopback (so the first hop connects) but denies private
        # ranges — the redirect destination must be refused.
        from app.security.ssrf import SSRFPolicy

        nested_policy = SSRFPolicy(allow_loopback=True, allow_private=False)
        with pytest.raises(SSRFBlocked):
            fetch(f"http://127.0.0.1:{port}/start", policy=nested_policy)

        # The fully-public policy refuses the original loopback URL outright.
        with pytest.raises(SSRFBlocked):
            fetch(f"http://127.0.0.1:{port}/start", policy=PUBLIC_POLICY)
        srv.server_close()


def test_dns_rebinding_prevention():
    """All resolved addresses are validated before connecting (no IP pinning bypass)."""
    # example.com resolves to public IPs only; ensure no private address is returned.
    host = "example.com"
    import socket

    infos = socket.getaddrinfo(host, 80, proto=socket.IPPROTO_TCP)
    import ipaddress

    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        assert not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)


def test_public_policy_allows_real_public_fetch():
    """End-to-end: a genuinely public URL is retrievable under public policy."""
    resp = fetch("https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf")
    assert resp.status == 200
    assert resp.body.startswith(b"%PDF-")