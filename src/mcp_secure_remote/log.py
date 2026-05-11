"""Logging to stderr — keeps stdout clean for the MCP JSON-RPC channel."""
import sys
import json
from datetime import datetime, timezone

try:
    BaseExceptionGroup
except NameError:
    from exceptiongroup import BaseExceptionGroup

_debug_enabled = False


def flatten_exception(exc: BaseException) -> BaseException:
    """Return the deepest non-group leaf exception inside *exc*.

    ``anyio`` wraps task-group failures in ``BaseExceptionGroup``; the wrapper
    message ("unhandled errors in a TaskGroup (1 sub-exception)") hides the
    underlying error. Unwrap it so callers can act on the real exception.
    """
    seen: set[int] = set()
    cur: BaseException = exc
    while isinstance(cur, BaseExceptionGroup) and cur.exceptions:
        if id(cur) in seen:
            break
        seen.add(id(cur))
        cur = cur.exceptions[0]
    return cur


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
