"""SSRF-safe HTTP retrieval.

Design goals
------------
1. Only ``http`` / ``https`` schemes are allowed.
2. Hostnames are resolved BEFORE any connection is made; every resolved
   address must be a globally routable (non-private, non-reserved) address.
3. The connection is pinned to a verified IP address while preserving the
   original hostname in ``Host`` / TLS-SNI, defeating DNS-rebinding attacks.
4. Every redirect hop is revalidated through the same policy.
5. Bounded redirects, bounded timeouts, bounded response size.

This uses the standard-library ``http.client`` parser over a hand-driven
socket so the remote address, TLS ``server_hostname`` and ``Host`` header
stay fully under our control.
"""
from __future__ import annotations

import http.client
import ipaddress
import logging
import socket
import ssl
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

log = logging.getLogger("docfetch.ssrf")


class SSRFBlocked(Exception):
    """Raised when a host or URL is refused by SSRF policy."""

    def __init__(self, reason: str, code: str, metadata: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.metadata = metadata or {}


class FetchError(Exception):
    """Raised when a request fails for a transport/documentation reason."""

    def __init__(self, reason: str, code: str, metadata: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.metadata = metadata or {}


@dataclass
class SSRFPolicy:
    allow_http: bool = True
    allow_https: bool = True
    allow_private: bool = False
    allow_loopback: bool = False
    allow_link_local: bool = False
    allow_reserved: bool = False
    dns_resolve_required: bool = True
    max_redirects: int = 5
    connect_timeout: float = 10.0
    read_timeout: float = 25.0
    max_response_bytes: int = 104_857_600


@dataclass
class Response:
    status: int
    final_url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    served_from: str = ""
    redirects: list[str] = field(default_factory=list)

    def header(self, name: str) -> str | None:
        for k, v in self.headers.items():
            if k.lower() == name.lower():
                return v
        return None

    @property
    def content_type(self) -> str:
        ct = self.header("content-type") or ""
        return ct.split(";")[0].strip().lower()

    @property
    def content_length(self) -> int:
        cl = self.header("content-length")
        return int(cl) if cl and cl.isdigit() else len(self.body)

    @property
    def security_headers(self) -> dict[str, str]:
        wanted = {
            "content-security-policy",
            "x-content-type-options",
            "x-frame-options",
            "strict-transport-security",
            "referrer-policy",
            "permissions-policy",
            "x-xss-protection",
        }
        return {k: v for k, v in self.headers.items() if k.lower() in wanted}


def _is_private(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or (isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local)
        or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"))
    )


def _blocked(default: bool, allowed: bool, label: str, addr: object) -> None:
    if not allowed:
        raise SSRFBlocked(
            f"Address family '{label}' (address {addr}) is not permitted by SSRF policy.",
            "SSRF_BLOCKED_PRIVATE",
            {"address": str(addr), "family": label},
        )


def validate_hostname(host: str, policy: SSRFPolicy, service_port: int) -> str:
    """Parse a host, returning the validated hostname (lowercased).

    IP literals are validated directly; DNS names are resolved and *all*
    resulting addresses are checked against the policy.
    """
    if not host:
        raise SSRFBlocked("Hostname is empty.", "SSRF_BLOCKED_EMPTY")

    host = host.strip().lower().rstrip(".")
    if not host or len(host) > 253:
        raise SSRFBlocked("Hostname is invalid.", "SSRF_BLOCKED_INVALID_HOST")

    # IPv6 literal, e.g. http://[::1]:8000/
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        _blocked(policy.allow_reserved, policy.allow_reserved, "reserved", ip)
        _check_ip(ip, policy)
        return host

    # Domain name — must not look like a number-dotted trick
    labels = host.split(".")
    if len(labels) < 2 and host not in ("localhost",):
        raise SSRFBlocked("Hostname must be a fully-qualified name.", "SSRF_BLOCKED_INVALID_HOST")

    try:
        infos = socket.getaddrinfo(host, service_port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFBlocked(
            f"Could not resolve hostname '{host}'.", "SSRF_DNS_FAILED", {"hostname": host}
        ) from exc

    seen = set()
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            continue
        if addr in seen:
            continue
        seen.add(addr)
        _check_ip(ip, policy)

    return host


def _check_ip(ip, policy: SSRFPolicy) -> None:
    if _is_private(ip):
        label = "private" if not ip.is_loopback else "loopback"
        if ip.is_loopback:
            _blocked(policy.allow_loopback, policy.allow_loopback, "loopback", ip)
        elif ip.is_link_local:
            _blocked(policy.allow_link_local, policy.allow_link_local, "link-local", ip)
        else:
            _blocked(policy.allow_private, policy.allow_private, label, ip)


def _pick_destination(host: str, port: int, policy: SSRFPolicy) -> str:
    """Return an IP to pin the connection to (the validated resolved host)."""
    try:
        ip = ipaddress.ip_address(host)
        _check_ip(ip, policy)
        return str(ip)
    except ValueError:
        pass
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
            _check_ip(ip, policy)
            return str(ip)
        except SSRFBlocked:
            continue
    raise SSRFBlocked(
        f"No routable destination found for '{host}'.", "SSRF_DNS_FAILED"
    )


def _validate_url(raw_url: str, policy: SSRFPolicy) -> tuple[str, int, str]:
    parsed = urlparse(raw_url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise SSRFBlocked(
            f"Scheme '{scheme or 'none'}' is not permitted (http/https only).",
            "SSRF_BLOCKED_SCHEME",
            {"scheme": scheme},
        )
    port = parsed.port or (443 if scheme == "https" else 80)
    host = parsed.hostname or ""
    return scheme, port, host


def _connect(scheme: str, ip: str, port: int, hostname: str, policy: SSRFPolicy):
    ctx = ssl.create_default_context() if scheme == "https" else None
    sock = socket.create_connection((ip, port), timeout=policy.connect_timeout)
    sock.settimeout(policy.read_timeout)
    if ctx is not None:
        sock = ctx.wrap_socket(sock, server_hostname=hostname)
    return sock


def fetch(
    raw_url: str,
    *,
    policy: SSRFPolicy | None = None,
    extra_headers: dict[str, str] | None = None,
    read_body: bool = True,
) -> Response:
    """Retrieve ``raw_url`` under SSRF policy. Returns a parsed Response."""
    policy = policy or SSRFPolicy()
    current_url = raw_url
    redirects: list[str] = []
    served_from = ""

    for hop in range(policy.max_redirects + 1):
        scheme, port, hostname = _validate_url(current_url, policy)
        ip = _pick_destination(hostname, port, policy)
        served_from = ip

        path = urlparse(current_url).path or "/"
        if urlparse(current_url).query:
            path += "?" + urlparse(current_url).query

        target = "%s://%s:%s" % (scheme, hostname, port)
        log.info("GET %s (pinned %s)", current_url, ip)

        headers = {
            "Host": hostname if port in (80, 443) else f"{hostname}:{port}",
            "User-Agent": "DocFetch-Security-Lab/0.1 (+authorized research)",
            "Accept": "application/pdf, application/octet-stream;q=0.8, */*;q=0.1",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        headers.update(extra_headers or {})

        sock = _connect(scheme, ip, port, hostname, policy)
        try:
            request_line = f"GET {path} HTTP/1.1"
            payload = request_line + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
            sock.sendall(payload.encode("latin-1"))

            resp = http.client.HTTPResponse(sock, method="GET", url=path)
            resp.begin()
            status = resp.status
            resp_headers = {}
            for k, v in resp.getheaders():
                resp_headers[k.lower()] = resp_headers.get(k.lower(), v)

            loc = resp_headers.get("location")
            if status in (301, 302, 303, 307, 308) and loc:
                redirects.append(current_url)
                if hop >= policy.max_redirects:
                    raise FetchError(
                        "Too many redirects while following the document URL.",
                        "REDIRECT_TOO_MANY",
                        {"redirects": len(redirects)},
                    )
                next_url = urljoin(current_url, loc)
                log.info("redirect %s -> %s", current_url, next_url)
                current_url = next_url
                resp.close()
                continue

            body = b""
            if read_body:
                body = _read_limited(resp, policy.max_response_bytes)
            else:
                resp.close()
            return Response(
                status=status,
                final_url=current_url,
                headers=resp_headers,
                body=body,
                served_from=served_from,
                redirects=redirects,
            )
        finally:
            try:
                sock.close()
            except OSError:
                pass

    raise FetchError("Too many redirects.", "REDIRECT_TOO_MANY")


def _read_limited(resp: http.client.HTTPResponse, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = resp.read(min(65_536, limit + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise FetchError(
                "Response exceeded the configured size limit.",
                "RESPONSE_TOO_LARGE",
                {"limit_bytes": limit},
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Public policy instances
# ---------------------------------------------------------------------------

PUBLIC_POLICY = SSRFPolicy(
    allow_private=False,
    allow_loopback=False,
    allow_link_local=False,
    allow_reserved=False,
    dns_resolve_required=True,
)