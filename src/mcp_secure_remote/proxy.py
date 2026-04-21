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
from .log import debug_log, log, set_debug
from .mtls import MtlsOptions
from .transport import connect_to_remote_server


def _sanitize_mtls(mtls: MtlsOptions) -> dict:
    return {
        "cert_path": mtls.cert_path,
        "key_path": mtls.key_path,
        "ca_path": mtls.ca_path,
        "pfx_path": mtls.pfx_path,
        "servername": mtls.servername,
        "min_version": mtls.min_version,
        "reject_unauthorized": mtls.reject_unauthorized,
        "passphrase": "***" if mtls.passphrase else None,
    }


async def _run() -> None:
    try:
        parsed = parse_args()
    except (ValueError, SystemExit) as exc:
        if isinstance(exc, ValueError):
            log("Argument error:", str(exc))
            print_usage()
        sys.exit(2)

    set_debug(parsed.debug)
    debug_log("parsed arguments", {
        "server_url": parsed.server_url,
        "transport_strategy": parsed.transport_strategy,
        "allow_http": parsed.allow_http,
        "headers": list(parsed.headers.keys()),
        "mtls": _sanitize_mtls(parsed.mtls),
    })

    async with connect_to_remote_server(
        server_url=parsed.server_url,
        headers=parsed.headers,
        strategy=parsed.transport_strategy,
        mtls=parsed.mtls,
    ) as (remote_read, remote_write):
        async with stdio_server() as (local_read, local_write):
            log(f"Proxy established: stdio <-> {parsed.server_url}")

            async def forward_local_to_remote() -> None:
                async for message in local_read:
                    debug_log("client -> server", str(message))
                    await remote_write.send(message)

            async def forward_remote_to_local() -> None:
                async for message in remote_read:
                    debug_log("server -> client", str(message))
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
    except Exception as exc:
        log("Fatal error:", str(exc))
        msg = str(exc).lower()
        if "self signed" in msg or "unable to verify" in msg or "certificate verify failed" in msg:
            log(
                "TLS verification failed. If testing against a private CA, pass --tls-ca <path> "
                "to point at its bundle, or (for local dev only) --tls-insecure-skip-verify."
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
