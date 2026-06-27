"""SSRF-safe URL validation for server-side fetches (SAK-040)."""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Optional
from urllib.parse import urlparse

from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }
)


def spec_url_fetch_allowed() -> bool:
    """True only when the operator explicitly opts in to server-side URL fetches."""
    return os.environ.get("SAKURA_ALLOW_SPEC_URL_FETCH", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def validate_fetch_url(url: str) -> tuple[bool, Optional[str]]:
    """Return (ok, error_message) for a URL the backend may fetch."""
    if not url or not isinstance(url, str):
        return False, "URL is required"

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False, "Only http and https URLs are permitted"
    if parsed.username or parsed.password:
        return False, "Embedded credentials in URLs are not permitted"
    if not parsed.hostname:
        return False, "URL must include a hostname"

    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTNAMES:
        return False, f"Host {host!r} is not permitted"

    # Block obvious cloud metadata endpoints.
    if host in ("169.254.169.254", "fd00:ec2::254"):
        return False, "Link-local / metadata hosts are not permitted"

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in (80, 443):
            return False, f"Port {port} is not permitted for spec URL fetch"
    except ValueError:
        return False, "Invalid port in URL"

    # Resolve and verify every returned address is a public, non-special IP.
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return False, f"Could not resolve host: {exc}"

    if not infos:
        return False, "Could not resolve host"

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False, f"Unresolvable address {addr!r}"
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False, f"Resolved address {addr} is not a public routable target"

    return True, None
