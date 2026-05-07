"""Remote MCP server transport — HTTP/SSE with mTLS. Mirrors Node.js transport.ts."""
from __future__ import annotations

from contextlib import asynccontextmanager
import inspect
from typing import AsyncGenerator, Callable

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

    order: list[str] = (
        ["http", "sse"] if strategy in ("http-first", "http-only")
        else ["sse", "http"]
    )
    allow_fallback = strategy in ("http-first", "sse-first")
    last_error: Exception | None = None

    client_factory = _build_httpx_client_factory(ssl_context)

    for kind in order:
        try:
            if kind == "http":
                async with _try_streamable_http(server_url, headers, client_factory) as streams:
                    log("Connected using Streamable HTTP transport")
                    yield streams
                    return
            else:
                async with _try_sse(server_url, headers, client_factory) as streams:
                    log("Connected using SSE transport")
                    yield streams
                    return
        except Exception as exc:
            last_error = exc
            log(f"{kind} transport failed: {exc}")
            if not allow_fallback:
                break

    raise last_error if last_error is not None else RuntimeError("Unable to establish remote transport")


def _build_httpx_client_factory(
    ssl_context,
) -> Callable[[dict[str, str] | None, httpx.Timeout | None, httpx.Auth | None], httpx.AsyncClient]:
    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        kwargs: dict = {
            "follow_redirects": True,
            "verify": ssl_context or True,
        }
        if headers is not None:
            kwargs["headers"] = headers
        if timeout is not None:
            kwargs["timeout"] = timeout
        if auth is not None:
            kwargs["auth"] = auth
        return httpx.AsyncClient(**kwargs)

    return factory


@asynccontextmanager
async def _try_streamable_http(
    url: str,
    headers: dict[str, str],
    client_factory,
) -> AsyncGenerator[tuple, None]:
    from mcp.client import streamable_http as streamable_http_module  # type: ignore[import]

    streamable_http_client = getattr(
        streamable_http_module,
        "streamable_http_client",
        None,
    ) or getattr(streamable_http_module, "streamablehttp_client")

    signature = inspect.signature(streamable_http_client)
    if "httpx_client_factory" in signature.parameters:
        async with streamable_http_client(
            url,
            headers=headers,
            httpx_client_factory=client_factory,
        ) as streams:
            yield streams[:2]
    elif "client" in signature.parameters:
        async with client_factory(headers=headers, timeout=None, auth=None) as client:
            async with streamable_http_client(url, client=client) as streams:
                yield streams
    else:
        async with streamable_http_client(url, headers=headers) as streams:
            yield streams[:2]


@asynccontextmanager
async def _try_sse(
    url: str,
    headers: dict[str, str],
    client_factory,
) -> AsyncGenerator[tuple, None]:
    from mcp.client.sse import sse_client  # type: ignore[import]

    signature = inspect.signature(sse_client)
    if "httpx_client_factory" in signature.parameters:
        async with sse_client(
            url,
            headers=headers,
            httpx_client_factory=client_factory,
        ) as streams:
            yield streams
    elif "client" in signature.parameters:
        async with client_factory(headers=headers, timeout=None, auth=None) as client:
            async with sse_client(url, client=client) as streams:
                yield streams
    else:
        async with sse_client(url, headers=headers) as streams:
            yield streams
