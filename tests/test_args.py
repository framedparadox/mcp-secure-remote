"""Unit tests for mcp_secure_remote.args."""
import os
from unittest.mock import patch

import pytest

from mcp_secure_remote.args import (
    VALID_TRANSPORTS,
    ParsedArgs,
    _validate_http_header,
    parse_args,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Clear all MCP_REMOTE_TLS_* env vars so CI environment doesn't bleed into tests.
_TLS_ENV_VARS = [
    "MCP_REMOTE_TLS_CERT",
    "MCP_REMOTE_TLS_KEY",
    "MCP_REMOTE_TLS_CA",
    "MCP_REMOTE_TLS_PASSPHRASE",
    "MCP_REMOTE_TLS_PFX",
    "MCP_REMOTE_TLS_SERVERNAME",
    "MCP_REMOTE_TLS_MIN_VERSION",
    "MCP_REMOTE_TLS_INSECURE",
]


@pytest.fixture(autouse=True)
def clean_tls_env():
    """Remove MCP_REMOTE_TLS_* env vars for the duration of each test."""
    overrides = {k: "" for k in _TLS_ENV_VARS}
    with patch.dict(os.environ, overrides):
        yield


# ---------------------------------------------------------------------------
# _validate_http_header
# ---------------------------------------------------------------------------


class TestValidateHttpHeader:
    def test_valid_simple_name(self):
        _validate_http_header("Authorization", "Bearer token")  # must not raise

    def test_valid_x_prefixed_name(self):
        _validate_http_header("X-Custom-Header", "value")

    def test_valid_rfc_special_chars_in_name(self):
        _validate_http_header("X-Header!#$%&'*+-.^_`|~", "value")

    def test_name_with_space_raises(self):
        with pytest.raises(ValueError, match="Invalid header name"):
            _validate_http_header("Bad Name", "value")

    def test_name_with_colon_raises(self):
        with pytest.raises(ValueError, match="Invalid header name"):
            _validate_http_header("Bad:Name", "value")

    def test_name_with_at_sign_raises(self):
        with pytest.raises(ValueError, match="Invalid header name"):
            _validate_http_header("Bad@Name", "value")

    def test_value_with_cr_raises(self):
        with pytest.raises(ValueError, match="must not contain CR, LF, or NUL"):
            _validate_http_header("X-H", "val\r\ninjected")

    def test_value_with_lf_raises(self):
        with pytest.raises(ValueError, match="must not contain CR, LF, or NUL"):
            _validate_http_header("X-H", "val\ninjected")

    def test_value_with_nul_raises(self):
        with pytest.raises(ValueError, match="must not contain CR, LF, or NUL"):
            _validate_http_header("X-H", "val\x00injected")

    def test_value_with_unicode_is_allowed(self):
        _validate_http_header("X-Unicode", "ñ-value")  # must not raise


# ---------------------------------------------------------------------------
# parse_args — positional argument / URL validation
# ---------------------------------------------------------------------------


class TestParseArgsUrl:
    def test_basic_https_url(self):
        result = parse_args(["https://example.com"])
        assert result.server_url == "https://example.com"

    def test_https_url_with_path(self):
        result = parse_args(["https://example.com/mcp"])
        assert result.server_url == "https://example.com/mcp"

    def test_missing_url_raises(self):
        with pytest.raises((ValueError, SystemExit)):
            parse_args([])

    def test_invalid_url_no_scheme_raises(self):
        with pytest.raises(ValueError, match="Invalid server URL"):
            parse_args(["notaurl"])

    def test_invalid_url_no_netloc_raises(self):
        with pytest.raises(ValueError, match="Invalid server URL"):
            parse_args(["https://"])

    def test_ftp_scheme_raises(self):
        with pytest.raises(ValueError, match="Server URL must use http"):
            parse_args(["ftp://example.com"])

    def test_ws_scheme_raises(self):
        with pytest.raises(ValueError, match="Server URL must use http"):
            parse_args(["ws://example.com"])

    def test_embedded_credentials_raises(self):
        with pytest.raises(ValueError, match="must not contain embedded credentials"):
            parse_args(["https://user:pass@example.com"])

    def test_embedded_username_only_raises(self):
        with pytest.raises(ValueError, match="must not contain embedded credentials"):
            parse_args(["https://user@example.com"])

    def test_http_without_allow_http_raises(self):
        with pytest.raises(ValueError, match="Refusing to use http://"):
            parse_args(["http://example.com"])

    def test_http_with_allow_http_succeeds(self):
        result = parse_args(["http://example.com", "--allow-http"])
        assert result.server_url == "http://example.com"
        assert result.allow_http is True

    def test_duplicate_positional_raises(self):
        with pytest.raises(ValueError, match="Unexpected positional argument"):
            parse_args(["https://example.com", "https://other.com"])


# ---------------------------------------------------------------------------
# parse_args — default values
# ---------------------------------------------------------------------------


class TestParseArgsDefaults:
    def test_default_transport_strategy(self):
        result = parse_args(["https://example.com"])
        assert result.transport_strategy == "http-first"

    def test_default_debug_false(self):
        result = parse_args(["https://example.com"])
        assert result.debug is False

    def test_default_allow_http_false(self):
        result = parse_args(["https://example.com"])
        assert result.allow_http is False

    def test_default_headers_empty(self):
        result = parse_args(["https://example.com"])
        assert result.headers == {}

    def test_default_mtls_reject_unauthorized_true(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.reject_unauthorized is True

    def test_returns_parsed_args_instance(self):
        assert isinstance(parse_args(["https://example.com"]), ParsedArgs)


# ---------------------------------------------------------------------------
# parse_args — flags
# ---------------------------------------------------------------------------


class TestParseArgsFlags:
    def test_debug_flag(self):
        result = parse_args(["https://example.com", "--debug"])
        assert result.debug is True

    def test_allow_http_flag(self):
        result = parse_args(["https://example.com", "--allow-http"])
        assert result.allow_http is True

    def test_unknown_flag_raises(self):
        with pytest.raises(ValueError, match="Unknown flag"):
            parse_args(["https://example.com", "--nonexistent"])

    def test_flag_missing_value_raises(self):
        with pytest.raises(ValueError, match="Missing value for --header"):
            parse_args(["https://example.com", "--header"])

    def test_transport_missing_value_raises(self):
        with pytest.raises(ValueError, match="Missing value for --transport"):
            parse_args(["https://example.com", "--transport"])


# ---------------------------------------------------------------------------
# parse_args — --header
# ---------------------------------------------------------------------------


class TestParseArgsHeader:
    def test_single_header_parsed(self):
        result = parse_args(["https://example.com", "--header", "Authorization: Bearer tok"])
        assert result.headers["Authorization"] == "Bearer tok"

    def test_header_value_trimmed(self):
        result = parse_args(["https://example.com", "--header", "X-H:  val  "])
        assert result.headers["X-H"] == "val"

    def test_multiple_headers(self):
        result = parse_args([
            "https://example.com",
            "--header", "X-A: first",
            "--header", "X-B: second",
        ])
        assert result.headers["X-A"] == "first"
        assert result.headers["X-B"] == "second"

    def test_header_value_with_colon(self):
        result = parse_args(["https://example.com", "--header", "X-H: val:with:colons"])
        assert result.headers["X-H"] == "val:with:colons"

    def test_header_missing_colon_raises(self):
        with pytest.raises(ValueError, match='--header expects "Name: value"'):
            parse_args(["https://example.com", "--header", "NoColon"])

    def test_header_empty_name_raises(self):
        with pytest.raises(ValueError, match="--header has empty name"):
            parse_args(["https://example.com", "--header", ": value"])

    def test_header_crlf_injection_raises(self):
        with pytest.raises(ValueError):
            parse_args(["https://example.com", "--header", "X-H: val\r\ninjected"])


# ---------------------------------------------------------------------------
# parse_args — --transport
# ---------------------------------------------------------------------------


class TestParseArgsTransport:
    @pytest.mark.parametrize("strategy", VALID_TRANSPORTS)
    def test_all_valid_transport_values(self, strategy):
        result = parse_args(["https://example.com", "--transport", strategy])
        assert result.transport_strategy == strategy

    def test_invalid_transport_raises(self):
        with pytest.raises(ValueError, match="--transport must be one of"):
            parse_args(["https://example.com", "--transport", "grpc"])


# ---------------------------------------------------------------------------
# parse_args — TLS/mTLS flags
# ---------------------------------------------------------------------------


class TestParseArgsTlsFlags:
    def test_tls_cert(self):
        result = parse_args(["https://example.com", "--tls-cert", "/c.pem"])
        assert result.mtls.cert_path == "/c.pem"

    def test_tls_key(self):
        result = parse_args(["https://example.com", "--tls-key", "/k.pem"])
        assert result.mtls.key_path == "/k.pem"

    def test_tls_cert_and_key_together(self):
        result = parse_args([
            "https://example.com",
            "--tls-cert", "/c.pem",
            "--tls-key", "/k.pem",
        ])
        assert result.mtls.cert_path == "/c.pem"
        assert result.mtls.key_path == "/k.pem"

    def test_tls_ca(self):
        result = parse_args(["https://example.com", "--tls-ca", "/ca.pem"])
        assert result.mtls.ca_path == "/ca.pem"

    def test_tls_passphrase(self):
        result = parse_args(["https://example.com", "--tls-passphrase", "s3cr3t"])
        assert result.mtls.passphrase == "s3cr3t"

    def test_tls_pfx(self):
        result = parse_args(["https://example.com", "--tls-pfx", "/c.pfx"])
        assert result.mtls.pfx_path == "/c.pfx"

    def test_tls_servername(self):
        result = parse_args(["https://example.com", "--tls-servername", "override.host"])
        assert result.mtls.servername == "override.host"

    def test_tls_min_version_tls13(self):
        result = parse_args(["https://example.com", "--tls-min-version", "TLSv1.3"])
        assert result.mtls.min_version == "TLSv1.3"

    def test_tls_min_version_tls12(self):
        result = parse_args(["https://example.com", "--tls-min-version", "TLSv1.2"])
        assert result.mtls.min_version == "TLSv1.2"

    def test_tls_min_version_invalid_raises(self):
        with pytest.raises(ValueError, match="--tls-min-version must be"):
            parse_args(["https://example.com", "--tls-min-version", "TLSv1.1"])

    def test_tls_insecure_skip_verify(self):
        result = parse_args(["https://example.com", "--tls-insecure-skip-verify"])
        assert result.mtls.reject_unauthorized is False

    def test_tls_no_verify_alias(self):
        result = parse_args(["https://example.com", "--tls-no-verify"])
        assert result.mtls.reject_unauthorized is False


# ---------------------------------------------------------------------------
# parse_args — environment variables
# ---------------------------------------------------------------------------


class TestParseArgsEnvVars:
    @patch.dict(os.environ, {"MCP_REMOTE_TLS_CERT": "/env/cert.pem"})
    def test_env_cert(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.cert_path == "/env/cert.pem"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_KEY": "/env/key.pem"})
    def test_env_key(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.key_path == "/env/key.pem"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_CA": "/env/ca.pem"})
    def test_env_ca(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.ca_path == "/env/ca.pem"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_PASSPHRASE": "env-secret"})
    def test_env_passphrase(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.passphrase == "env-secret"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_PFX": "/env/client.pfx"})
    def test_env_pfx(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.pfx_path == "/env/client.pfx"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_SERVERNAME": "env.override.host"})
    def test_env_servername(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.servername == "env.override.host"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_MIN_VERSION": "TLSv1.3"})
    def test_env_min_version_tls13(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.min_version == "TLSv1.3"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_MIN_VERSION": "TLSv1.2"})
    def test_env_min_version_tls12(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.min_version == "TLSv1.2"

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_MIN_VERSION": "TLSv1.1"})
    def test_env_min_version_invalid_raises(self):
        with pytest.raises(ValueError, match="MCP_REMOTE_TLS_MIN_VERSION"):
            parse_args(["https://example.com"])

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_INSECURE": "true"})
    def test_env_insecure_true(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.reject_unauthorized is False

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_INSECURE": "1"})
    def test_env_insecure_one(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.reject_unauthorized is False

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_INSECURE": "yes"})
    def test_env_insecure_yes(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.reject_unauthorized is False

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_INSECURE": "false"})
    def test_env_insecure_false_not_applied(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.reject_unauthorized is True

    @patch.dict(os.environ, {"MCP_REMOTE_TLS_INSECURE": "0"})
    def test_env_insecure_zero_not_applied(self):
        result = parse_args(["https://example.com"])
        assert result.mtls.reject_unauthorized is True

    def test_empty_env_var_treated_as_none(self):
        with patch.dict(os.environ, {"MCP_REMOTE_TLS_CERT": ""}):
            result = parse_args(["https://example.com"])
            assert result.mtls.cert_path is None
