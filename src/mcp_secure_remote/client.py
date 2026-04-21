"""
mcp-secure-remote-client — standalone client for exercising a remote MCP server
over mTLS without running a stdio proxy. Useful for verifying certificate
configuration and listing the tools/resources/prompts exposed by the server.
"""
from __future__ import annotations

import sys

import anyio
from mcp import ClientSession  # type: ignore[import]

from .args import parse_args, print_usage
from .log import debug_log, log, set_debug
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
    debug_log("parsed arguments", {
        "server_url": parsed.server_url,
        "transport_strategy": parsed.transport_strategy,
        "headers": list(parsed.headers.keys()),
    })

    async with connect_to_remote_server(
        server_url=parsed.server_url,
        headers=parsed.headers,
        strategy=parsed.transport_strategy,
        mtls=parsed.mtls,
    ) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            log("Connected.")

            capabilities = session.server_capabilities
            log("Server capabilities:", str(capabilities))

            if capabilities and capabilities.tools:
                result = await session.list_tools()
                log(f"Tools ({len(result.tools)}):")
                for tool in result.tools:
                    desc = f" – {tool.description}" if tool.description else ""
                    sys.stdout.write(f"  - {tool.name}{desc}\n")

            if capabilities and capabilities.resources:
                result = await session.list_resources()
                log(f"Resources ({len(result.resources)}):")
                for res in result.resources:
                    name = f" ({res.name})" if res.name else ""
                    sys.stdout.write(f"  - {res.uri}{name}\n")

            if capabilities and capabilities.prompts:
                result = await session.list_prompts()
                log(f"Prompts ({len(result.prompts)}):")
                for prompt in result.prompts:
                    sys.stdout.write(f"  - {prompt.name}\n")

            sys.stdout.flush()


def main() -> None:
    try:
        anyio.run(_run)
    except Exception as exc:
        log("Fatal error:", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
