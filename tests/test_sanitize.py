"""Unit tests for mcp_secure_remote.sanitize."""
from unittest.mock import MagicMock

import pytest

from mcp_secure_remote.sanitize import (
    _message_kind,
    _summarize_single,
    sanitize_parsed_args_for_log,
    sanitize_server_url_for_log,
    sanitize_terminal_text,
    summarize_message,
)


class TestSanitizeTerminalText:
    def test_plain_string_unchanged(self):
        assert sanitize_terminal_text("hello world") == "hello world"

    def test_unicode_preserved(self):
        assert sanitize_terminal_text("café résumé") == "café résumé"

    def test_strips_csi_colour_sequence(self):
        assert sanitize_terminal_text("\x1b[31mred\x1b[0m") == "red"

    def test_strips_csi_with_multiple_params(self):
        assert sanitize_terminal_text("\x1b[1;32mbold green\x1b[0m") == "bold green"

    def test_strips_osc_title_sequence_bell_terminated(self):
        assert sanitize_terminal_text("\x1b]0;title\x07rest") == "rest"

    def test_strips_osc_sequence_st_terminated(self):
        assert sanitize_terminal_text("\x1b]0;title\x1b\\rest") == "rest"

    def test_strips_two_char_esc_sequence(self):
        assert sanitize_terminal_text("\x1bAtext") == "text"

    def test_strips_8bit_csi(self):
        assert sanitize_terminal_text("\x9b31mred") == "red"

    def test_strips_nul_character(self):
        assert sanitize_terminal_text("a\x00b") == "ab"

    def test_strips_lf(self):
        # LF (\x0a) is a control character — stripped to prevent log-line injection
        assert sanitize_terminal_text("a\nb") == "ab"

    def test_strips_cr(self):
        assert sanitize_terminal_text("a\rb") == "ab"

    def test_preserves_tab(self):
        # TAB (\x09) must be preserved per the spec
        assert sanitize_terminal_text("col1\tcol2") == "col1\tcol2"

    def test_non_string_int_converted(self):
        assert sanitize_terminal_text(42) == "42"

    def test_non_string_none_converted(self):
        assert sanitize_terminal_text(None) == "None"

    def test_empty_string(self):
        assert sanitize_terminal_text("") == ""

    def test_only_ansi_sequence_becomes_empty(self):
        assert sanitize_terminal_text("\x1b[31m") == ""


class TestSanitizeServerUrlForLog:
    def test_plain_url_unchanged(self):
        url = "https://example.com/path"
        assert sanitize_server_url_for_log(url) == "https://example.com/path"

    def test_strips_username_and_password(self):
        result = sanitize_server_url_for_log("https://user:pass@example.com/path")
        assert "user" not in result
        assert "pass" not in result
        assert "example.com" in result

    def test_strips_username_only(self):
        result = sanitize_server_url_for_log("https://user@example.com")
        assert "user" not in result
        assert "example.com" in result

    def test_preserves_port(self):
        result = sanitize_server_url_for_log("https://example.com:8443/api")
        assert "8443" in result
        assert "example.com" in result

    def test_preserves_path(self):
        result = sanitize_server_url_for_log("https://example.com/some/path")
        assert "/some/path" in result

    def test_preserves_query(self):
        result = sanitize_server_url_for_log("https://example.com/p?key=val")
        assert "key=val" in result

    def test_http_scheme(self):
        result = sanitize_server_url_for_log("http://localhost:8080")
        assert result.startswith("http://")
        assert "8080" in result


class TestSanitizeParsedArgsForLog:
    def _make_parsed(self, **kwargs):
        parsed = MagicMock()
        parsed.server_url = kwargs.get("server_url", "https://example.com")
        parsed.transport_strategy = kwargs.get("transport_strategy", "http-first")
        parsed.allow_http = kwargs.get("allow_http", False)
        parsed.headers = kwargs.get("headers", {})
        mtls = MagicMock()
        mtls.cert_path = kwargs.get("cert_path", None)
        mtls.key_path = kwargs.get("key_path", None)
        mtls.ca_path = kwargs.get("ca_path", None)
        mtls.pfx_path = kwargs.get("pfx_path", None)
        mtls.servername = kwargs.get("servername", None)
        mtls.min_version = kwargs.get("min_version", None)
        mtls.reject_unauthorized = kwargs.get("reject_unauthorized", True)
        mtls.passphrase = kwargs.get("passphrase", None)
        parsed.mtls = mtls
        return parsed

    def test_header_values_not_included(self):
        parsed = self._make_parsed(headers={"Authorization": "Bearer secret"})
        result = sanitize_parsed_args_for_log(parsed)
        assert "Bearer secret" not in str(result)

    def test_header_names_are_included(self):
        parsed = self._make_parsed(headers={"Authorization": "Bearer secret", "X-Api-Key": "xyz"})
        result = sanitize_parsed_args_for_log(parsed)
        assert "Authorization" in result["headers"]
        assert "X-Api-Key" in result["headers"]

    def test_passphrase_is_redacted(self):
        parsed = self._make_parsed(passphrase="my-secret-phrase")
        result = sanitize_parsed_args_for_log(parsed)
        assert result["mtls"]["passphrase"] == "***"

    def test_no_passphrase_is_none(self):
        parsed = self._make_parsed(passphrase=None)
        result = sanitize_parsed_args_for_log(parsed)
        assert result["mtls"]["passphrase"] is None

    def test_server_url_credentials_stripped(self):
        parsed = self._make_parsed(server_url="https://user:pass@example.com")
        result = sanitize_parsed_args_for_log(parsed)
        assert "pass" not in result["server_url"]

    def test_transport_strategy_present(self):
        parsed = self._make_parsed(transport_strategy="sse-only")
        result = sanitize_parsed_args_for_log(parsed)
        assert result["transport_strategy"] == "sse-only"

    def test_allow_http_present(self):
        parsed = self._make_parsed(allow_http=True)
        result = sanitize_parsed_args_for_log(parsed)
        assert result["allow_http"] is True

    def test_mtls_cert_path_exposed(self):
        parsed = self._make_parsed(cert_path="/etc/certs/client.pem")
        result = sanitize_parsed_args_for_log(parsed)
        assert result["mtls"]["cert_path"] == "/etc/certs/client.pem"

    def test_mtls_reject_unauthorized_exposed(self):
        parsed = self._make_parsed(reject_unauthorized=False)
        result = sanitize_parsed_args_for_log(parsed)
        assert result["mtls"]["reject_unauthorized"] is False


class TestSummarizeMessage:
    def test_single_request_message(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        result = summarize_message(msg)
        assert result["kind"] == "request"
        assert result["id"] == 1
        assert result["method"] == "tools/list"
        assert result["has_params"] is True

    def test_single_response_message(self):
        msg = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        result = summarize_message(msg)
        assert result["kind"] == "response"
        assert result["has_result"] is True
        assert result["has_params"] is False

    def test_single_error_message(self):
        msg = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32600, "message": "Invalid Request"}}
        result = summarize_message(msg)
        assert result["kind"] == "error"
        assert result["has_error"] is True
        assert result["error_code"] == -32600

    def test_single_notification_message(self):
        msg = {"jsonrpc": "2.0", "method": "notifications/message"}
        result = summarize_message(msg)
        assert result["kind"] == "notification"
        assert result["id"] is None

    def test_batch_message(self):
        msgs = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(3)]
        result = summarize_message(msgs)
        assert result["kind"] == "batch"
        assert result["count"] == 3
        assert result["truncated"] is False

    def test_batch_truncated_at_5(self):
        msgs = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(10)]
        result = summarize_message(msgs)
        assert result["kind"] == "batch"
        assert result["count"] == 10
        assert result["truncated"] is True
        assert len(result["entries"]) == 5

    def test_batch_exactly_5_not_truncated(self):
        msgs = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(5)]
        result = summarize_message(msgs)
        assert result["truncated"] is False

    def test_non_dict_single_message(self):
        result = summarize_message("raw string")
        assert result["kind"] == "str"

    def test_id_string_preserved(self):
        msg = {"jsonrpc": "2.0", "id": "req-abc", "method": "ping"}
        result = summarize_message(msg)
        assert result["id"] == "req-abc"

    def test_id_none_preserved(self):
        msg = {"jsonrpc": "2.0", "method": "notify", "id": None}
        result = summarize_message(msg)
        assert result["id"] is None

    def test_unwraps_session_message_wrapper(self):
        from mcp.shared.message import SessionMessage
        import mcp.types as t
        inner = t.JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}})
        wrapped = SessionMessage(message=inner)
        result = summarize_message(wrapped)
        assert result["kind"] == "request"
        assert result["id"] == 7
        assert result["method"] == "tools/list"

    def test_unwraps_pydantic_jsonrpc_message(self):
        import mcp.types as t
        m = t.JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": 3, "method": "ping"})
        result = summarize_message(m)
        assert result["kind"] == "request"
        assert result["method"] == "ping"

    def test_exception_payload_is_marked(self):
        result = summarize_message(ValueError("bad json"))
        assert result["kind"] == "exception"
        assert result["exc_type"] == "ValueError"


class TestMessageKind:
    def test_request_has_method_and_id(self):
        assert _message_kind({"id": 1, "method": "test"}) == "request"

    def test_notification_has_method_no_id(self):
        assert _message_kind({"method": "notify"}) == "notification"

    def test_response_has_result(self):
        assert _message_kind({"id": 1, "result": {}}) == "response"

    def test_error_has_error_key(self):
        assert _message_kind({"id": 1, "error": {}}) == "error"

    def test_error_takes_precedence_over_result(self):
        # error check comes first in the function
        assert _message_kind({"id": 1, "error": {}, "result": {}}) == "error"

    def test_unknown_empty_dict(self):
        assert _message_kind({}) == "unknown"

    def test_method_non_string_is_unknown(self):
        assert _message_kind({"method": 42}) == "unknown"


class TestSummarizeSingle:
    def test_non_dict_returns_type_name(self):
        result = _summarize_single(123)
        assert result["kind"] == "int"

    def test_none_returns_type_name(self):
        result = _summarize_single(None)
        assert result["kind"] == "NoneType"

    def test_error_code_extracted(self):
        msg = {"error": {"code": -32700, "message": "Parse error"}}
        result = _summarize_single(msg)
        assert result["error_code"] == -32700

    def test_error_code_none_when_error_not_dict(self):
        msg = {"error": "simple string error"}
        result = _summarize_single(msg)
        assert result["error_code"] is None
