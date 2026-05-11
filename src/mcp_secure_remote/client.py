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
from .log import debug_log, flatten_exception, log, set_debug
from .sanitize import sanitize_parsed_args_for_log, sanitize_terminal_text
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
    ) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialize_result = await session.initialize()
            log("Connected.")

            capabilities = getattr(session, "server_capabilities", None) or initialize_result.capabilities
            log("Server capabilities:", str(capabilities))

            if capabilities and capabilities.tools:
                result = await session.list_tools()
                log(f"Tools ({len(result.tools)}):")
                for tool in result.tools:
                    name = sanitize_terminal_text(tool.name)
                    desc = f" – {sanitize_terminal_text(tool.description)}" if tool.description else ""
                    sys.stdout.write(f"  - {name}{desc}\n")

            if capabilities and capabilities.resources:
                result = await session.list_resources()
                log(f"Resources ({len(result.resources)}):")
                for res in result.resources:
                    uri = sanitize_terminal_text(res.uri)
                    name = f" ({sanitize_terminal_text(res.name)})" if res.name else ""
                    sys.stdout.write(f"  - {uri}{name}\n")

            if capabilities and capabilities.prompts:
                result = await session.list_prompts()
                log(f"Prompts ({len(result.prompts)}):")
                for prompt in result.prompts:
                    sys.stdout.write(f"  - {sanitize_terminal_text(prompt.name)}\n")

            sys.stdout.flush()


def main() -> None:
    try:
        anyio.run(_run)
    except KeyboardInterrupt:
        log("Received interrupt; shutting down.")
        sys.exit(0)
    except SystemExit:
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
