#!/usr/bin/env python3
"""Run a local HTTPS MCP server that requires a trusted client certificate."""
from __future__ import annotations

import argparse
import ssl
import sys
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def build_server(mcp_path: str, sse_path: str, message_path: str) -> FastMCP:
    server = FastMCP(
        "mcp-secure-remote-local-mtls",
        instructions="Local development MCP server protected by mutual TLS.",
        streamable_http_path=mcp_path,
        sse_path=sse_path,
        message_path=message_path,
        log_level="INFO",
    )

    @server.tool()
    def ping() -> str:
        """Return a simple liveness response."""
        return "pong"

    @server.tool()
    def echo(message: str) -> str:
        """Echo a message back to the caller."""
        return message

    @server.resource("mock://mtls/status", mime_type="text/plain")
    def mtls_status() -> str:
        return (
            "ok: this resource is only reachable after the HTTPS server "
            "accepts the client's mTLS certificate"
        )

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok", "mtls": "required", "mcp_path": mcp_path})

    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local mock MCP endpoint over HTTPS with client certificate authentication."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8443, help="Port to bind. Default: 8443")
    parser.add_argument(
        "--cert-dir",
        default="certs/dev",
        help="Directory containing ca.crt, server.crt, and server.key. Default: certs/dev",
    )
    parser.add_argument(
        "--transport",
        choices=("streamable-http", "sse"),
        default="streamable-http",
        help="MCP transport to expose. Default: streamable-http",
    )
    parser.add_argument("--mcp-path", default="/mcp", help="Streamable HTTP path. Default: /mcp")
    parser.add_argument("--sse-path", default="/sse", help="SSE path. Default: /sse")
    parser.add_argument("--message-path", default="/messages/", help="SSE message path. Default: /messages/")
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if path.is_file():
        return
    raise SystemExit(
        f"Missing {label}: {path}\n"
        "Generate local certificates first:\n"
        "  scripts/generate_dev_mtls_certs.sh"
    )


def main() -> None:
    args = parse_args()
    cert_dir = Path(args.cert_dir)
    ca_cert = cert_dir / "ca.crt"
    server_cert = cert_dir / "server.crt"
    server_key = cert_dir / "server.key"

    require_file(ca_cert, "CA bundle")
    require_file(server_cert, "server certificate")
    require_file(server_key, "server private key")

    server = build_server(args.mcp_path, args.sse_path, args.message_path)
    app = server.streamable_http_app() if args.transport == "streamable-http" else server.sse_app()
    endpoint_path = args.mcp_path if args.transport == "streamable-http" else args.sse_path
    endpoint_url = f"https://localhost:{args.port}{endpoint_path}"

    print("Starting local mTLS MCP mock server", file=sys.stderr)
    print(f"  endpoint: {endpoint_url}", file=sys.stderr)
    print(f"  health:   https://localhost:{args.port}/healthz", file=sys.stderr)
    print(f"  CA:       {ca_cert}", file=sys.stderr)
    print("  client certificates signed by this CA are required", file=sys.stderr)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        ssl_certfile=str(server_cert),
        ssl_keyfile=str(server_key),
        ssl_ca_certs=str(ca_cert),
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
    )


if __name__ == "__main__":
    main()
