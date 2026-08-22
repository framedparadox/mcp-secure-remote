"""Remote MCP server transport — HTTP/SSE with mTLS."""
from __future__ import annotations

from contextlib import asynccontextmanager
import inspect
from typing import AsyncGenerator, Callable
from urllib.parse import urlparse

import httpx

from .args import TransportStrategy
from .log import debug_log, log
from .mtls import MtlsOptions, build_ssl_context, has_mtls_config


def _get_origin(url: str) -> str:
    """Return the scheme+netloc origin of *url* (e.g. 'https://host:8443')."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc.lower()}"


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

    client_factory = _build_httpx_client_factory(ssl_context, _get_origin(server_url))

    for kind in order:
        connected = False
        try:
            if kind == "http":
                async with _try_streamable_http(server_url, headers, client_factory) as streams:
                    log("Connected using Streamable HTTP transport")
                    connected = True
                    yield streams
                    return
            else:
                async with _try_sse(server_url, headers, client_factory) as streams:
                    log("Connected using SSE transport")
                    connected = True
                    yield streams
                    return
        except Exception as exc:
            if connected:
                # Error occurred after a successful connection — not a transport
                # negotiation failure, so don't fall back and don't suppress it.
                raise
            last_error = exc
            log(f"{kind} transport failed: {exc}")
            if not allow_fallback:
                break

    raise last_error if last_error is not None else RuntimeError("Unable to establish remote transport")


def _build_httpx_client_factory(
    ssl_context,
    expected_origin: str,
) -> Callable[[dict[str, str] | None, httpx.Timeout | None, httpx.Auth | None], httpx.AsyncClient]:
    async def _check_origin(request: httpx.Request) -> None:
        """Block any request whose origin differs from the pinned expected origin."""
        req_origin = _get_origin(str(request.url))
        if req_origin != expected_origin:
            debug_log(
                "blocked outbound request to unexpected origin",
                {"expected": expected_origin, "actual": req_origin},
            )
            raise ValueError(
                f"Refusing outbound request to an unexpected origin: {req_origin!r}"
            )

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        kwargs: dict = {
            "follow_redirects": False,
            "verify": ssl_context or True,
            "event_hooks": {"request": [_check_origin]},
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
    elif "http_client" in signature.parameters:
        # mcp ≥ 1.27: accepts a pre-built httpx.AsyncClient via http_client
        async with client_factory(headers=headers, timeout=None, auth=None) as http_client:
            async with streamable_http_client(url, http_client=http_client) as streams:
                yield streams[:2]
    elif "client" in signature.parameters:
        async with client_factory(headers=headers, timeout=None, auth=None) as client:
            async with streamable_http_client(url, client=client) as streams:
                yield streams
    else:
        detected = list(signature.parameters.keys())
        raise RuntimeError(
            f"mcp streamable_http_client has an unrecognised signature {detected}; "
            "cannot inject a secure httpx client. "
            "Upgrade mcp-secure-remote or pin a supported version of the mcp package."
        )


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
        detected = list(signature.parameters.keys())
        raise RuntimeError(
            f"mcp sse_client has an unrecognised signature {detected}; "
            "cannot inject a secure httpx client. "
            "Upgrade mcp-secure-remote or pin a supported version of the mcp package."
        )
