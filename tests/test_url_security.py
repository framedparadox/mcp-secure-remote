"""Unit tests for mcp_secure_remote.url_security."""
import pytest

from mcp_secure_remote.url_security import UrlSecurityOptions, validate_remote_url


class TestValidateRemoteUrl:
    def test_public_host_allowed(self):
        validate_remote_url("https://example.com/mcp", UrlSecurityOptions())

    def test_localhost_blocked_by_default(self):
        with pytest.raises(ValueError, match="private or restricted host"):
            validate_remote_url("https://localhost/mcp", UrlSecurityOptions())

    def test_loopback_ip_blocked_by_default(self):
        with pytest.raises(ValueError, match="private or restricted host"):
            validate_remote_url("https://127.0.0.1:8443/mcp", UrlSecurityOptions())

    def test_private_ip_blocked_by_default(self):
        with pytest.raises(ValueError, match="private or restricted host"):
            validate_remote_url("https://10.0.0.5/mcp", UrlSecurityOptions())

    def test_metadata_ip_blocked_by_default(self):
        with pytest.raises(ValueError, match="private or restricted host"):
            validate_remote_url("https://169.254.169.254/latest/meta-data", UrlSecurityOptions())

    def test_allow_private_urls_permits_loopback(self):
        validate_remote_url(
            "https://127.0.0.1:8443/mcp",
            UrlSecurityOptions(allow_private_urls=True),
        )
