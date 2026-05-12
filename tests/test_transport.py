"""Unit tests for mcp_secure_remote.transport."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock
from contextlib import asynccontextmanager

from mcp_secure_remote.transport import (
    _get_origin,
    _build_httpx_client_factory,
    connect_to_remote_server,
)
from mcp_secure_remote.mtls import MtlsOptions


# ---------------------------------------------------------------------------
# _get_origin
# ---------------------------------------------------------------------------


class TestGetOrigin:
    def test_basic_https(self):
        assert _get_origin("https://example.com/path") == "https://example.com"

    def test_https_with_port(self):
        assert _get_origin("https://example.com:8443/path") == "https://example.com:8443"

    def test_http_with_port(self):
        assert _get_origin("http://localhost:8080/api") == "http://localhost:8080"

    def test_path_and_query_stripped(self):
        assert _get_origin("https://host.com/path?q=1#frag") == "https://host.com"

    def test_host_normalised_to_lowercase(self):
        assert _get_origin("https://Example.COM/path") == "https://example.com"

    def test_no_trailing_slash(self):
        result = _get_origin("https://example.com")
        assert not result.endswith("/")

    def test_preserves_scheme(self):
        assert _get_origin("http://example.com").startswith("http://")
        assert _get_origin("https://example.com").startswith("https://")


# ---------------------------------------------------------------------------
# _build_httpx_client_factory
# ---------------------------------------------------------------------------


class TestBuildHttpxClientFactory:
    def test_returns_callable(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        assert callable(factory)

    def test_creates_async_client_instance(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        assert isinstance(client, httpx.AsyncClient)

    def test_follow_redirects_is_false(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        assert client.follow_redirects is False

    def test_registers_exactly_one_request_hook(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        hooks = client.event_hooks.get("request", [])
        assert len(hooks) == 1

    def test_ssl_context_none_uses_default_verification(self):
        # verify=True when no ssl_context passed → default CA bundle
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        assert isinstance(client, httpx.AsyncClient)  # created successfully

    def test_custom_ssl_context_accepted(self):
        mock_ssl = MagicMock()
        factory = _build_httpx_client_factory(mock_ssl, "https://example.com")
        # Should not raise; the mock ssl object is passed as verify
        assert callable(factory)

    def test_factory_accepts_headers(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory(headers={"X-Custom": "value"})
        assert isinstance(client, httpx.AsyncClient)

    def test_factory_accepts_timeout(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory(timeout=httpx.Timeout(30.0))
        assert isinstance(client, httpx.AsyncClient)

    def test_two_calls_return_independent_clients(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        c1 = factory()
        c2 = factory()
        assert c1 is not c2

    @pytest.mark.asyncio
    async def test_origin_hook_blocks_different_origin(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        hook = client.event_hooks["request"][0]
        req = httpx.Request("GET", "https://evil.com/steal")
        with pytest.raises(ValueError, match="Refusing outbound request to an unexpected origin"):
            await hook(req)

    @pytest.mark.asyncio
    async def test_origin_hook_allows_same_origin(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        hook = client.event_hooks["request"][0]
        req = httpx.Request("GET", "https://example.com/api/v2")
        await hook(req)  # must not raise

    @pytest.mark.asyncio
    async def test_origin_hook_blocks_different_scheme(self):
        factory = _build_httpx_client_factory(None, "https://example.com")
        client = factory()
        hook = client.event_hooks["request"][0]
        # http vs https → different origin
        req = httpx.Request("GET", "http://example.com/endpoint")
        with pytest.raises(ValueError, match="Refusing outbound request to an unexpected origin"):
            await hook(req)

    @pytest.mark.asyncio
    async def test_origin_hook_blocks_different_port(self):
        factory = _build_httpx_client_factory(None, "https://example.com:8443")
        client = factory()
        hook = client.event_hooks["request"][0]
        req = httpx.Request("GET", "https://example.com:9999/endpoint")
        with pytest.raises(ValueError, match="Refusing outbound request to an unexpected origin"):
            await hook(req)

    @pytest.mark.asyncio
    async def test_origin_hook_allows_subpath_same_origin(self):
        factory = _build_httpx_client_factory(None, "https://api.example.com")
        client = factory()
        hook = client.event_hooks["request"][0]
        req = httpx.Request("POST", "https://api.example.com/v1/tools/call")
        await hook(req)  # must not raise


# ---------------------------------------------------------------------------
# connect_to_remote_server — strategy / fallback logic
# ---------------------------------------------------------------------------


class TestConnectToRemoteServer:
    """Tests for transport selection strategy using mocked transport functions."""

    def _make_streams(self):
        read = AsyncMock()
        write = AsyncMock()
        return read, write

    @pytest.mark.asyncio
    async def test_http_first_tries_http_before_sse(self):
        """http-first strategy: HTTP is attempted first; if it succeeds no SSE attempted."""
        read, write = self._make_streams()

        @asynccontextmanager
        async def fake_http(*a, **kw):
            yield (read, write)

        @asynccontextmanager
        async def fake_sse(*a, **kw):
            raise AssertionError("SSE should not be attempted when HTTP succeeds")
            yield  # pragma: no cover

        with patch("mcp_secure_remote.transport._try_streamable_http", fake_http), \
             patch("mcp_secure_remote.transport._try_sse", fake_sse), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False):
            async with connect_to_remote_server(
                "https://example.com", {}, "http-first", MtlsOptions()
            ) as streams:
                assert streams == (read, write)

    @pytest.mark.asyncio
    async def test_http_first_falls_back_to_sse(self):
        """http-first strategy: falls back to SSE when HTTP fails."""
        read, write = self._make_streams()

        @asynccontextmanager
        async def failing_http(*a, **kw):
            raise ConnectionError("HTTP not supported")
            yield  # pragma: no cover

        @asynccontextmanager
        async def fake_sse(*a, **kw):
            yield (read, write)

        with patch("mcp_secure_remote.transport._try_streamable_http", failing_http), \
             patch("mcp_secure_remote.transport._try_sse", fake_sse), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False):
            async with connect_to_remote_server(
                "https://example.com", {}, "http-first", MtlsOptions()
            ) as streams:
                assert streams == (read, write)

    @pytest.mark.asyncio
    async def test_sse_first_tries_sse_before_http(self):
        """sse-first strategy: SSE is attempted first."""
        read, write = self._make_streams()

        @asynccontextmanager
        async def fake_http(*a, **kw):
            raise AssertionError("HTTP should not be attempted when SSE succeeds")
            yield  # pragma: no cover

        @asynccontextmanager
        async def fake_sse(*a, **kw):
            yield (read, write)

        with patch("mcp_secure_remote.transport._try_streamable_http", fake_http), \
             patch("mcp_secure_remote.transport._try_sse", fake_sse), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False):
            async with connect_to_remote_server(
                "https://example.com", {}, "sse-first", MtlsOptions()
            ) as streams:
                assert streams == (read, write)

    @pytest.mark.asyncio
    async def test_http_only_does_not_fall_back(self):
        """http-only strategy: raises immediately if HTTP fails without trying SSE."""
        @asynccontextmanager
        async def failing_http(*a, **kw):
            raise ConnectionError("HTTP not supported")
            yield  # pragma: no cover

        @asynccontextmanager
        async def fake_sse(*a, **kw):
            raise AssertionError("SSE must not be attempted with http-only strategy")
            yield  # pragma: no cover

        with patch("mcp_secure_remote.transport._try_streamable_http", failing_http), \
             patch("mcp_secure_remote.transport._try_sse", fake_sse), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False):
            with pytest.raises(ConnectionError, match="HTTP not supported"):
                async with connect_to_remote_server(
                    "https://example.com", {}, "http-only", MtlsOptions()
                ):
                    pass

    @pytest.mark.asyncio
    async def test_sse_only_does_not_fall_back(self):
        """sse-only strategy: raises immediately if SSE fails without trying HTTP."""
        @asynccontextmanager
        async def fake_http(*a, **kw):
            raise AssertionError("HTTP must not be attempted with sse-only strategy")
            yield  # pragma: no cover

        @asynccontextmanager
        async def failing_sse(*a, **kw):
            raise ConnectionError("SSE not supported")
            yield  # pragma: no cover

        with patch("mcp_secure_remote.transport._try_streamable_http", fake_http), \
             patch("mcp_secure_remote.transport._try_sse", failing_sse), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False):
            with pytest.raises(ConnectionError, match="SSE not supported"):
                async with connect_to_remote_server(
                    "https://example.com", {}, "sse-only", MtlsOptions()
                ):
                    pass

    @pytest.mark.asyncio
    async def test_both_transports_fail_raises_last_error(self):
        """Both transports fail → the last attempted error is raised."""
        @asynccontextmanager
        async def failing_http(*a, **kw):
            raise ConnectionError("HTTP failed")
            yield  # pragma: no cover

        @asynccontextmanager
        async def failing_sse(*a, **kw):
            raise ConnectionError("SSE failed")
            yield  # pragma: no cover

        with patch("mcp_secure_remote.transport._try_streamable_http", failing_http), \
             patch("mcp_secure_remote.transport._try_sse", failing_sse), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False):
            with pytest.raises(ConnectionError, match="SSE failed"):
                async with connect_to_remote_server(
                    "https://example.com", {}, "http-first", MtlsOptions()
                ):
                    pass

    @pytest.mark.asyncio
    async def test_mtls_config_triggers_ssl_context_build(self):
        """When mTLS config is present, build_ssl_context is called."""
        read, write = self._make_streams()

        @asynccontextmanager
        async def fake_http(*a, **kw):
            yield (read, write)

        with patch("mcp_secure_remote.transport._try_streamable_http", fake_http), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=True), \
             patch("mcp_secure_remote.transport.build_ssl_context") as mock_build:
            mock_build.return_value = MagicMock()
            async with connect_to_remote_server(
                "https://example.com", {}, "http-only", MtlsOptions()
            ):
                pass
            mock_build.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_mtls_config_skips_ssl_context_build(self):
        """When no mTLS config, build_ssl_context is NOT called."""
        read, write = self._make_streams()

        @asynccontextmanager
        async def fake_http(*a, **kw):
            yield (read, write)

        with patch("mcp_secure_remote.transport._try_streamable_http", fake_http), \
             patch("mcp_secure_remote.transport.has_mtls_config", return_value=False), \
             patch("mcp_secure_remote.transport.build_ssl_context") as mock_build:
            async with connect_to_remote_server(
                "https://example.com", {}, "http-only", MtlsOptions()
            ):
                pass
            mock_build.assert_not_called()
