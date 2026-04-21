"""Logging to stderr — keeps stdout clean for the MCP JSON-RPC channel."""
import sys
import json
from datetime import datetime, timezone

_debug_enabled = False


def set_debug(enabled: bool) -> None:
    global _debug_enabled
    _debug_enabled = enabled


def is_debug() -> bool:
    return _debug_enabled


def log(message: str, *rest: object) -> None:
    prefix = f"[mcp-secure-remote {datetime.now(timezone.utc).isoformat()}]"
    if rest:
        parts = " ".join(_serialize(v) for v in rest)
        sys.stderr.write(f"{prefix} {message} {parts}\n")
    else:
        sys.stderr.write(f"{prefix} {message}\n")
    sys.stderr.flush()


def debug_log(message: str, *rest: object) -> None:
    if not _debug_enabled:
        return
    log(f"[debug] {message}", *rest)


def _serialize(value: object) -> str:
    if isinstance(value, Exception):
        return str(value)
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except Exception:
        return str(value)
