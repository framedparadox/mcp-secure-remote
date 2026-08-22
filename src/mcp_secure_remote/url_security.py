"""URL validation helpers to block SSRF to private/restricted hosts."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class UrlSecurityOptions:
    allow_private_urls: bool = False


def validate_remote_url(server_url: str, options: UrlSecurityOptions) -> None:
    """Reject private, link-local, and metadata hosts unless explicitly allowed."""
    if options.allow_private_urls:
        return

    parsed = urlparse(server_url)
    host = _normalize_hostname(parsed.hostname or "")
    if _is_restricted_host(host):
        raise ValueError(
            f'Refusing to connect to private or restricted host "{host}"; '
            "pass --allow-private-urls for local/dev targets."
        )


def _normalize_hostname(hostname: str) -> str:
    trimmed = hostname.strip().lower()
    if trimmed.startswith("[") and trimmed.endswith("]"):
        return trimmed[1:-1]
    return trimmed


def _is_restricted_host(host: str) -> bool:
    if not host:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return True
    if host in {"0.0.0.0", "::"}:
        return True

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False

    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )
