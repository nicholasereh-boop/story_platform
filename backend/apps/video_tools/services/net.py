"""The ONLY way adapters may fetch a media file: allow-listed hosts, public addresses, manual redirects, hard limits.

Defends against SSRF: arbitrary schemes, private / loopback / link-local / metadata addresses, redirects to them, and
unbounded downloads. Every hop (the first request and each redirect) is checked again. Note on DNS rebinding: the host
must be on the adapter's allow-list of the provider's own domains AND resolve only to public addresses at check time;
an allow-listed provider domain that an attacker cannot control is the real defence, the resolution check is the second.
"""
import ipaddress
import os
import socket
import time
from urllib.parse import urlsplit

import requests

MAX_REDIRECTS = 3


class UnsafeTarget(Exception):
    pass


class FetchFailed(Exception):
    """A safe-to-show message about why the file could not be fetched."""

    def __init__(self, message, code="fetch_failed"):
        super().__init__(message)
        self.message = message
        self.code = code


def is_public_ip(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved and not ip.is_loopback and not ip.is_link_local and not ip.is_private


def resolve_public(host, port=443):
    """Every address `host` resolves to must be public, or UnsafeTarget."""
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
    if host not in {h.lower() for h in allowed_hosts}:
        raise UnsafeTarget("That host is not allowed.")
    resolver(host)
    return host


def download_to_file(url, dest_path, *, allowed_hosts, max_bytes, timeout=30, deadline_seconds=300, session=None,
                     headers=None, resolver=resolve_public):
    """Stream `url` into `dest_path`. Returns bytes written. Removes the partial file on any failure."""
    session = session or requests.Session()
    started = time.monotonic()
    response = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                check_target(url, allowed_hosts, resolver)
            except UnsafeTarget:
                raise FetchFailed("The file is hosted somewhere we do not allow, so it was not downloaded.", "unsafe_target")
            response = session.get(url, headers=headers or {}, stream=True, allow_redirects=False, timeout=timeout)
            if response.status_code in (301, 302, 303, 307, 308):
                url = response.headers.get("Location", "")
                response.close()
                response = None
                continue
            break
        else:
            raise FetchFailed("Too many redirects.", "redirects")
        if response is None or response.status_code != 200:
            raise FetchFailed("The platform did not provide the file.", "not_provided")
        declared = response.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise FetchFailed("The file is larger than the allowed size.", "too_large")
        written = 0
        with open(dest_path, "wb") as out:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise FetchFailed("The file is larger than the allowed size.", "too_large")
                if time.monotonic() - started > deadline_seconds:
                    raise FetchFailed("The download took too long.", "timeout")
                out.write(chunk)
        return written
    except requests.RequestException:
        raise FetchFailed("Could not reach the platform.", "unreachable")
    except BaseException:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise
    finally:
        if response is not None:
            response.close()
