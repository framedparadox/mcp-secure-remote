"""
mcp-secure-remote proxy — stdio <-> remote MCP server bridge with mTLS support.

Spawns as a local stdio MCP server and forwards traffic to a remote MCP
server over HTTPS. Client certificate authentication (mTLS) can be
configured via --tls-cert / --tls-key / --tls-ca (or the MCP_REMOTE_TLS_*
environment variables).
"""
from __future__ import annotations

import anyio
import sys

from mcp.server.stdio import stdio_server  # type: ignore[import]

from .args import parse_args, print_usage
from .log import debug_log, flatten_exception, log, set_debug
from .sanitize import sanitize_parsed_args_for_log, sanitize_server_url_for_log, summarize_message
from .transport import connect_to_remote_server


async def _run() -> None:
    try:
        parsed = parse_args()
    except (ValueError, SystemExit) as exc:
        if isinstance(exc, ValueError):
            log("Argument error:", str(exc))
            print_usage()
        sys.exit(2)

    set_debug(parsed.debug)
    debug_log("parsed arguments", sanitize_parsed_args_for_log(parsed))

    async with connect_to_remote_server(
        server_url=parsed.server_url,
        headers=parsed.headers,
        strategy=parsed.transport_strategy,
        mtls=parsed.mtls,
    ) as (remote_read, remote_write):
        async with stdio_server() as (local_read, local_write):
            log(f"Proxy established: stdio <-> {sanitize_server_url_for_log(parsed.server_url)}")

            async def forward_local_to_remote() -> None:
                async for message in local_read:
                    if isinstance(message, Exception):
                        # MCP's stdio_server emits the raw ValidationError when the
                        # client sends malformed JSON. Forwarding it would crash the
                        # remote transport; drop it and just record the parse error.
                        debug_log("client -> server (dropped parse error)", str(message))
                        continue
                    debug_log("client -> server", summarize_message(message))
                    await remote_write.send(message)

            async def forward_remote_to_local() -> None:
                async for message in remote_read:
                    if isinstance(message, Exception):
                        # Same hazard on the remote side — drop it before it
                        # tears down stdout_writer with an AttributeError.
                        debug_log("server -> client (dropped parse error)", str(message))
                        continue
                    debug_log("server -> client", summarize_message(message))
                    await local_write.send(message)

            async with anyio.create_task_group() as tg:
                tg.start_soon(forward_local_to_remote)
                tg.start_soon(forward_remote_to_local)


def main() -> None:
    try:
        anyio.run(_run)
    except KeyboardInterrupt:
        log("Received interrupt; shutting down.")
        sys.exit(0)
    except SystemExit:
        # _run() raised sys.exit(<code>) on its own — let it through verbatim
        # so the user sees their original argument-error exit code (2).
        raise
    except BaseException as exc:
        leaf = flatten_exception(exc)
        if isinstance(leaf, SystemExit):
            raise leaf
        log("Fatal error:", f"{type(leaf).__name__}: {leaf}")
        msg = str(leaf).lower()
        if "self signed" in msg or "unable to verify" in msg or "certificate verify failed" in msg:
            log(
                "TLS verification failed. If testing against a private CA, pass --tls-ca <path> "
                "to point at its bundle, or (for local dev only) --tls-insecure-skip-verify."
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
