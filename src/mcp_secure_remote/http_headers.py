"""HTTP header validation shared by args and auth helpers."""
from __future__ import annotations

import re

_VALID_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$")


def validate_http_header(name: str, value: str) -> None:
    """Raise ValueError for header names/values that could enable injection."""
    if not _VALID_HEADER_NAME_RE.match(name):
        raise ValueError(
            f'Invalid header name {name!r}: must be a valid RFC 7230 HTTP token '
            r"(alphanumerics and !#$%&'*+-.^_`|~)"
        )
    if re.search(r"[\r\n\x00]", value):
        raise ValueError(
            f"Header value for {name!r} must not contain CR, LF, or NUL characters"
        )
