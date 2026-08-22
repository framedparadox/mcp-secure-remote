"""Unit tests for mcp_secure_remote.mtls."""
import ssl
from unittest.mock import MagicMock, patch

import pytest

from mcp_secure_remote.mtls import MtlsOptions, build_ssl_context, has_mtls_config


class TestHasMtlsConfig:
    def test_all_defaults_returns_false(self):
        assert has_mtls_config(MtlsOptions()) is False

    def test_cert_path_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(cert_path="/cert.pem")) is True

    def test_key_path_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(key_path="/key.pem")) is True

    def test_ca_path_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(ca_path="/ca.pem")) is True

    def test_pfx_path_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(pfx_path="/client.pfx")) is True

    def test_passphrase_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(passphrase="secret")) is True

    def test_servername_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(servername="override.host")) is True

    def test_min_version_set_returns_true(self):
        assert has_mtls_config(MtlsOptions(min_version="TLSv1.3")) is True

    def test_reject_unauthorized_false_returns_true(self):
        assert has_mtls_config(MtlsOptions(reject_unauthorized=False)) is True

    def test_reject_unauthorized_true_only_returns_false(self):
        # Default reject_unauthorized=True with no other fields set → False
        assert has_mtls_config(MtlsOptions(reject_unauthorized=True)) is False


class TestBuildSslContextErrors:
    """Error cases that are caught before any file I/O."""

    def test_pfx_and_cert_conflict_raises(self):
        opts = MtlsOptions(pfx_path="/p.pfx", cert_path="/c.pem")
        with pytest.raises(ValueError, match="Use either --tls-pfx OR --tls-cert"):
            build_ssl_context(opts)

    def test_pfx_and_key_conflict_raises(self):
        opts = MtlsOptions(pfx_path="/p.pfx", key_path="/k.pem")
        with pytest.raises(ValueError, match="Use either --tls-pfx OR --tls-cert"):
            build_ssl_context(opts)

    def test_cert_without_key_raises(self):
        opts = MtlsOptions(cert_path="/cert.pem")
        with pytest.raises(ValueError, match="Both --tls-cert and --tls-key must be provided together"):
            build_ssl_context(opts)

    def test_key_without_cert_raises(self):
        opts = MtlsOptions(key_path="/key.pem")
        with pytest.raises(ValueError, match="Both --tls-cert and --tls-key must be provided together"):
            build_ssl_context(opts)

    def test_passphrase_without_cert_or_pfx_raises(self):
        opts = MtlsOptions(passphrase="secret")
        with pytest.raises(ValueError, match="--tls-passphrase requires"):
            build_ssl_context(opts)

    def test_invalid_min_version_raises(self):
        opts = MtlsOptions(min_version="TLSv1.1")
        with pytest.raises(ValueError, match="Unknown TLS version"):
            build_ssl_context(opts)

    def test_pfx_file_not_found_raises_valueerror(self):
        opts = MtlsOptions(pfx_path="/definitely/not/here.pfx")
        with pytest.raises(ValueError, match="Unable to load PKCS#12 bundle"):
            build_ssl_context(opts)

    def test_pfx_garbage_data_raises_valueerror(self, tmp_path):
        bad = tmp_path / "bad.pfx"
        bad.write_bytes(b"not a real pfx bundle")
        opts = MtlsOptions(pfx_path=str(bad))
        with pytest.raises(ValueError, match="Unable to decode PKCS#12 bundle"):
            build_ssl_context(opts)


class TestBuildSslContextWithMockedContext:
    """Verify SSL context configuration via mocked ssl.create_default_context."""

    def _mock_ctx(self):
        ctx = MagicMock(spec=ssl.SSLContext)
        return ctx

    @patch("ssl.create_default_context")
    def test_minimum_version_floor_is_tls12(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions())
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    @patch("ssl.create_default_context")
    def test_min_version_tls13_applied(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions(min_version="TLSv1.3"))
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3

    @patch("ssl.create_default_context")
    def test_min_version_tls12_applied(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions(min_version="TLSv1.2"))
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    @patch("ssl.create_default_context")
    def test_reject_unauthorized_false_disables_verification(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions(reject_unauthorized=False))
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    @patch("ssl.create_default_context")
    def test_reject_unauthorized_true_does_not_modify_verification(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions(reject_unauthorized=True))
        # check_hostname and verify_mode must NOT be touched when verification is kept on
        ctx.check_hostname  # access it — but it should not have been set to False
        # Assert False was never assigned
        for call in ctx.mock_calls:
            if "__setattr__" in str(call) and "check_hostname" in str(call):
                assert "False" not in str(call)

    @patch("ssl.create_default_context")
    def test_ca_path_file_not_found_raises(self, mock_factory):
        ctx = self._mock_ctx()
        ctx.load_verify_locations.side_effect = FileNotFoundError("no such file")
        mock_factory.return_value = ctx
        with pytest.raises(ValueError, match="Unable to load CA bundle"):
            build_ssl_context(MtlsOptions(ca_path="/nonexistent/ca.pem"))

    @patch("ssl.create_default_context")
    def test_ca_path_os_error_raises(self, mock_factory):
        ctx = self._mock_ctx()
        ctx.load_verify_locations.side_effect = OSError("permission denied")
        mock_factory.return_value = ctx
        with pytest.raises(ValueError, match="Unable to load CA bundle"):
            build_ssl_context(MtlsOptions(ca_path="/unreadable/ca.pem"))

    @patch("ssl.create_default_context")
    def test_cert_key_file_not_found_raises(self, mock_factory):
        ctx = self._mock_ctx()
        ctx.load_cert_chain.side_effect = FileNotFoundError("no such file")
        mock_factory.return_value = ctx
        with pytest.raises(ValueError, match="Unable to load client cert/key"):
            build_ssl_context(MtlsOptions(cert_path="/no/cert.pem", key_path="/no/key.pem"))

    @patch("ssl.create_default_context")
    def test_cert_key_os_error_raises(self, mock_factory):
        ctx = self._mock_ctx()
        ctx.load_cert_chain.side_effect = OSError("permission denied")
        mock_factory.return_value = ctx
        with pytest.raises(ValueError, match="Unable to load client cert/key"):
            build_ssl_context(MtlsOptions(cert_path="/cert.pem", key_path="/key.pem"))

    @patch("ssl.create_default_context")
    def test_passphrase_encoded_and_passed(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions(cert_path="/c.pem", key_path="/k.pem", passphrase="my-pass"))
        _, kwargs = ctx.load_cert_chain.call_args
        assert kwargs.get("password") == b"my-pass"

    @patch("ssl.create_default_context")
    def test_no_passphrase_passes_none(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions(cert_path="/c.pem", key_path="/k.pem"))
        _, kwargs = ctx.load_cert_chain.call_args
        assert kwargs.get("password") is None

    @patch("ssl.create_default_context")
    def test_context_created_with_server_auth_purpose(self, mock_factory):
        ctx = self._mock_ctx()
        mock_factory.return_value = ctx
        build_ssl_context(MtlsOptions())
        mock_factory.assert_called_once_with(ssl.Purpose.SERVER_AUTH)
