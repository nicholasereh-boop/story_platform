"""The ONLY way News fetches anything from the internet: https only, the registered feed's own host only, public addresses only,
manual redirects (each hop re-checked), hard size and time limits. Defends against SSRF (private, loopback, link-local and
metadata addresses; redirects to them) and unbounded downloads. Provider keys and cookies are never sent.

DNS rebinding note: the host must equal the host staff registered for the source AND resolve only to public addresses at check
time. Staff control the registered host, so the resolution check is the second line of defence, not the only one."""
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests

MAX_REDIRECTS = 3


class UnsafeTarget(Exception):
    pass


class FetchFailed(Exception):
    """`message` is safe to show to staff. `retryable` is True for failures that may go away on their own (network trouble, 5xx, 429)."""

    def __init__(self, message, code="fetch_failed", retryable=False, http_status=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.http_status = http_status


def is_public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local or ip.is_private)


def resolve_public(host, port=443):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise UnsafeTarget("The host could not be resolved.")
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(is_public_ip(a) for a in addresses):
        raise UnsafeTarget("The host does not resolve to a public address.")
    return addresses


def check_target(url, allowed_hosts, resolver=resolve_public):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        port = parts.port
    except ValueError:
        raise UnsafeTarget("Bad port.")
    if parts.scheme != "https" or parts.username is not None or parts.password is not None or port not in (None, 443):
        raise UnsafeTarget("Only plain https addresses on the standard port are allowed.")
    if not host or host not in {h.lower() for h in allowed_hosts}:
        raise UnsafeTarget("That host is not the one registered for this source.")
    resolver(host)
    return host


def fetch_bytes(url, *, allowed_hosts, max_bytes, timeout=10, deadline_seconds=30, session=None, resolver=resolve_public, accept="application/rss+xml, application/atom+xml, application/xml, text/xml"):
    """The response body of `url` (at most `max_bytes`). Raises FetchFailed. Returns (body, http_status)."""
    session = session or requests.Session()
    started = time.monotonic()
    response = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                check_target(url, allowed_hosts, resolver)
            except UnsafeTarget as exc:
                raise FetchFailed(f"Not fetched: {exc}", "unsafe_target")
            try:
                response = session.get(url, headers={"Accept": accept, "User-Agent": "ResourceBoardNews/1.0"}, stream=True, allow_redirects=False, timeout=timeout)
            except requests.RequestException:
                raise FetchFailed("The feed could not be reached.", "network", retryable=True)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "")
                response.close()
                response = None
                url = urljoin(url, location)
                continue
            break
        else:
            raise FetchFailed("Too many redirects.", "redirects")
        if response is None:
            raise FetchFailed("The feed could not be reached.", "network", retryable=True)
        status = response.status_code
        if status != 200:
            raise FetchFailed(f"The feed answered with HTTP {status}.", f"http_{status}", retryable=status >= 500 or status == 429, http_status=status)
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise FetchFailed("The feed is larger than the allowed size.", "too_large")
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=16384):
            total += len(chunk)
            if total > max_bytes:
                raise FetchFailed("The feed is larger than the allowed size.", "too_large")
            if time.monotonic() - started > deadline_seconds:
                raise FetchFailed("The feed took too long to download.", "timeout", retryable=True)
            chunks.append(chunk)
        return b"".join(chunks), status
    finally:
        if response is not None:
            response.close()
