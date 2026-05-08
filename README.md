# mcp-secure-remote

A stdio ↔ remote bridge for the [Model Context Protocol](https://modelcontextprotocol.io)
with first-class **mTLS (mutual TLS) client-certificate authentication**.

Run directly with [`uvx`](https://docs.astral.sh/uv/guides/tools/) — no install step needed:

```bash
uvx mcp-secure-remote https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

Works with any MCP-capable AI agent or IDE — Claude Desktop, Claude Code,
Cursor, Windsurf, Cline, Continue, Zed, and any custom client that speaks
the MCP stdio transport.

---

## Contents

1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
3. [Prerequisites](#prerequisites)
4. [Install](#install)
5. [Docker](#docker)
6. [Generate or obtain client certificates](#generate-or-obtain-client-certificates)
7. [Quick start](#quick-start)
8. [CLI parameters](#cli-parameters)
9. [Environment variables](#environment-variables)
10. [AI agent / IDE integration](#ai-agent--ide-integration)
    - [Claude Desktop](#claude-desktop)
    - [Claude Code (CLI)](#claude-code-cli)
    - [Cursor](#cursor)
    - [Windsurf](#windsurf)
    - [Cline (VS Code)](#cline-vs-code)
    - [Continue (VS Code / JetBrains)](#continue-vs-code--jetbrains)
    - [Zed](#zed)
    - [Generic MCP client](#generic-mcp-client)
11. [Testing your setup](#testing-your-setup)
12. [Security notes](#security-notes)
13. [Troubleshooting](#troubleshooting)
14. [Development](#development)
15. [License](#license)

---

## What it does

`mcp-secure-remote` spawns as a local stdio MCP server and forwards every
JSON-RPC message to a remote MCP server over HTTPS. Every outbound request
carries a client certificate you supply, so the remote server sees a
cryptographically authenticated connection — no OAuth dance, no bearer
tokens on the wire, no shared API keys.

```
┌──────────────┐   stdio    ┌────────────────────┐   HTTPS + mTLS   ┌───────────────┐
│ MCP client   │───────────▶│ mcp-secure-remote  │─────────────────▶│ Remote MCP    │
│ (Claude,     │            │ (uvx, this proxy)  │                  │ server        │
│  Cursor, …)  │◀───────────│                    │◀─────────────────│               │
└──────────────┘            └────────────────────┘                  └───────────────┘
```

The remote MCP server can be implemented in any language — Python, Go, Rust,
Node.js, etc. The proxy only sees HTTPS + JSON-RPC.

## How it works

1. AI agent launches `mcp-secure-remote` (via `uvx`) as a local subprocess
   and talks to it over stdio — the transport every MCP client already supports.
2. Proxy builds an `httpx` HTTPS client seeded with your client cert,
   private key, and trusted CA bundle.
3. Proxy opens either a Streamable HTTP or SSE transport to the remote
   server (configurable). TLS handshake presents the client cert; the server
   validates it before forwarding the MCP session.
4. JSON-RPC frames flow bidirectionally. All proxy logging goes to stderr
   so the stdio channel stays clean.

## Prerequisites

- Python **≥ 3.10**.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed
  (`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS/Linux).
- A client certificate + private key issued by a CA the remote MCP server
  trusts (or a PKCS#12 bundle containing both).
- The CA bundle used by the remote server, if it is not in your OS trust
  store (private/corporate CAs almost always need this).
- The remote MCP server URL (typically `https://host/mcp` or
  `https://host/sse`).

## Install

`uvx` runs the package directly from PyPI in an isolated environment — no
explicit install step needed:

```bash
uvx mcp-secure-remote --help
```

To install permanently in a `uv`-managed tool environment:

```bash
uv tool install mcp-secure-remote
mcp-secure-remote --help
```

## Docker

Docker lets you run `mcp-secure-remote` without installing Python or `uv`.
The container reads stdio from its parent process, so MCP clients that
spawn subprocesses work exactly the same way — just replace `uvx` with
`docker run`.

### Dockerfile

```dockerfile
FROM python:3.12-slim

RUN pip install --no-cache-dir mcp-secure-remote

ENTRYPOINT ["mcp-secure-remote"]
```

Build the image:

```bash
docker build -t mcp-secure-remote .
```

### Run directly

Mount your cert directory (read-only) and pass the usual flags:

```bash
docker run --rm -i \
  -v /absolute/path/to/certs:/certs:ro \
  mcp-secure-remote \
  https://mcp.example.com/mcp \
  --tls-cert /certs/client.crt \
  --tls-key  /certs/client.key \
  --tls-ca   /certs/ca-bundle.pem
```

`-i` keeps stdin open — required because the proxy reads the MCP stream
from the container's stdin. `--rm` removes the container after it exits.

Using env vars to keep secrets out of command history:

```bash
docker run --rm -i \
  -v /absolute/path/to/certs:/certs:ro \
  -e MCP_REMOTE_TLS_CERT=/certs/client.crt \
  -e MCP_REMOTE_TLS_KEY=/certs/client.key \
  -e MCP_REMOTE_TLS_CA=/certs/ca-bundle.pem \
  mcp-secure-remote \
  https://mcp.example.com/mcp
```

### MCP client config

Replace `uvx` with `docker run` in any client config. Example for Claude
Desktop / Claude Code / Cursor:

```json
{
  "mcpServers": {
    "example": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/absolute/path/to/certs:/certs:ro",
        "mcp-secure-remote",
        "https://mcp.example.com/mcp",
        "--tls-cert", "/certs/client.crt",
        "--tls-key",  "/certs/client.key",
        "--tls-ca",   "/certs/ca-bundle.pem"
      ]
    }
  }
}
```

To keep secrets out of the config, pass them via `-e` instead:

```json
{
  "mcpServers": {
    "example": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "/absolute/path/to/certs:/certs:ro",
        "-e", "MCP_REMOTE_TLS_CERT=/certs/client.crt",
        "-e", "MCP_REMOTE_TLS_KEY=/certs/client.key",
        "-e", "MCP_REMOTE_TLS_CA=/certs/ca-bundle.pem",
        "mcp-secure-remote",
        "https://mcp.example.com/mcp"
      ]
    }
  }
}
```

### Docker Compose

Useful when you want cert mounts and env vars declared once in version
control rather than repeated in every client config.

`compose.yml`:

```yaml
services:
  mcp-proxy:
    build: .
    stdin_open: true
    volumes:
      - /absolute/path/to/certs:/certs:ro
    environment:
      MCP_REMOTE_TLS_CERT: /certs/client.crt
      MCP_REMOTE_TLS_KEY:  /certs/client.key
      MCP_REMOTE_TLS_CA:   /certs/ca-bundle.pem
    command:
      - https://mcp.example.com/mcp
```

Run once to verify the connection:

```bash
docker compose run --rm mcp-proxy
```

Then point MCP clients at `docker compose run --rm mcp-proxy` as the
command (with no extra args — env and volume come from `compose.yml`):

```json
{
  "mcpServers": {
    "example": {
      "command": "docker",
      "args": ["compose", "run", "--rm", "mcp-proxy"]
    }
  }
}
```

---

## Generate or obtain client certificates

If your team already issues client certs, skip this section. For local
testing, generate a throw-away CA + client cert pair with OpenSSL:

```bash
# CA
openssl req -x509 -newkey rsa:4096 -sha256 -days 365 -nodes \
  -keyout ca.key -out ca.crt -subj "/CN=dev-ca"

# client key + CSR
openssl req -newkey rsa:4096 -nodes \
  -keyout client.key -out client.csr -subj "/CN=dev-client"

# sign client cert with CA
openssl x509 -req -in client.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out client.crt -days 365 -sha256
```

Configure the remote MCP server to require client certs signed by `ca.crt`.
Point the proxy at `client.crt` + `client.key` + the server's CA bundle.

## Quick start

Cert + key pair:

```bash
uvx mcp-secure-remote https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

PKCS#12 bundle:

```bash
uvx mcp-secure-remote https://mcp.example.com/mcp \
  --tls-pfx       ./certs/client.p12 \
  --tls-passphrase "$P12_PASSPHRASE" \
  --tls-ca        ./certs/ca-bundle.pem
```

Force SSE transport + pin minimum TLS:

```bash
uvx mcp-secure-remote https://mcp.example.com/sse \
  --transport sse-only \
  --tls-min-version TLSv1.3 \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

## CLI parameters

Usage: `mcp-secure-remote <server-url> [options]`

`<server-url>` is a positional argument (required). Everything else is a
named flag.

### General

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `<server-url>` | string (URL) | — | **Required.** Remote MCP endpoint. Must be `https://…` unless `--allow-http` is set. |
| `--header "Name: value"` | string (repeatable) | — | Extra HTTP header on every outbound request. Repeat the flag for multiple headers. |
| `--transport <strategy>` | enum | `http-first` | Transport negotiation. One of `http-first`, `sse-first`, `http-only`, `sse-only`. `-first` variants try the preferred transport then fall back; `-only` variants never fall back. |
| `--allow-http` | boolean | `false` | Permit plain `http://` URLs. Off by default; mTLS is meaningless over HTTP. |
| `--debug` | boolean | `false` | Verbose logging to stderr (parsed args, per-message trace, transport selection). |
| `--version` | boolean | — | Print version and exit. |
| `-h`, `--help` | boolean | — | Print usage and exit. |

### mTLS / TLS

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--tls-cert <path>` | path | — | PEM client certificate (leaf, optionally followed by chain intermediates). |
| `--tls-key <path>` | path | — | PEM private key matching `--tls-cert`. Must be supplied together with `--tls-cert`. |
| `--tls-ca <path>` | path | — | PEM CA bundle used to verify the remote server. Required for private CAs not in the OS trust store. |
| `--tls-pfx <path>` | path | — | PKCS#12 (`.pfx` / `.p12`) bundle. Mutually exclusive with `--tls-cert`/`--tls-key`. |
| `--tls-passphrase <value>` | string | — | Passphrase protecting the private key or PFX bundle. Prefer the env var to keep secrets off the command line. |
| `--tls-servername <name>` | string | URL hostname | SNI override. Use when the server cert's SAN differs from the URL host (e.g. IP literal, internal DNS). |
| `--tls-min-version <ver>` | enum | system default | Minimum TLS version: `TLSv1.2` or `TLSv1.3`. |
| `--tls-insecure-skip-verify`, `--tls-no-verify` | boolean | `false` | Disable server certificate validation. **Dev only.** Proxy prints a warning when enabled. |

### Parameter rules

- `--tls-cert` and `--tls-key` must appear together.
- `--tls-pfx` cannot combine with `--tls-cert`/`--tls-key`.
- `--allow-http` is required for any `http://` URL. Supplying mTLS flags
  with `http://` triggers a warning (cert is not sent over plain HTTP).
- Unknown `--flags` cause parse failure with exit code 2.
- Argument errors exit with code 2; runtime errors exit with code 1.

## Environment variables

Every TLS flag has an env-var fallback so secrets can stay out of shell
history and MCP client configs.

| Variable | Equivalent flag | Values |
| --- | --- | --- |
| `MCP_REMOTE_TLS_CERT` | `--tls-cert` | path |
| `MCP_REMOTE_TLS_KEY` | `--tls-key` | path |
| `MCP_REMOTE_TLS_CA` | `--tls-ca` | path |
| `MCP_REMOTE_TLS_PFX` | `--tls-pfx` | path |
| `MCP_REMOTE_TLS_PASSPHRASE` | `--tls-passphrase` | string |
| `MCP_REMOTE_TLS_SERVERNAME` | `--tls-servername` | string |
| `MCP_REMOTE_TLS_MIN_VERSION` | `--tls-min-version` | `TLSv1.2` \| `TLSv1.3` |
| `MCP_REMOTE_TLS_INSECURE` | `--tls-insecure-skip-verify` | `1` / `true` / `yes` to disable verify |

Precedence: explicit CLI flag overrides env var.

## AI agent / IDE integration

Use **absolute paths** for all cert files — agents do not inherit your
shell's working directory.

### Claude Desktop

File: `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": [
        "mcp-secure-remote",
        "https://mcp.example.com/mcp",
        "--tls-cert", "/absolute/path/client.crt",
        "--tls-key",  "/absolute/path/client.key",
        "--tls-ca",   "/absolute/path/ca-bundle.pem"
      ]
    }
  }
}
```

Using env vars to keep secrets out of the config file:

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": ["mcp-secure-remote", "https://mcp.example.com/mcp"],
      "env": {
        "MCP_REMOTE_TLS_CERT": "/absolute/path/client.crt",
        "MCP_REMOTE_TLS_KEY":  "/absolute/path/client.key",
        "MCP_REMOTE_TLS_CA":   "/absolute/path/ca-bundle.pem"
      }
    }
  }
}
```

Restart Claude Desktop after editing.

### Claude Code (CLI)

Add via `claude mcp add` or edit `~/.claude.json` / project `.mcp.json`:

```bash
claude mcp add example uvx -- mcp-secure-remote \
  https://mcp.example.com/mcp \
  --tls-cert /absolute/path/client.crt \
  --tls-key  /absolute/path/client.key \
  --tls-ca   /absolute/path/ca-bundle.pem
```

Or in `.mcp.json`:

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": [
        "mcp-secure-remote",
        "https://mcp.example.com/mcp",
        "--tls-cert", "/absolute/path/client.crt",
        "--tls-key",  "/absolute/path/client.key",
        "--tls-ca",   "/absolute/path/ca-bundle.pem"
      ]
    }
  }
}
```

### Cursor

File: `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per project).

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": [
        "mcp-secure-remote",
        "https://mcp.example.com/mcp",
        "--tls-cert", "/absolute/path/client.crt",
        "--tls-key",  "/absolute/path/client.key",
        "--tls-ca",   "/absolute/path/ca-bundle.pem"
      ],
      "env": {
        "MCP_REMOTE_TLS_PASSPHRASE": "…optional…"
      }
    }
  }
}
```

### Windsurf

File: `~/.codeium/windsurf/mcp_config.json`.

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": [
        "mcp-secure-remote",
        "https://mcp.example.com/mcp",
        "--tls-cert", "/absolute/path/client.crt",
        "--tls-key",  "/absolute/path/client.key",
        "--tls-ca",   "/absolute/path/ca-bundle.pem"
      ]
    }
  }
}
```

### Cline (VS Code)

Open the Cline MCP panel → "Configure MCP Servers" or edit
`cline_mcp_settings.json` from its extension storage directly:

```json
{
  "mcpServers": {
    "example": {
      "command": "uvx",
      "args": [
        "mcp-secure-remote",
        "https://mcp.example.com/mcp",
        "--tls-cert", "/absolute/path/client.crt",
        "--tls-key",  "/absolute/path/client.key",
        "--tls-ca",   "/absolute/path/ca-bundle.pem"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Continue (VS Code / JetBrains)

File: `~/.continue/config.json` (or `config.yaml`).

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "uvx",
          "args": [
            "mcp-secure-remote",
            "https://mcp.example.com/mcp",
            "--tls-cert", "/absolute/path/client.crt",
            "--tls-key",  "/absolute/path/client.key",
            "--tls-ca",   "/absolute/path/ca-bundle.pem"
          ]
        }
      }
    ]
  }
}
```

### Zed

File: `~/.config/zed/settings.json`.

```json
{
  "context_servers": {
    "example": {
      "command": {
        "path": "uvx",
        "args": [
          "mcp-secure-remote",
          "https://mcp.example.com/mcp",
          "--tls-cert", "/absolute/path/client.crt",
          "--tls-key",  "/absolute/path/client.key",
          "--tls-ca",   "/absolute/path/ca-bundle.pem"
        ]
      }
    }
  }
}
```

### Generic MCP client

Any client that spawns stdio MCP servers works:

- `command`: `uvx`
- `args`: `["mcp-secure-remote", "<server-url>", …tls-flags]`
- Optional `env` block for `MCP_REMOTE_TLS_*` variables to keep secrets
  out of the args array.

## Testing your setup

The bundled `mcp-secure-remote-client` verifies the TLS handshake and
enumerates the server's capabilities — no real agent needed:

```bash
uvx mcp-secure-remote-client https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

Output: negotiated capabilities + lists of tools, resources, prompts.

Add `--debug` for per-message tracing.

For a fully local endpoint that actually requires client-certificate
authentication, see [LOCAL_MTLS_TESTING.md](./LOCAL_MTLS_TESTING.md).

## Security notes

- **HTTPS only by default.** `http://` URLs are refused unless
  `--allow-http` is explicitly set. Proxy additionally warns when mTLS
  flags are combined with `http://` because the client cert will not be
  sent.
- **Skip-verify prints a warning.** `--tls-insecure-skip-verify` disables
  server certificate validation; intended for local dev loops only.
- **Prefer env vars for passphrases.** Anything on the CLI may leak into
  process listings, shell history, or agent logs.
- **Proxy logs to stderr.** stdout is reserved for the MCP JSON-RPC stream.
- **No credential persistence.** Proxy does not write certs, keys, or
  tokens to disk.
- **Pin TLS 1.3** (`--tls-min-version TLSv1.3`) when the server supports
  it, to avoid downgrade-prone 1.2 cipher suites.

## Troubleshooting

**`CERTIFICATE_VERIFY_FAILED` / `unable to verify the first certificate`**
Point `--tls-ca` at the PEM bundle that signed the remote server's cert.
OS trust store alone is not enough for private CAs.

**`Hostname/IP does not match certificate's altnames`**
Set `--tls-servername` to the SAN the server cert presents.

**Private key malformed or passphrase error**
Ensure the key file is PEM-encoded. If encrypted, supply
`--tls-passphrase` (or `MCP_REMOTE_TLS_PASSPHRASE`).

**TLS handshake failure / `alert bad certificate`**
Server rejected your client cert. Check:
- Cert signed by a CA the server trusts.
- Key matches cert:
  `openssl x509 -noout -modulus -in client.crt | openssl md5`
  vs. `openssl rsa -noout -modulus -in client.key | openssl md5`.
- Intermediate chain present in `--tls-cert`.

**Agent shows "failed to start server" with no detail.**
Run the exact same command in a terminal to see stderr. Agents hide
subprocess stderr by default.

**Remote transport hangs.**
Try `--transport sse-only` or `--transport http-only` to isolate which
transport the server actually implements. Add `--debug`.

## Development

```bash
# clone and set up dev environment
git clone https://github.com/framedparadox/mcp-secure-remote.git
cd mcp-secure-remote
uv sync

# run directly from source
uv run mcp-secure-remote --help
uv run mcp-secure-remote-client --help

# typecheck
uv run mypy src/

# build wheel + sdist
uv build
```

## License

MIT — see [LICENSE](./LICENSE).
