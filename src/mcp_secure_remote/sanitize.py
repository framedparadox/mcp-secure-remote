"""Security utilities: sanitize text for safe terminal/log output."""
from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

# CSI sequences (e.g. \x1b[31m), OSC sequences, two-char ESC, 8-bit CSI
_ANSI_ESCAPE_RE = re.compile(
    r"(?:"
    r"\x1b\[[0-9;]*[A-Za-z]"           # CSI sequences
    r"|\x1b\][^\x07]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|\x1b[A-Z]"                       # two-char ESC sequences
    r"|\x9b[0-9;]*[A-Za-z]"            # 8-bit CSI
    r")"
)
# Control chars except TAB (\x09); LF is stripped to prevent log-line injection
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def sanitize_terminal_text(text: object) -> str:
    """Strip ANSI escape sequences and control characters from *text*.

    Prevents a malicious remote server from injecting terminal escape sequences
    (cursor movement, colour, OSC title-set, etc.) or raw control characters
    into the terminal via tool/resource/prompt names returned from the server.

    Preserves printable ASCII, Unicode, TAB, and LF.
    """
    s = text if isinstance(text, str) else str(text)
    s = _ANSI_ESCAPE_RE.sub("", s)
    s = _CONTROL_CHARS_RE.sub("", s)
    return s


def sanitize_server_url_for_log(server_url: str) -> str:
    """Return *server_url* with any embedded userinfo (credentials) removed.

    A URL such as ``https://user:pass@host/path`` becomes
    ``https://host/path`` so credentials are never written to logs.
    """
    try:
        p = urlparse(server_url)
        # Reconstruct netloc without userinfo
        netloc = p.hostname or ""
        if p.port:
            netloc = f"{netloc}:{p.port}"
        return urlunparse(p._replace(netloc=netloc))
    except Exception:
        return "<invalid-url>"


def sanitize_parsed_args_for_log(parsed: object) -> dict:
    """Return a safe dict of *ParsedArgs* fields suitable for debug logging.

    - Header *values* are redacted; only header *names* are emitted.
    - The server URL has embedded credentials stripped.
    - The mTLS passphrase is redacted.
    """
    mtls = parsed.mtls  # type: ignore[attr-defined]
    return {
        "server_url": sanitize_server_url_for_log(parsed.server_url),  # type: ignore[attr-defined]
        "transport_strategy": parsed.transport_strategy,  # type: ignore[attr-defined]
        "allow_http": parsed.allow_http,  # type: ignore[attr-defined]
        "headers": list(parsed.headers.keys()),  # names only, never values  # type: ignore[attr-defined]
        "mtls": {
            "cert_path": mtls.cert_path,
            "key_path": mtls.key_path,
            "ca_path": mtls.ca_path,
            "pfx_path": mtls.pfx_path,
            "servername": mtls.servername,
            "min_version": mtls.min_version,
            "reject_unauthorized": mtls.reject_unauthorized,
            "passphrase": "***" if mtls.passphrase else None,
        },
    }


def summarize_message(message: object) -> dict:
    """Return a lightweight, non-sensitive summary of an MCP JSON-RPC message.

    Avoids logging arbitrary server-supplied content (tool results, resource
    data, etc.) which may contain sensitive information.  Only structural
    metadata — message kind, id, method name, and presence of payload fields —
    is included.
    """
    if isinstance(message, list):
        return {
            "kind": "batch",
            "count": len(message),
            "entries": [_summarize_single(m) for m in message[:5]],
            "truncated": len(message) > 5,
        }
    return _summarize_single(message)


def _summarize_single(message: object) -> dict:
    if not isinstance(message, dict):
        return {"kind": type(message).__name__}

    msg_id = message.get("id")
    method = message.get("method")
    error = message.get("error")
    error_code = error.get("code") if isinstance(error, dict) else None

    return {
        "kind": _message_kind(message),
        "id": msg_id if isinstance(msg_id, (str, int, type(None))) else None,
        "method": method if isinstance(method, str) else None,
        "has_params": "params" in message,
        "has_result": "result" in message,
        "has_error": "error" in message,
        "error_code": error_code,
    }


def _message_kind(message: dict) -> str:
    if "error" in message:
        return "error"
    if "result" in message:
        return "response"
    if isinstance(message.get("method"), str) and "id" in message:
        return "request"
    if isinstance(message.get("method"), str):
        return "notification"
    return "unknown"
