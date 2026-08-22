"""CLI argument parser."""
import os
import re
import sys
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from .mtls import MtlsOptions

TransportStrategy = Literal["http-first", "sse-first", "http-only", "sse-only"]
VALID_TRANSPORTS: tuple[str, ...] = ("http-first", "sse-first", "http-only", "sse-only")

# RFC 7230 §3.2.6 — a header field-name must be a sequence of "token" chars.
# Rejecting anything outside this alphabet prevents CRLF-injection attacks
# even if the underlying HTTP library would catch it later.
_VALID_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+\-.^_`|~]+$")


def _validate_http_header(name: str, value: str) -> None:
    """Raise ValueError for header names/values that could enable injection."""
    if not _VALID_HEADER_NAME_RE.match(name):
        raise ValueError(
            f'Invalid header name {name!r}: must be a valid RFC 7230 HTTP token '
            r"(alphanumerics and !#$%&'*+-.^_`|~)"
        )
    # Bare CR, LF, or NUL in a header value enable CRLF-injection attacks.
    if re.search(r"[\r\n\x00]", value):
        raise ValueError(
            f"Header value for {name!r} must not contain CR, LF, or NUL characters"
        )


@dataclass
class ParsedArgs:
    server_url: str
    headers: dict[str, str]
    transport_strategy: TransportStrategy
    debug: bool
    allow_http: bool
    mtls: MtlsOptions


def _env(name: str) -> str | None:
    v = os.environ.get(name, "")
    return v if v else None


def parse_args(argv: list[str] | None = None) -> ParsedArgs:
    if argv is None:
        argv = sys.argv[1:]

    args = list(argv)
    server_url: str | None = None
    headers: dict[str, str] = {}
    transport_strategy: TransportStrategy = "http-first"
    debug = False
    allow_http = False

    env_min_version = _env("MCP_REMOTE_TLS_MIN_VERSION")
    if env_min_version and env_min_version not in ("TLSv1.2", "TLSv1.3"):
        raise ValueError('MCP_REMOTE_TLS_MIN_VERSION must be "TLSv1.2" or "TLSv1.3"')

    env_insecure = _env("MCP_REMOTE_TLS_INSECURE")
    reject_unauthorized: bool | None = (
        False if env_insecure and env_insecure.lower() in ("1", "true", "yes") else None
    )

    mtls = MtlsOptions(
        cert_path=_env("MCP_REMOTE_TLS_CERT"),
        key_path=_env("MCP_REMOTE_TLS_KEY"),
        ca_path=_env("MCP_REMOTE_TLS_CA"),
        passphrase=_env("MCP_REMOTE_TLS_PASSPHRASE"),
        pfx_path=_env("MCP_REMOTE_TLS_PFX"),
        servername=_env("MCP_REMOTE_TLS_SERVERNAME"),
        min_version=env_min_version,  # type: ignore[arg-type]
        reject_unauthorized=reject_unauthorized if reject_unauthorized is not None else True,
    )

    def take(flag: str) -> str:
        if not args:
            raise ValueError(f"Missing value for {flag}")
        return args.pop(0)

    while args:
        arg = args.pop(0)

        if arg == "--header":
            raw = take("--header")
            idx = raw.find(":")
            if idx == -1:
                raise ValueError(f'--header expects "Name: value", got "{raw}"')
            name = raw[:idx].strip()
            value = raw[idx + 1:].strip()
            if not name:
                raise ValueError(f'--header has empty name: "{raw}"')
            _validate_http_header(name, value)
            headers[name] = value

        elif arg == "--transport":
            value = take("--transport")
            if value not in VALID_TRANSPORTS:
                raise ValueError(f"--transport must be one of {', '.join(VALID_TRANSPORTS)}")
            transport_strategy = value  # type: ignore[assignment]

        elif arg == "--debug":
            debug = True

        elif arg == "--allow-http":
            allow_http = True

        elif arg == "--tls-cert":
            mtls.cert_path = take("--tls-cert")
        elif arg == "--tls-key":
            mtls.key_path = take("--tls-key")
        elif arg == "--tls-ca":
            mtls.ca_path = take("--tls-ca")
        elif arg == "--tls-passphrase":
            mtls.passphrase = take("--tls-passphrase")
        elif arg == "--tls-pfx":
            mtls.pfx_path = take("--tls-pfx")
        elif arg == "--tls-servername":
            mtls.servername = take("--tls-servername")

        elif arg == "--tls-min-version":
            v = take("--tls-min-version")
            if v not in ("TLSv1.2", "TLSv1.3"):
                raise ValueError('--tls-min-version must be "TLSv1.2" or "TLSv1.3"')
            mtls.min_version = v  # type: ignore[assignment]

        elif arg in ("--tls-insecure-skip-verify", "--tls-no-verify"):
            mtls.reject_unauthorized = False

        elif arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)

        elif arg.startswith("--"):
            raise ValueError(f"Unknown flag: {arg}")

        else:
            if server_url is not None:
                raise ValueError(f"Unexpected positional argument: {arg}")
            server_url = arg

    if server_url is None:
        raise ValueError("Missing required positional argument: <server-url>")

    parsed_url = urlparse(server_url)
    if not parsed_url.scheme or not parsed_url.netloc:
        raise ValueError(f"Invalid server URL: {server_url}")
    if parsed_url.scheme not in ("http", "https"):
        raise ValueError(f"Server URL must use http(s), got: {parsed_url.scheme}:")
    if parsed_url.username or parsed_url.password:
        raise ValueError(
            "Server URL must not contain embedded credentials; "
            "use --header or environment configuration instead."
        )

    if server_url.startswith("http://") and not allow_http:
        raise ValueError("Refusing to use http:// without --allow-http; mTLS requires https://.")

    if server_url.startswith("http://") and _has_any_mtls_flag(mtls):
        sys.stderr.write(
            "WARNING: mTLS options supplied with http:// URL; "
            "client certificate will NOT be sent over plain HTTP.\n"
        )
        sys.stderr.flush()

    if not mtls.reject_unauthorized:
        sys.stderr.write(
            "WARNING: TLS server certificate verification disabled. "
            "This is insecure; use only for local development.\n"
        )
        sys.stderr.flush()

    return ParsedArgs(
        server_url=server_url,
        headers=headers,
        transport_strategy=transport_strategy,
        debug=debug,
        allow_http=allow_http,
        mtls=mtls,
    )


def _has_any_mtls_flag(m: MtlsOptions) -> bool:
    return bool(m.cert_path or m.key_path or m.pfx_path or m.ca_path or m.passphrase or m.servername or m.min_version)


def print_usage() -> None:
    lines = [
        "Usage: mcp-secure-remote <server-url> [options]",
        "",
        "Bridges a local stdio MCP client to a remote MCP server, authenticating",
        "with a mutual-TLS client certificate.",
        "",
        "Options:",
        '  --header "Name: value"      Add a custom HTTP header (repeatable).',
        "  --transport <strategy>      http-first | sse-first | http-only | sse-only (default: http-first).",
        "  --allow-http                Allow plain http:// URLs (disables the default https-only check).",
        "  --debug                     Verbose logging to stderr.",
        "",
        "mTLS options:",
        "  --tls-cert <path>           PEM client certificate (or chain).",
        "  --tls-key <path>            PEM private key matching --tls-cert.",
        "  --tls-ca <path>             PEM CA bundle used to verify the remote server.",
        "  --tls-passphrase <value>    Passphrase protecting the private key.",
        "                              WARNING: visible in process listings (ps/top). Prefer MCP_REMOTE_TLS_PASSPHRASE.",
        "  --tls-pfx <path>            PKCS#12 bundle (alternative to --tls-cert/--tls-key).",
        "  --tls-servername <name>     SNI servername override.",
        "  --tls-min-version <ver>     TLSv1.2 or TLSv1.3.",
        "  --tls-insecure-skip-verify  Disable server certificate validation (NOT for production).",
        "",
        "Environment variables (fallbacks for flags):",
        "  MCP_REMOTE_TLS_CERT, MCP_REMOTE_TLS_KEY, MCP_REMOTE_TLS_CA,",
        "  MCP_REMOTE_TLS_PASSPHRASE, MCP_REMOTE_TLS_PFX, MCP_REMOTE_TLS_SERVERNAME,",
        "  MCP_REMOTE_TLS_MIN_VERSION, MCP_REMOTE_TLS_INSECURE (=1 to skip server cert verify)",
    ]
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()
