"""Build Authorization / API-key headers from env or CLI auth options."""
from __future__ import annotations

import base64
from dataclasses import dataclass

from .http_headers import validate_http_header as _validate_http_header


@dataclass
class AuthOptions:
    bearer: str | None = None
    basic: str | None = None
    api_key: str | None = None
    api_key_header: str | None = None


def build_auth_headers(auth: AuthOptions) -> dict[str, str]:
    if auth.bearer and auth.basic:
        raise ValueError("Use only one of --auth-bearer or --auth-basic, not both.")

    headers: dict[str, str] = {}

    if auth.bearer:
        value = f"Bearer {auth.bearer}"
        _validate_http_header("Authorization", value)
        headers["Authorization"] = value
    elif auth.basic:
        if ":" not in auth.basic:
            raise ValueError('--auth-basic expects "username:password".')
        encoded = base64.b64encode(auth.basic.encode()).decode()
        value = f"Basic {encoded}"
        _validate_http_header("Authorization", value)
        headers["Authorization"] = value

    if auth.api_key:
        header_name = auth.api_key_header or "X-Api-Key"
        _validate_http_header(header_name, auth.api_key)
        headers[header_name] = auth.api_key

    return headers


def merge_auth_headers(headers: dict[str, str], auth: AuthOptions) -> dict[str, str]:
    auth_headers = build_auth_headers(auth)
    return {**auth_headers, **headers}
