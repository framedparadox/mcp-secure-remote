"""JSON-RPC message size limits for the stdio proxy."""
from __future__ import annotations

import json

DEFAULT_MAX_MESSAGE_BYTES = 10 * 1024 * 1024
_MAX_MESSAGE_BYTES_FLOOR = 1024
_MAX_MESSAGE_BYTES_CEILING = 256 * 1024 * 1024


def parse_max_message_bytes(raw: str, flag: str) -> int:
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise ValueError(f"{flag} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{flag} must be a positive integer")
    if value < _MAX_MESSAGE_BYTES_FLOOR:
        raise ValueError(f"{flag} must be at least {_MAX_MESSAGE_BYTES_FLOOR} bytes")
    if value > _MAX_MESSAGE_BYTES_CEILING:
        raise ValueError(f"{flag} must not exceed {_MAX_MESSAGE_BYTES_CEILING} bytes")
    return value


def message_byte_length(message: object) -> int:
    if isinstance(message, Exception):
        return 0
    return len(json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def is_within_message_limit(message: object, max_bytes: int) -> bool:
    return message_byte_length(message) <= max_bytes
