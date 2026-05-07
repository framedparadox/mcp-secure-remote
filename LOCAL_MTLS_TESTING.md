# Local mTLS Testing

This repo includes a dev-only HTTPS MCP server that requires a client
certificate. Use it to verify that `mcp-secure-remote` can complete a real
mTLS handshake and talk to a remote MCP endpoint.

## 1. Generate local certificates

```bash
scripts/generate_dev_mtls_certs.sh
```

This creates:

- `certs/dev/ca.crt`: the local CA trusted by both client and server.
- `certs/dev/server.crt` and `certs/dev/server.key`: the HTTPS server identity for `localhost`.
- `certs/dev/client.crt` and `certs/dev/client.key`: the client certificate pair.
- `certs/dev/client.p12`: PKCS#12 client bundle with passphrase `dev-password`.

The generated files are ignored by git.

## 2. Start the mock mTLS MCP endpoint

```bash
python3 scripts/mock_mtls_mcp_server.py
```

Default endpoint:

```text
https://localhost:8443/mcp
```

The TLS listener requires a client certificate signed by `certs/dev/ca.crt`.

## 3. Verify the handshake and MCP capability listing

From another terminal:

```bash
PYTHONPATH=src python3 -m mcp_secure_remote.client \
  https://localhost:8443/mcp \
  --transport http-only \
  --tls-cert certs/dev/client.crt \
  --tls-key certs/dev/client.key \
  --tls-ca certs/dev/ca.crt
```

Expected result: the client connects and lists the mock `ping` and `echo`
tools plus the `mock://mtls/status` resource.

You can also smoke-test the TLS gate directly:

```bash
curl --cacert certs/dev/ca.crt \
  --cert certs/dev/client.crt \
  --key certs/dev/client.key \
  https://localhost:8443/healthz
```

Without `--cert` and `--key`, the TLS handshake should fail.

## Optional: test PKCS#12 client credentials

```bash
PYTHONPATH=src python3 -m mcp_secure_remote.client \
  https://localhost:8443/mcp \
  --transport http-only \
  --tls-pfx certs/dev/client.p12 \
  --tls-passphrase dev-password \
  --tls-ca certs/dev/ca.crt
```

## Optional: run the mock endpoint with SSE

```bash
python3 scripts/mock_mtls_mcp_server.py --transport sse
```

Then test:

```bash
PYTHONPATH=src python3 -m mcp_secure_remote.client \
  https://localhost:8443/sse \
  --transport sse-only \
  --tls-cert certs/dev/client.crt \
  --tls-key certs/dev/client.key \
  --tls-ca certs/dev/ca.crt
```
