"""CLI argument parser."""
import os
import sys
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from .auth_headers import AuthOptions, merge_auth_headers
from .http_headers import validate_http_header as _validate_http_header
from .message_size import DEFAULT_MAX_MESSAGE_BYTES, parse_max_message_bytes
from .mtls import MtlsOptions
from .url_security import UrlSecurityOptions, validate_remote_url
from . import __version__

TransportStrategy = Literal["http-first", "sse-first", "http-only", "sse-only"]
VALID_TRANSPORTS: tuple[str, ...] = ("http-first", "sse-first", "http-only", "sse-only")


@dataclass
class ParsedArgs:
    server_url: str
    headers: dict[str, str]
    transport_strategy: TransportStrategy
    debug: bool
    allow_http: bool
    allow_private_urls: bool
    max_message_bytes: int
    mtls: MtlsOptions
    auth: AuthOptions


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
    allow_private_urls = False
    max_message_bytes = DEFAULT_MAX_MESSAGE_BYTES
    tls_pins: list[str] = []

    auth = AuthOptions(
        bearer=_env("MCP_REMOTE_AUTH_BEARER"),
        basic=_env("MCP_REMOTE_AUTH_BASIC"),
        api_key=_env("MCP_REMOTE_API_KEY"),
        api_key_header=_env("MCP_REMOTE_API_KEY_HEADER"),
    )

    env_min_version = _env("MCP_REMOTE_TLS_MIN_VERSION")
    if env_min_version and env_min_version not in ("TLSv1.2", "TLSv1.3"):
        raise ValueError('MCP_REMOTE_TLS_MIN_VERSION must be "TLSv1.2" or "TLSv1.3"')

    env_insecure = _env("MCP_REMOTE_TLS_INSECURE")
    reject_unauthorized: bool | None = (
        False if env_insecure and env_insecure.lower() in ("1", "true", "yes") else None
    )

    env_max_message_bytes = _env("MCP_REMOTE_MAX_MESSAGE_BYTES")
    if env_max_message_bytes:
        max_message_bytes = parse_max_message_bytes(env_max_message_bytes, "MCP_REMOTE_MAX_MESSAGE_BYTES")

    env_tls_pin = _env("MCP_REMOTE_TLS_PIN_SHA256")
    if env_tls_pin:
        tls_pins.extend(pin.strip() for pin in env_tls_pin.split(",") if pin.strip())

    mtls = MtlsOptions(
        cert_path=_env("MCP_REMOTE_TLS_CERT"),
        key_path=_env("MCP_REMOTE_TLS_KEY"),
        ca_path=_env("MCP_REMOTE_TLS_CA"),
        passphrase=_env("MCP_REMOTE_TLS_PASSPHRASE"),
        pfx_path=_env("MCP_REMOTE_TLS_PFX"),
        servername=_env("MCP_REMOTE_TLS_SERVERNAME"),
        min_version=env_min_version,  # type: ignore[arg-type]
        reject_unauthorized=reject_unauthorized if reject_unauthorized is not None else True,
        pin_sha256=tls_pins or None,
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

        elif arg == "--allow-private-urls":
            allow_private_urls = True

        elif arg == "--max-message-bytes":
            max_message_bytes = parse_max_message_bytes(take("--max-message-bytes"), "--max-message-bytes")

        elif arg == "--auth-bearer":
            auth.bearer = take("--auth-bearer")
        elif arg == "--auth-basic":
            auth.basic = take("--auth-basic")
        elif arg == "--api-key":
            auth.api_key = take("--api-key")
        elif arg == "--api-key-header":
            auth.api_key_header = take("--api-key-header")

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

        elif arg == "--tls-pin-sha256":
            tls_pins.append(take("--tls-pin-sha256"))

        elif arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)

        elif arg in ("-V", "--version"):
            sys.stdout.write(f"mcp-secure-remote {__version__}\n")
            sys.stdout.flush()
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

    if parsed_url.scheme == "http" and not allow_http:
        raise ValueError("Refusing to use http:// without --allow-http; mTLS requires https://.")

    if parsed_url.scheme == "http" and _has_any_mtls_flag(mtls):
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

    validate_remote_url(server_url, UrlSecurityOptions(allow_private_urls=allow_private_urls))

    if tls_pins:
        mtls.pin_sha256 = tls_pins

    if mtls.pin_sha256 and not mtls.reject_unauthorized:
        raise ValueError("--tls-pin-sha256 cannot be combined with --tls-insecure-skip-verify")

    merged_headers = merge_auth_headers(headers, auth)

    return ParsedArgs(
        server_url=server_url,
        headers=merged_headers,
        transport_strategy=transport_strategy,
        debug=debug,
        allow_http=allow_http,
        allow_private_urls=allow_private_urls,
        max_message_bytes=max_message_bytes,
        mtls=mtls,
        auth=auth,
    )


def _has_any_mtls_flag(m: MtlsOptions) -> bool:
    return bool(
        m.cert_path
        or m.key_path
        or m.pfx_path
        or m.ca_path
        or m.passphrase
        or m.servername
        or m.min_version
        or m.pin_sha256
    )


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
        "  --allow-private-urls        Allow localhost and private-network targets (local dev / mTLS lab).",
        "  --max-message-bytes <n>     Drop JSON-RPC messages larger than n bytes (default: 10485760).",
        "  --debug                     Verbose logging to stderr.",
        "",
        "Application auth (supplement mTLS; sent as HTTP headers):",
        "  --auth-bearer <token>       Set Authorization: Bearer <token>.",
        "  --auth-basic <user:pass>    Set Authorization: Basic (base64).",
        "  --api-key <key>             Set an API key header (default name: X-Api-Key).",
        "  --api-key-header <name>     Override the API key header name.",
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
        "  --tls-pin-sha256 <pin>      SHA-256 SPKI pin for server cert (repeatable; base64, hex, or sha256/…).",
        "  --tls-insecure-skip-verify  Disable server certificate validation (NOT for production).",
        "",
        "  -h, --help                  Print usage and exit.",
        "  -V, --version               Print version and exit.",
        "",
        "Environment variables (fallbacks for flags):",
        "  MCP_REMOTE_TLS_CERT, MCP_REMOTE_TLS_KEY, MCP_REMOTE_TLS_CA,",
        "  MCP_REMOTE_TLS_PASSPHRASE, MCP_REMOTE_TLS_PFX, MCP_REMOTE_TLS_SERVERNAME,",
        "  MCP_REMOTE_TLS_MIN_VERSION, MCP_REMOTE_TLS_INSECURE (=1 to skip server cert verify)",
        "  MCP_REMOTE_TLS_PIN_SHA256 (comma-separated SPKI pins)",
        "  MCP_REMOTE_MAX_MESSAGE_BYTES",
        "  MCP_REMOTE_AUTH_BEARER, MCP_REMOTE_AUTH_BASIC, MCP_REMOTE_API_KEY, MCP_REMOTE_API_KEY_HEADER",
    ]
    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()
