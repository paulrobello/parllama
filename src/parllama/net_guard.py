"""SSRF guard shared by every code path that fetches a user- or model-supplied URL."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    """Raised when a URL is not http(s) or resolves to a non-public address."""


def check_public_url(url: str, kind: str = "resource") -> None:
    """Reject URLs that are not http(s) or whose host resolves to a non-public address.

    Blocks loopback, RFC1918/ULA private, link-local (including cloud metadata at
    169.254.169.254), multicast, and reserved ranges. Every resolved address must be
    public. A DNS answer that changes between this check and the connect is not covered,
    so callers must re-check every redirect hop and disable automatic redirects.

    Args:
        url: The URL about to be fetched.
        kind: Noun used in error messages (e.g. ``"document"``, ``"image"``).

    Raises:
        UnsafeUrlError: If the URL may not be fetched.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrlError(f"Only http(s) {kind} URLs are allowed: {url}")
    try:
        port = parts.port
    except ValueError as e:
        raise UnsafeUrlError(f"Invalid {kind} URL: {url}") from e
    try:
        infos = socket.getaddrinfo(parts.hostname, port or None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError) as e:
        raise UnsafeUrlError(f"Cannot resolve {kind} host '{parts.hostname}': {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            raise UnsafeUrlError(f"Refusing to fetch {kind} from non-public address {ip} ({parts.hostname})")
