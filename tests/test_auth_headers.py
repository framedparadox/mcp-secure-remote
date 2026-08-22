"""Unit tests for mcp_secure_remote.auth_headers."""
import pytest

from mcp_secure_remote.auth_headers import AuthOptions, build_auth_headers, merge_auth_headers


class TestBuildAuthHeaders:
    def test_bearer_header(self):
        headers = build_auth_headers(AuthOptions(bearer="tok"))
        assert headers["Authorization"] == "Bearer tok"

    def test_basic_header(self):
        headers = build_auth_headers(AuthOptions(basic="user:pass"))
        assert headers["Authorization"] == "Basic dXNlcjpwYXNz"

    def test_api_key_default_header(self):
        headers = build_auth_headers(AuthOptions(api_key="secret"))
        assert headers["X-Api-Key"] == "secret"

    def test_api_key_custom_header(self):
        headers = build_auth_headers(AuthOptions(api_key="secret", api_key_header="X-Custom"))
        assert headers["X-Custom"] == "secret"

    def test_bearer_and_basic_conflict(self):
        with pytest.raises(ValueError, match="only one"):
            build_auth_headers(AuthOptions(bearer="tok", basic="u:p"))

    def test_basic_without_colon_raises(self):
        with pytest.raises(ValueError, match="username:password"):
            build_auth_headers(AuthOptions(basic="nocolon"))


class TestMergeAuthHeaders:
    def test_cli_header_overrides_same_auth_header(self):
        merged = merge_auth_headers({"Authorization": "Bearer override"}, AuthOptions(bearer="tok"))
        assert merged["Authorization"] == "Bearer override"

    def test_conflicting_auth_and_header_allows_header_override(self):
        merged = merge_auth_headers({"Authorization": "Bearer other"}, AuthOptions(bearer="tok"))
        assert merged["Authorization"] == "Bearer other"
