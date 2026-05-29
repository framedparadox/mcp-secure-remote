# ─── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY tsconfig.json tsup.config.ts ./
COPY src/ ./src/
RUN npm run build

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM node:22-alpine AS runtime

WORKDIR /app

# Install production dependencies only
COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

# TLS/mTLS is configured entirely via environment variables at runtime:
#   MCP_REMOTE_TLS_CERT       – path to PEM client certificate
#   MCP_REMOTE_TLS_KEY        – path to PEM private key
#   MCP_REMOTE_TLS_CA         – path to PEM CA bundle
#   MCP_REMOTE_TLS_PFX        – path to PKCS#12 bundle (alternative to cert/key)
#   MCP_REMOTE_TLS_PASSPHRASE – private key passphrase
#   MCP_REMOTE_TLS_SERVERNAME – SNI override
#   MCP_REMOTE_TLS_MIN_VERSION – TLSv1.2 or TLSv1.3
#   MCP_REMOTE_TLS_INSECURE   – set to "true" to skip server cert validation (dev only)
#
# Example:
#   docker run -i \
#     -e MCP_REMOTE_TLS_CERT=/run/secrets/client.crt \
#     -e MCP_REMOTE_TLS_KEY=/run/secrets/client.key \
#     --mount type=secret,id=client.crt \
#     --mount type=secret,id=client.key \
#     mcp-secure-remote https://your-mcp-server.example.com

# Default: run the proxy. Override entrypoint to run the client instead.
ENTRYPOINT ["node", "dist/proxy.js"]
