# mcp-secure-remote

A stdio ↔ remote bridge for the [Model Context Protocol](https://modelcontextprotocol.io)
with first-class **mTLS (mutual TLS) client-certificate authentication**.

One repository. Two runtimes. Same CLI.

| Runtime | Install / run | Registry | Bins |
| --- | --- | --- | --- |
| **Node.js ≥ 22.19** | `npx mcp-secure-remote …` | [npm](https://www.npmjs.com/package/mcp-secure-remote) | `mcp-secure-remote`, `mcp-secure-remote-client` |
| **Python ≥ 3.10** | `uvx mcp-secure-remote …` | [PyPI](https://pypi.org/project/mcp-secure-remote/) | `mcp-secure-remote`, `mcp-secure-remote-client` |

Both packages accept the same flags, environment variables, and positional
`<server-url>`. Pick whichever launcher your agent already has.

Works with Claude Desktop, Claude Code, Cursor, Windsurf, Cline, Continue,
Zed, VS Code MCP extensions, and any custom client that speaks MCP stdio.

---

## Contents

1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
3. [Two runtimes, one CLI](#two-runtimes-one-cli)
4. [Prerequisites](#prerequisites)
5. [Install](#install)
6. [Generate or obtain client certificates](#generate-or-obtain-client-certificates)
7. [Local mTLS lab](#local-mtls-lab)
8. [Quick start](#quick-start)
9. [CLI parameters](#cli-parameters)
10. [Environment variables](#environment-variables)
11. [Transport negotiation](#transport-negotiation)
12. [SNI and hostname overrides](#sni-and-hostname-overrides)
13. [AI agent / IDE integration](#ai-agent--ide-integration)
    - [Claude Desktop](#claude-desktop)
    - [Claude Code (CLI)](#claude-code-cli)
    - [Cursor](#cursor)
    - [Windsurf](#windsurf)
    - [Cline (VS Code)](#cline-vs-code)
    - [Continue (VS Code / JetBrains)](#continue-vs-code--jetbrains)
    - [Zed](#zed)
    - [Generic MCP client](#generic-mcp-client)
14. [Testing your setup](#testing-your-setup)
15. [Security notes](#security-notes)
16. [Troubleshooting](#troubleshooting)
17. [Docker](#docker)
18. [Development](#development)
19. [Publishing](#publishing)
20. [Repository layout](#repository-layout)
21. [License](#license)

---

## What it does

`mcp-secure-remote` starts as a **local stdio MCP server**. Your AI agent
already knows how to spawn that. The proxy then forwards every JSON-RPC
message to a **remote MCP server over HTTPS**, presenting a client
certificate on the TLS handshake.

There is no OAuth dance, no bearer token on the wire, and no shared API
key. The remote server authenticates the caller with the certificate you
provisioned.

```mermaid
flowchart LR
  subgraph local [Your machine]
    agent[MCP client]
    proxy[mcp-secure-remote]
  end
  subgraph remote [Remote host]
    server[Remote MCP server]
  end
  agent -->|"stdio JSON-RPC"| proxy
  proxy -->|"HTTPS + client cert"| server
  server -->|"HTTPS + server cert"| proxy
  proxy -->|"stdio JSON-RPC"| agent
```

The remote MCP implementation can be any language. This proxy only sees
HTTPS and JSON-RPC.

Two binaries ship in both packages:

| Binary | Role |
| --- | --- |
| `mcp-secure-remote` | Long-lived stdio ↔ remote proxy for agents |
| `mcp-secure-remote-client` | One-shot probe: handshake, then list tools / resources / prompts |

---

## How it works

1. The agent launches `mcp-secure-remote` (via `npx` or `uvx`) as a local
   subprocess and talks to it over **stdio**.
2. The Node package builds an **undici** HTTPS dispatcher. The Python
   package builds an **httpx** / **httpx2** client (whichever the installed
   MCP SDK expects). Both are seeded with your client cert, private key,
   and trusted CA bundle.
3. The proxy opens **Streamable HTTP** or **SSE** to the remote URL
   (see [Transport negotiation](#transport-negotiation)). The TLS
   handshake presents the client cert. The server must accept it before
   any MCP session starts.
4. JSON-RPC frames flow both ways. Proxy logs go to **stderr** so stdout
   stays a clean MCP stream.

```mermaid
sequenceDiagram
  participant Agent as MCP_client
  participant Proxy as mcp_secure_remote
  participant Remote as Remote_MCP
  Agent->>Proxy: spawn stdio
  Agent->>Proxy: JSON-RPC request
  Proxy->>Remote: TLS ClientHello plus SNI
  Remote-->>Proxy: server certificate
  Proxy->>Remote: client certificate
  Note over Proxy,Remote: mTLS established
  Proxy->>Remote: Streamable HTTP or SSE
  Remote-->>Proxy: JSON-RPC response
  Proxy-->>Agent: JSON-RPC response on stdout
```

---

## Two runtimes, one CLI

```mermaid
flowchart TB
  repo[Git repo]
  repo --> npmMeta[package.json]
  repo --> pyMeta[pyproject.toml]
  npmMeta --> npmReg[npm registry]
  pyMeta --> pypi[PyPI]
  npmReg --> npx["npx mcp-secure-remote"]
  pypi --> uvx["uvx mcp-secure-remote"]
  npx --> sameCli[Same flags and MCP_REMOTE_TLS_* env]
  uvx --> sameCli
```

| | Node | Python |
| --- | --- | --- |
| Sources | `src/*.ts`, `src/lib/` | `src/mcp_secure_remote/` |
| HTTP stack | `@modelcontextprotocol/sdk` + `undici` | `mcp` + `httpx` / `httpx2` |
| TLS | Node `tls` / undici `Agent` | `ssl.SSLContext` (SNI override on `wrap_socket` / `wrap_bio`) |
| Tests | Vitest in `test/unit/` | pytest in `tests/` |
| Build output | `dist/` | `dist-py/` |
| Default Docker target | `npm` | `--target python` |

You do **not** need both runtimes installed. Agents typically use one.

---

## Prerequisites

Pick **one** runtime:

- **Node.js ≥ 22.19** and npm / `npx`
- **Python ≥ 3.10** and [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
  (`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS/Linux).
  `pip` also works if you prefer a venv.

Also required for any runtime:

- A **client certificate + private key** issued by a CA the remote MCP
  server trusts, **or** a PKCS#12 (`.pfx` / `.p12`) bundle
- The **server CA bundle** if the remote cert is not in the OS trust store
  (almost always true for private / corporate CAs)
- The remote MCP URL, usually `https://host/mcp` or `https://host/sse`

---

## Install

### Node (npm / npx)

```bash
# ephemeral — recommended in agent configs (always latest compatible)
npx mcp-secure-remote --help

# global
npm install -g mcp-secure-remote
mcp-secure-remote --help

# from this repo
git clone https://github.com/framedparadox/mcp-secure-remote.git
cd mcp-secure-remote
npm install
npm run build
node dist/proxy.js --help
```

`npx github:framedparadox/mcp-secure-remote` also works because
`package.json` lives at the repo root.

### Python (uv / uvx / pip)

```bash
# ephemeral isolated env from PyPI
uvx mcp-secure-remote --help

# persistent uv tool
uv tool install mcp-secure-remote
mcp-secure-remote --help

# pip / venv
python -m pip install mcp-secure-remote

# from this repo
uv sync --extra dev
uv run mcp-secure-remote --help
```

`uvx --from git+https://github.com/framedparadox/mcp-secure-remote mcp-secure-remote`
works because `pyproject.toml` lives at the repo root.

---

## Generate or obtain client certificates

If your platform team already issues client certs, skip to
[Quick start](#quick-start). For a throw-away local CA + client pair:

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

Configure the remote MCP server to **require** client certs signed by
`ca.crt`. Point this proxy at `client.crt` + `client.key` + the server's
CA bundle (often the same `ca.crt` in a lab).

Prefer the repo helper if you also want a **server** cert, PKCS#12 bundle,
and localhost SANs — see [Local mTLS lab](#local-mtls-lab).

---

## Local mTLS lab

This repo ships a complete loopback lab. Nothing in `certs/` is committed
(`.gitignore` covers `*.crt`, `*.key`, `*.p12`, `certs/*`).

### 1. Generate materials

```bash
scripts/generate_dev_mtls_certs.sh            # writes certs/dev/
scripts/generate_dev_mtls_certs.sh certs/lab  # custom output dir
```

Environment overrides:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DAYS` | `365` | Certificate lifetime |
| `P12_PASSPHRASE` | `dev-password` | Passphrase for `client.p12` |

The script refuses to overwrite an existing tree. Delete the directory or
pick another path.

Outputs in the target directory:

| File | Role |
| --- | --- |
| `ca.crt` / `ca.key` | Dev CA (trust this as `--tls-ca`) |
| `server.crt` / `server.key` | Server identity for `localhost`, `127.0.0.1`, `::1` |
| `client.crt` / `client.key` | Client identity (`clientAuth` EKU) |
| `client.p12` | PKCS#12 alternative to cert + key |

### 2. Run the mock server

Requires the generated cert dir and Python deps (`uv sync --extra dev`
or `pip install mcp uvicorn`).

```bash
# Streamable HTTP on https://localhost:8443/mcp
scripts/mock_mtls_mcp_server.py --cert-dir certs/dev

# SSE instead
scripts/mock_mtls_mcp_server.py --cert-dir certs/dev --transport sse
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8443` | Bind port |
| `--cert-dir` | `certs/dev` | Must contain `ca.crt`, `server.crt`, `server.key` |
| `--transport` | `streamable-http` | `streamable-http` or `sse` |
| `--mcp-path` | `/mcp` | Streamable HTTP path |
| `--sse-path` | `/sse` | SSE path |
| `--message-path` | `/messages/` | SSE message path |

The mock **requires** a client cert signed by that CA (`ssl.CERT_REQUIRED`).
It exposes `ping`, `echo`, resource `mock://mtls/status`, and `GET /healthz`.

### 3. Probe it

The mock presents a `localhost` SAN. If you connect via `127.0.0.1`,
set `--tls-servername localhost`.

```bash
npx mcp-secure-remote-client https://127.0.0.1:8443/mcp \
  --allow-private-urls \
  --tls-cert certs/dev/client.crt \
  --tls-key  certs/dev/client.key \
  --tls-ca   certs/dev/ca.crt \
  --tls-servername localhost

uvx mcp-secure-remote-client https://127.0.0.1:8443/mcp \
  --allow-private-urls \
  --tls-cert certs/dev/client.crt \
  --tls-key  certs/dev/client.key \
  --tls-ca   certs/dev/ca.crt \
  --tls-servername localhost \
  --debug
```

You should see capabilities plus the `ping` / `echo` tools.

---

## Quick start

Cert + key (Node):

```bash
npx mcp-secure-remote https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

Same flags on Python:

```bash
uvx mcp-secure-remote https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

PKCS#12:

```bash
npx mcp-secure-remote https://mcp.example.com/mcp \
  --tls-pfx       ./certs/client.p12 \
  --tls-passphrase "$P12_PASSPHRASE" \
  --tls-ca        ./certs/ca-bundle.pem
```

Prefer the env var for the passphrase so it does not appear in `ps`:

```bash
export MCP_REMOTE_TLS_PFX=./certs/client.p12
export MCP_REMOTE_TLS_PASSPHRASE='…'
export MCP_REMOTE_TLS_CA=./certs/ca-bundle.pem
uvx mcp-secure-remote https://mcp.example.com/mcp
```

Force SSE and pin TLS 1.3:

```bash
uvx mcp-secure-remote https://mcp.example.com/sse \
  --transport sse-only \
  --tls-min-version TLSv1.3 \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

Connect to an IP whose certificate SAN is a DNS name:

```bash
npx mcp-secure-remote https://192.0.2.10/mcp \
  --tls-servername mcp.internal.example \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

Extra headers (repeatable):

```bash
npx mcp-secure-remote https://mcp.example.com/mcp \
  --header "X-Tenant: acme" \
  --header "X-Request-Id: local-debug" \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

---

## CLI parameters

Usage (both binaries):

```text
mcp-secure-remote <server-url> [options]
mcp-secure-remote-client <server-url> [options]
```

`<server-url>` is required and positional. Everything else is a named
flag. Node and Python accept the same arguments.

### General

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `<server-url>` | URL | — | **Required.** Remote MCP endpoint. Must be `https://…` unless `--allow-http` is set. No userinfo (`user:pass@`). |
| `--header "Name: value"` | string, repeatable | — | Extra HTTP header on every outbound request. Name must be an RFC 7230 token. Value must not contain CR, LF, or NUL. |
| `--transport <strategy>` | enum | `http-first` | `http-first`, `sse-first`, `http-only`, `sse-only`. See [Transport negotiation](#transport-negotiation). |
| `--allow-http` | boolean | `false` | Permit `http://` URLs. mTLS is meaningless over plain HTTP; the proxy warns if TLS flags are also set. |
| `--debug` | boolean | `false` | Verbose logging to stderr: redacted args, transport choice, per-message metadata (not payloads). |
| `--allow-private-urls` | boolean | `false` | Allow localhost and RFC1918/link-local targets. Required for the local mTLS lab. |
| `--max-message-bytes <n>` | number | `10485760` | Drop JSON-RPC messages larger than *n* bytes (env `MCP_REMOTE_MAX_MESSAGE_BYTES`). |
| `--auth-bearer <token>` | string | — | Set `Authorization: Bearer <token>`. |
| `--auth-basic <user:pass>` | string | — | Set `Authorization: Basic` (base64). |
| `--api-key <key>` | string | — | Set an API key header (default name `X-Api-Key`). |
| `--api-key-header <name>` | string | `X-Api-Key` | Override the API key header name. |
| `-h`, `--help` | boolean | — | Print usage to stderr and exit `0`. |
| `-V`, `--version` | boolean | — | Print `mcp-secure-remote <version>` to stdout and exit `0`. |

### mTLS / TLS

| Flag | Type | Default | Description |
| --- | --- | --- | --- |
| `--tls-cert <path>` | path | — | PEM client certificate (leaf, optionally followed by intermediates). |
| `--tls-key <path>` | path | — | PEM private key matching `--tls-cert`. Required together with `--tls-cert`. |
| `--tls-ca <path>` | path | — | PEM CA bundle used to verify the **server**. Required for private CAs. |
| `--tls-pfx <path>` | path | — | PKCS#12 (`.pfx` / `.p12`). Mutually exclusive with `--tls-cert` / `--tls-key`. |
| `--tls-passphrase <value>` | string | — | Passphrase for the key or PFX. Prefer `MCP_REMOTE_TLS_PASSPHRASE`. |
| `--tls-servername <name>` | string | URL hostname | SNI **and** certificate hostname. Use for IP URLs, split DNS, or SAN mismatch. |
| `--tls-min-version <ver>` | enum | TLS 1.2 floor | `TLSv1.2` or `TLSv1.3`. The proxy never goes below TLS 1.2 even if you omit this. |
| `--tls-pin-sha256 <pin>` | string, repeatable | — | SHA-256 SPKI pin for the server leaf cert (base64, hex, or `sha256/…`). Incompatible with `--tls-insecure-skip-verify`. |
| `--tls-insecure-skip-verify`, `--tls-no-verify` | boolean | `false` | Disable server cert validation. **Dev only.** Prints a warning. |

### Parameter rules

- `--tls-cert` and `--tls-key` must appear together.
- `--tls-pfx` cannot combine with `--tls-cert` / `--tls-key`.
- `--tls-passphrase` requires a PFX or a cert/key pair.
- `--allow-http` is required for any `http://` URL.
- Unknown `--flags` fail parse with exit code **2**.
- Argument errors exit **2**. Runtime errors exit **1**. Interrupt exits **0**.
- `https://user:pass@host/mcp` is rejected. Use `--header` or env instead.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success, `--help`, `--version`, or clean interrupt |
| `1` | Runtime / TLS / transport failure |
| `2` | CLI parse error (missing URL, bad flag, bad header) |

---

## Environment variables

Every TLS flag has an env-var fallback so secrets stay out of `ps`, shell
history, and agent config files.

| Variable | Equivalent flag | Values |
| --- | --- | --- |
| `MCP_REMOTE_TLS_CERT` | `--tls-cert` | path |
| `MCP_REMOTE_TLS_KEY` | `--tls-key` | path |
| `MCP_REMOTE_TLS_CA` | `--tls-ca` | path |
| `MCP_REMOTE_TLS_PFX` | `--tls-pfx` | path |
| `MCP_REMOTE_TLS_PASSPHRASE` | `--tls-passphrase` | string |
| `MCP_REMOTE_TLS_SERVERNAME` | `--tls-servername` | string |
| `MCP_REMOTE_TLS_MIN_VERSION` | `--tls-min-version` | `TLSv1.2` or `TLSv1.3` (invalid values fail parse) |
| `MCP_REMOTE_TLS_INSECURE` | `--tls-insecure-skip-verify` | `1` / `true` / `yes` (case-insensitive) disables verify |
| `MCP_REMOTE_TLS_PIN_SHA256` | `--tls-pin-sha256` | comma-separated SPKI pins |
| `MCP_REMOTE_MAX_MESSAGE_BYTES` | `--max-message-bytes` | integer byte limit |
| `MCP_REMOTE_AUTH_BEARER` | `--auth-bearer` | Bearer token (sent as `Authorization: Bearer …`) |
| `MCP_REMOTE_AUTH_BASIC` | `--auth-basic` | `username:password` (sent as HTTP Basic) |
| `MCP_REMOTE_API_KEY` | `--api-key` | API key value |
| `MCP_REMOTE_API_KEY_HEADER` | `--api-key-header` | Header name (default `X-Api-Key`) |

**Precedence:** an explicit CLI flag always wins over the env var. For headers,
`--header` overrides auth env vars when both target the same header name.

Empty env values are treated as unset.

### Application-layer auth (beyond mTLS)

Many remotes combine **mTLS at the TLS layer** with **Bearer tokens, HTTP Basic,
or API keys** at the HTTP layer. Use the auth flags/env vars above instead of
embedding secrets in the server URL (which is refused). These supplement — not
replace — client certificate authentication.

| Strategy | Flag / env | When to use |
| --- | --- | --- |
| **mTLS (client cert)** | `--tls-cert` / `--tls-key` / `--tls-pfx` | Primary auth; cert presented on TLS handshake |
| **Bearer token** | `--auth-bearer` / `MCP_REMOTE_AUTH_BEARER` | OAuth-style access tokens, JWT bearer |
| **HTTP Basic** | `--auth-basic` / `MCP_REMOTE_AUTH_BASIC` | Legacy basic-auth gateways |
| **API key header** | `--api-key` / `MCP_REMOTE_API_KEY` | Shared secret in a custom or standard header |
| **Custom headers** | `--header "Name: value"` | Any other application auth (tenant IDs, HMAC headers, etc.) |

**Not built in:** OAuth authorization-code flows, automatic token refresh, JWT
validation, or request signing (AWS SigV4).
Use your identity provider to mint tokens, then pass them via `--auth-bearer` or
`--header`. For server identity, use `--tls-ca` and/or `--tls-pin-sha256`.

---

## Transport negotiation

MCP remotes typically expose **Streamable HTTP** (`/mcp`) or **SSE**
(`/sse`). The `--transport` strategy controls which is tried first and
whether fallback is allowed.

```mermaid
flowchart TD
  start[connect_to_remote_server]
  start --> strategy{strategy}
  strategy -->|http-first| httpA[Try Streamable HTTP]
  strategy -->|sse-first| sseA[Try SSE]
  strategy -->|http-only| httpOnly[Try Streamable HTTP]
  strategy -->|sse-only| sseOnly[Try SSE]
  httpA -->|ok| done[Use that transport]
  httpA -->|fail| sseB[Try SSE]
  sseA -->|ok| done
  sseA -->|fail| httpB[Try Streamable HTTP]
  sseB -->|ok| done
  sseB -->|fail| fail[Raise last error]
  httpB -->|ok| done
  httpB -->|fail| fail
  httpOnly -->|ok| done
  httpOnly -->|fail| fail
  sseOnly -->|ok| done
  sseOnly -->|fail| fail
```

| Strategy | First try | Fallback |
| --- | --- | --- |
| `http-first` (default) | Streamable HTTP | SSE |
| `sse-first` | SSE | Streamable HTTP |
| `http-only` | Streamable HTTP | none |
| `sse-only` | SSE | none |

Fallback only happens when the **first** transport fails to connect. If
the session is already up and later errors, the proxy does not silently
switch transports.

If the remote hangs with no useful error, pin `--transport http-only` or
`--transport sse-only` and add `--debug`.

---

## SNI and hostname overrides

`--tls-servername` exists for the common lab/prod mismatch: you connect
to an IP or internal hostname, but the server certificate SAN is a
different DNS name.

On **Node**, the value is passed as undici / `tls` `servername` (SNI +
verification).

On **Python**, `ssl.SSLContext` has no `servername` field, so the proxy
rewrites `wrap_socket` / `wrap_bio` to force that hostname for both SNI
and certificate matching. Behavior matches Node.

Example: mock server cert is `CN=localhost` with SAN `localhost`. Client
URL is `https://127.0.0.1:8443/mcp`:

```bash
--tls-servername localhost
```

Without the override you typically get a hostname / IP mismatch error.

---

## AI agent / IDE integration

Every agent below launches the proxy as a local stdio MCP server. Only
the config file format changes.

**Use absolute paths.** Agents do not inherit your shell cwd.

`npx` and `uvx` are interchangeable. To use Python, replace
`"command": "npx"` with `"command": "uvx"` and keep the same `args`.
Move passphrases into `env` whenever you can.

```mermaid
flowchart LR
  ide[IDE or agent]
  ide --> spawn[spawn command plus args]
  spawn --> npx["npx mcp-secure-remote …"]
  spawn --> uvx["uvx mcp-secure-remote …"]
  spawn --> docker["docker run -i …"]
  npx --> remote[Remote MCP]
  uvx --> remote
  docker --> remote
```

### Claude Desktop

File: `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

```json
{
  "mcpServers": {
    "example": {
      "command": "npx",
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

Python equivalent — same args, different launcher:

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

Restart Claude Desktop after editing.

### Claude Code (CLI)

```bash
claude mcp add example npx -- mcp-secure-remote \
  https://mcp.example.com/mcp \
  --tls-cert /absolute/path/client.crt \
  --tls-key  /absolute/path/client.key \
  --tls-ca   /absolute/path/ca-bundle.pem
```

```bash
claude mcp add example uvx -- mcp-secure-remote \
  https://mcp.example.com/mcp \
  --tls-cert /absolute/path/client.crt \
  --tls-key  /absolute/path/client.key \
  --tls-ca   /absolute/path/ca-bundle.pem
```

Or in project `.mcp.json` / `~/.claude.json`:

```json
{
  "mcpServers": {
    "example": {
      "command": "npx",
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
      "command": "npx",
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
      "command": "npx",
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

Cline reads `cline_mcp_settings.json` from its extension storage. Open
the Cline MCP panel → "Configure MCP Servers", or edit the file:

```json
{
  "mcpServers": {
    "example": {
      "command": "npx",
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
          "command": "npx",
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
        "path": "npx",
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

| Field | Value |
| --- | --- |
| `command` | `npx`, `uvx`, `docker`, `node`, or `mcp-secure-remote` after a global/tool install |
| `args` | `["mcp-secure-remote", "<server-url>", …flags]` (omit the package name when `command` is already the binary) |
| `env` | optional `MCP_REMOTE_TLS_*` map |

Docker as the command (stdio still works because of `-i`):

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

---

## Testing your setup

`mcp-secure-remote-client` verifies the TLS handshake and lists tools,
resources, and prompts. No agent required.

```bash
npx mcp-secure-remote-client https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem
```

```bash
uvx mcp-secure-remote-client https://mcp.example.com/mcp \
  --tls-cert ./certs/client.crt \
  --tls-key  ./certs/client.key \
  --tls-ca   ./certs/ca-bundle.pem \
  --debug
```

Expected output: negotiated capabilities, then sanitized names/descriptions
for tools, resources, and prompts.

For a local server that actually requires a client cert, use the
[Local mTLS lab](#local-mtls-lab).

---

## Security notes

- **HTTPS only by default.** `http://` (any casing) is refused unless
  `--allow-http` is set. Combining mTLS flags with `http://` warns: the
  client cert is not sent over plain HTTP.
- **Private hosts blocked by default.** Loopback, RFC1918, link-local, and
  cloud-metadata IPs are refused unless `--allow-private-urls` is set.
  Use that flag for the [local mTLS lab](#local-mtls-lab); production agents
  should omit it to reduce SSRF risk from agent configs.
- **CA pinning is exclusive.** When `--tls-ca` is set, server verification
  trusts **only** that PEM bundle — not the OS public CA store (Node and
  Python behave the same).
- **Redirects are rejected.** Outbound requests set `redirect: error`
  (Node) / `follow_redirects=False` (Python). Responses whose final URL
  leaves the pinned origin are also refused (Python response hook; Node
  post-fetch check).
- **Origin pinning.** Every outbound request is checked against the
  origin of `<server-url>` (scheme + host + port). A different origin is
  refused.
- **SNI override is not a verify bypass.** `--tls-servername` changes
  which name is sent and checked; it does not disable verification.
- **Skip-verify prints a warning.** `--tls-insecure-skip-verify` is for
  local loops only.
- **Header injection is rejected.** Header names must be RFC 7230 tokens.
  Values cannot contain CR, LF, or NUL.
- **Prefer env vars for passphrases and auth secrets.** CLI values leak
  into process listings, shell history, and some agent logs.
- **Debug logging redacts secrets.** Passphrases, bearer tokens, basic
  auth, API keys, and header **values** are not printed. Message traces log
  kind / id / method only — not tool arguments or results.
- **Embedded URL credentials are refused.** Userinfo can leak through
  `ps` and logs; use auth env vars or `--header` instead.
- **Malformed JSON-RPC is dropped.** Parse errors from stdio or the remote
  transport are logged and discarded instead of crashing the proxy.
- **Proxy logs to stderr.** stdout is reserved for MCP JSON-RPC.
- **Client output is terminal-sanitized.** Tool names, descriptions,
  resources, and prompts have ANSI / control characters stripped before
  they hit the terminal.
- **No credential persistence.** The proxy does not write certs, keys, or
  tokens to disk (Python PFX handling uses short-lived temp files that
  are zero-filled and unlinked).
- **TLS 1.2 floor.** Both runtimes enforce TLS 1.2+ even without
  `--tls-min-version`. Pin `TLSv1.3` when the server allows it.
- **Message size cap.** JSON-RPC messages larger than `--max-message-bytes`
  (default 10 MiB; env `MCP_REMOTE_MAX_MESSAGE_BYTES`) are dropped and
  logged — they are not forwarded across the stdio bridge.
- **TLS SPKI pinning.** Repeat `--tls-pin-sha256` (or env
  `MCP_REMOTE_TLS_PIN_SHA256`, comma-separated) to require the server leaf
  certificate public key to match a known SHA-256 SPKI pin (base64, hex, or
  `sha256/…`). Incompatible with `--tls-insecure-skip-verify`.

---

## Troubleshooting

**`self signed certificate in certificate chain` / `unable to verify the first certificate` / `CERTIFICATE_VERIFY_FAILED`**
Point `--tls-ca` at the PEM bundle that signed the **server** cert. The
OS trust store is not enough for private CAs.

**`Hostname/IP does not match certificate's altnames`**
Set `--tls-servername` to a SAN the server cert actually presents. Common
when the URL is an IP and the cert is `CN=localhost`.

**`error:0909006C:PEM routines:get_name:no start line` / private key malformed**
Key is not PEM, or it is encrypted. Supply `--tls-passphrase` or
`MCP_REMOTE_TLS_PASSPHRASE`.

**`ERR_SSL_SSLV3_ALERT_HANDSHAKE_FAILURE` / `alert bad certificate`**
The server rejected the **client** cert. Check:

- Cert is signed by a CA the server trusts
- Key matches cert:
  `openssl x509 -noout -modulus -in client.crt | openssl md5`
  vs.
  `openssl rsa -noout -modulus -in client.key | openssl md5`
- Intermediate chain is present in `--tls-cert` if the server needs it
- Cert has `clientAuth` EKU if the server requires it

**Agent shows "failed to start server" with no detail.**
Run the exact same command in a terminal. Agents hide subprocess stderr.

**Remote transport hangs.**
Try `--transport sse-only` or `--transport http-only`. Add `--debug`.

**`already started` in `mcp-secure-remote-client`.**
Upgrade. Older Node builds started the transport twice.

**`mcp streamable_http_client has an unrecognised signature`**
The installed `mcp` Python package is newer or older than the injection
paths this proxy knows. Upgrade `mcp-secure-remote`, or pin `mcp` to a
supported release. mcp 2.x is supported (httpx2 client, headers on the
client, not on the transport).

**`--help` should exit 0.**
If an old Python build exits 2 on `--help`, upgrade. Current builds treat
`SystemExit(0)` as success.

---

## Docker

The `Dockerfile` is multi-target. The **default** image is Node (same as
older npm-only releases). `--target python` installs the local package
with `pip install .` and runs as a non-root `mcp` user.

```mermaid
flowchart LR
  df[Dockerfile]
  df --> builder[npm-builder]
  builder --> npmRuntime[target npm]
  df --> pyRuntime[target python]
  npmRuntime --> defaultImg[default image]
```

**Build:**

```bash
# Node (default)
docker build -t mcp-secure-remote .
docker build --target npm -t mcp-secure-remote:npm .

# Python
docker build --target python -t mcp-secure-remote:python .
```

**Run the proxy** (plain HTTPS, no mTLS):

```bash
docker run -i mcp-secure-remote https://mcp.example.com/mcp
```

`-i` is required: the proxy speaks **stdin/stdout**.

**mTLS with Docker secrets** (preferred in production):

```bash
docker run -i \
  -e MCP_REMOTE_TLS_CERT=/run/secrets/client.crt \
  -e MCP_REMOTE_TLS_KEY=/run/secrets/client.key \
  -e MCP_REMOTE_TLS_CA=/run/secrets/ca-bundle.pem \
  --mount type=secret,id=client.crt \
  --mount type=secret,id=client.key \
  --mount type=secret,id=ca-bundle.pem \
  mcp-secure-remote https://mcp.example.com/mcp
```

**mTLS with a bind-mounted cert directory:**

```bash
docker run -i \
  -v /path/to/local/certs:/certs:ro \
  -e MCP_REMOTE_TLS_CERT=/certs/client.crt \
  -e MCP_REMOTE_TLS_KEY=/certs/client.key \
  -e MCP_REMOTE_TLS_CA=/certs/ca-bundle.pem \
  mcp-secure-remote https://mcp.example.com/mcp
```

No certs are baked into the image. Configure TLS only via
`MCP_REMOTE_TLS_*` or flags after the image name.

**Node client:**

```bash
docker run --rm \
  -v /path/to/local/certs:/certs:ro \
  -e MCP_REMOTE_TLS_CERT=/certs/client.crt \
  -e MCP_REMOTE_TLS_KEY=/certs/client.key \
  -e MCP_REMOTE_TLS_CA=/certs/ca-bundle.pem \
  --entrypoint node mcp-secure-remote dist/client.js \
  https://mcp.example.com/mcp
```

**Python client:**

```bash
docker run --rm \
  -v /path/to/local/certs:/certs:ro \
  -e MCP_REMOTE_TLS_CERT=/certs/client.crt \
  -e MCP_REMOTE_TLS_KEY=/certs/client.key \
  -e MCP_REMOTE_TLS_CA=/certs/ca-bundle.pem \
  --entrypoint mcp-secure-remote-client mcp-secure-remote:python \
  https://mcp.example.com/mcp
```

**Extra flags** go after the image name:

```bash
docker run -i mcp-secure-remote \
  https://mcp.example.com/mcp \
  --transport sse-only \
  --tls-min-version TLSv1.3 \
  --debug
```

### Compose

`docker compose up` builds the Node service. Python is a profile:

```bash
docker compose build
docker compose --profile python build
```

| Service | Profile | Image | Target |
| --- | --- | --- | --- |
| `mcp-secure-remote` | default | `mcp-secure-remote:local` | `npm` |
| `mcp-secure-remote-python` | `python` | `mcp-secure-remote:local-python` | `python` |

Both mount `${CERTS_DIR:-./certs/dev}` at `/certs:ro` and default the
`MCP_REMOTE_TLS_*` env vars. Override `CERTS_DIR` and the remote URL
`command` for a real host.

---

## Development

```text
.
├── package.json              # npm metadata + bins
├── pyproject.toml            # PyPI metadata + scripts
├── src/
│   ├── proxy.ts / client.ts  # Node entrypoints
│   ├── lib/                  # Node args, mtls, transport, sanitize
│   └── mcp_secure_remote/    # Python package
├── test/unit/                # Vitest
├── tests/                    # pytest
├── scripts/                  # local CA + mock mTLS server
├── Dockerfile                # multi-target npm | python
└── .github/workflows/        # ci, publish-npm, publish-py
```

Node artifacts go to `dist/`. Python artifacts go to `dist-py/` so
`npm run build` (tsup `clean: true`) cannot wipe wheels.

### Node

```bash
npm install
npm run typecheck
npm run test
npm run test:coverage
npm run test:watch
npm run test:unit
npm run build
npm run check:version
npm pack --dry-run
```

| Script | What it does |
| --- | --- |
| `npm run build` | tsup → `dist/proxy.js`, `dist/client.js` (shebang) |
| `npm run build:watch` | rebuild on change |
| `npm run typecheck` | `tsc --noEmit` (excludes `src/mcp_secure_remote`) |
| `npm test` | Vitest once |
| `npm run start:proxy` / `start:client` | run built bins |
| `npm run check:version` | Fail if `package.json`, lockfile, `pyproject.toml`, and runtime version strings drift |
| `prepack` / `prepublishOnly` | rebuild `dist/` before pack/publish (`prepublishOnly` also typechecks and tests) |

### Python

```bash
uv sync --extra dev
uv run mcp-secure-remote --help
uv run mcp-secure-remote-client --help
uv run --extra dev pytest tests/
uv build --out-dir dist-py
```

Without uv:

```bash
python -m pip install -e ".[dev]"
pytest tests/
python -m build --outdir dist-py
```

### Both

```bash
npm run test:all    # Node tests, then pytest via uv
npm run test:py
npm run build:py
```

### Packaging fences

| Artifact | Contains | Must not contain |
| --- | --- | --- |
| npm tarball (`files` whitelist) | `dist/`, README, LICENSE, `package.json` | `*.py`, `pyproject.toml`, `src/mcp_secure_remote/` |
| PyPI wheel | `mcp_secure_remote` | `*.ts`, `src/lib/`, `package.json` |
| PyPI sdist | Python package + tests + metadata | TypeScript, `__pycache__` |

CI re-checks those fences on every PR.

---

## Publishing

Both registries publish from **this same tree** when a GitHub Release is
**published** (or via `workflow_dispatch`).

| Workflow | Trigger | What it does |
| --- | --- | --- |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | pull_request; push to `release/npm`, `main`, `develop` | Version sync; Node typecheck/test/build + pack fence; Python 3.10–3.14 pytest; wheel/sdist/twine fence on 3.12 |
| [`.github/workflows/publish-npm.yml`](.github/workflows/publish-npm.yml) | release published | Node 22, `npm ci`, version sync, typecheck, test, build, pack fence, `npm publish --provenance` |
| [`.github/workflows/publish-py.yml`](.github/workflows/publish-py.yml) | release published | pytest matrix, `python -m build --outdir dist-py`, twine check, sdist/wheel fence, PyPI trusted publishing (OIDC) |

Keep `package.json` `version` and `pyproject.toml` `version` in sync
before tagging. `npm run check:version` (and CI) enforces that, plus the
runtime strings in `src/lib/version.ts` and `src/mcp_secure_remote/__init__.py`.

npm **0.0.1** / **0.0.2** and PyPI **0.0.1** / **0.0.2** are already on the
registries. The next release is **0.0.3** (this tree). Publishing happens
when a GitHub Release is published; workflows do not push to the registries
from this PR.

---

## Repository layout

| Path | Purpose |
| --- | --- |
| [`src/proxy.ts`](src/proxy.ts) / [`src/client.ts`](src/client.ts) | Node bins |
| [`src/lib/`](src/lib/) | Node args, logging, mTLS dispatcher, transport, sanitize |
| [`src/mcp_secure_remote/`](src/mcp_secure_remote/) | Python package (same responsibilities) |
| [`test/unit/`](test/unit/) | Vitest |
| [`tests/`](tests/) | pytest |
| [`scripts/generate_dev_mtls_certs.sh`](scripts/generate_dev_mtls_certs.sh) | Dev CA + server + client + P12 |
| [`scripts/check-version-sync.mjs`](scripts/check-version-sync.mjs) | Fail if npm / PyPI / runtime versions drift |
| [`scripts/mock_mtls_mcp_server.py`](scripts/mock_mtls_mcp_server.py) | Local HTTPS MCP that requires a client cert |
| [`Dockerfile`](Dockerfile) | `npm-builder` → `python` → `npm` (default) |
| [`docker-compose.yml`](docker-compose.yml) | Node service + optional `python` profile |
| [`MANIFEST.in`](MANIFEST.in) | PyPI sdist inclusions / exclusions |
| [`tsconfig.json`](tsconfig.json) | Compiles `src/**/*.ts` only |

---

## License

MIT — see [LICENSE](./LICENSE).
