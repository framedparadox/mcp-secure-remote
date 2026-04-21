"""Remote MCP server transport — HTTP/SSE with mTLS. Mirrors Node.js transport.ts."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx

from .args import TransportStrategy
from .log import debug_log, log
from .mtls import MtlsOptions, build_ssl_context, has_mtls_config


@asynccontextmanager
async def connect_to_remote_server(
    server_url: str,
    headers: dict[str, str],
    strategy: TransportStrategy,
    mtls: MtlsOptions,
) -> AsyncGenerator[tuple, None]:
    """Yield (read_stream, write_stream) connected to the remote MCP server."""
    ssl_context = None
    if has_mtls_config(mtls):
        ssl_context = build_ssl_context(mtls)
        if mtls.servername:
            log(f"mTLS enabled; SNI override: {mtls.servername}")
        else:
            log("mTLS enabled for outbound requests")
    else:
        debug_log("no mTLS configuration supplied; using default SSL verification")

    # SNI override: pass a custom transport so httpx uses the right server_hostname.
    if ssl_context is not None and mtls.servername:
        http_transport = httpx.AsyncHTTPTransport(
            verify=ssl_context,
            http2=True,
            socket_options=[],
        )
        client_kwargs: dict = {"headers": headers, "transport": http_transport, "timeout": None}
    else:
        client_kwargs = {"headers": headers, "verify": ssl_context or True, "timeout": None}

    order: list[str] = (
        ["http", "sse"] if strategy in ("http-first", "http-only")
        else ["sse", "http"]
    )
    allow_fallback = strategy in ("http-first", "sse-first")
    last_error: Exception | None = None

    async with httpx.AsyncClient(**client_kwargs) as http_client:
        for kind in order:
            try:
                if kind == "http":
                    async with _try_streamable_http(server_url, http_client) as streams:
                        log("Connected using Streamable HTTP transport")
                        yield streams
                        return
                else:
                    async with _try_sse(server_url, http_client) as streams:
                        log("Connected using SSE transport")
                        yield streams
                        return
            except Exception as exc:
                last_error = exc
                log(f"{kind} transport failed: {exc}")
                if not allow_fallback:
                    break

    raise last_error if last_error is not None else RuntimeError("Unable to establish remote transport")


@asynccontextmanager
async def _try_streamable_http(url: str, client: httpx.AsyncClient) -> AsyncGenerator[tuple, None]:
    from mcp.client.streamable_http import streamable_http_client  # type: ignore[import]
    async with streamable_http_client(url, client=client) as streams:
        yield streams


@asynccontextmanager
async def _try_sse(url: str, client: httpx.AsyncClient) -> AsyncGenerator[tuple, None]:
    from mcp.client.sse import sse_client  # type: ignore[import]
    async with sse_client(url, client=client) as streams:
        yield streams
