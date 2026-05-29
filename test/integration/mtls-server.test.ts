/**
 * Integration tests against the local mock mTLS MCP server.
 *
 * The server (local-testing/dist/mock-mtls-server.js) must be pre-built.
 * These tests spawn it as a child process, wait for it to be ready, run
 * assertions, then shut it down.
 *
 * Certificates used are the pre-generated dev certs in certs/dev/.
 */

import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, type ChildProcess } from 'node:child_process'
import { fetch as undiciFetch, Agent as UndiciAgent } from 'undici'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { connectToRemoteServer } from '../../src/lib/transport.js'
import { Client } from '@modelcontextprotocol/sdk/client/index.js'

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const __dirname = dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = resolve(__dirname, '..', '..')
const CERT_DIR = resolve(PROJECT_ROOT, 'certs', 'dev')
const SERVER_SCRIPT = resolve(PROJECT_ROOT, 'local-testing', 'dist', 'mock-mtls-server.js')
const SERVER_URL = 'https://localhost:4433'
const MCP_URL = `${SERVER_URL}/mcp`

const CA = readFileSync(resolve(CERT_DIR, 'ca.crt'))
const CLIENT_CERT = readFileSync(resolve(CERT_DIR, 'client.crt'))
const CLIENT_KEY = readFileSync(resolve(CERT_DIR, 'client.key'))
const CLIENT_PFX = readFileSync(resolve(CERT_DIR, 'client.p12'))

// ---------------------------------------------------------------------------
// Server lifecycle
// ---------------------------------------------------------------------------

let serverProcess: ChildProcess

async function waitForServer(timeoutMs = 15_000): Promise<void> {
  const agent = new UndiciAgent({ connect: { ca: CA, cert: CLIENT_CERT, key: CLIENT_KEY, rejectUnauthorized: true } })
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const res = await undiciFetch(`${SERVER_URL}/health`, { dispatcher: agent } as Parameters<typeof undiciFetch>[1])
      if (res.ok) { await agent.close(); return }
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 150))
  }
  await agent.close()
  throw new Error('Server did not start within timeout')
}

beforeAll(async () => {
  serverProcess = spawn(process.execPath, [SERVER_SCRIPT], {
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env },
  })

  serverProcess.stderr?.on('data', (d: Buffer) => {
    process.stderr.write(`[mock-server] ${d.toString()}`)
  })

  await waitForServer()
}, 30_000)

afterAll(async () => {
  serverProcess?.kill('SIGTERM')
  await new Promise<void>((resolve) => {
    serverProcess?.on('exit', () => resolve())
    setTimeout(resolve, 3000)
  })
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMtlsAgent(opts?: { rejectUnauthorized?: boolean; useClientCert?: boolean }) {
  return new UndiciAgent({
    connect: {
      ca: CA,
      ...(opts?.useClientCert !== false
        ? { cert: CLIENT_CERT, key: CLIENT_KEY }
        : {}),
      rejectUnauthorized: opts?.rejectUnauthorized !== false,
    },
  })
}

// ---------------------------------------------------------------------------
// /health – basic connectivity & mTLS
// ---------------------------------------------------------------------------
describe('GET /health', () => {
  it('returns 200 ok with client cert', async () => {
    const agent = makeMtlsAgent({ useClientCert: true })
    const res = await undiciFetch(`${SERVER_URL}/health`, { dispatcher: agent } as Parameters<typeof undiciFetch>[1])
    expect(res.status).toBe(200)
    const body = await res.json() as { status: string; clientCN: string | null }
    expect(body.status).toBe('ok')
    await agent.close()
  })

  it('includes clientCN in /health response', async () => {
    const agent = makeMtlsAgent({ useClientCert: true })
    const res = await undiciFetch(`${SERVER_URL}/health`, { dispatcher: agent } as Parameters<typeof undiciFetch>[1])
    const body = await res.json() as { clientCN: string | null }
    // The dev client cert has a CN — it should not be null
    expect(body.clientCN).not.toBeNull()
    await agent.close()
  })

  it('rejects connections without a client cert', async () => {
    const agent = new UndiciAgent({ connect: { ca: CA, rejectUnauthorized: true } })
    await expect(
      undiciFetch(`${SERVER_URL}/health`, { dispatcher: agent } as Parameters<typeof undiciFetch>[1]),
    ).rejects.toThrow()
    await agent.close()
  })

  it('rejects connections that do not trust the server CA', async () => {
    const agent = new UndiciAgent({
      connect: { cert: CLIENT_CERT, key: CLIENT_KEY, rejectUnauthorized: true },
    })
    await expect(
      undiciFetch(`${SERVER_URL}/health`, { dispatcher: agent } as Parameters<typeof undiciFetch>[1]),
    ).rejects.toThrow()
    await agent.close()
  })
})

// ---------------------------------------------------------------------------
// /unknown – 404 path
// ---------------------------------------------------------------------------
describe('GET /unknown-path', () => {
  it('returns 404', async () => {
    const agent = makeMtlsAgent()
    const res = await undiciFetch(`${SERVER_URL}/unknown-path`, { dispatcher: agent } as Parameters<typeof undiciFetch>[1])
    expect(res.status).toBe(404)
    await agent.close()
  })
})

// ---------------------------------------------------------------------------
// MCP JSON-RPC over mTLS – using connectToRemoteServer
// ---------------------------------------------------------------------------
describe('MCP over mTLS – cert+key', () => {
  async function makeClient() {
    const transport = await connectToRemoteServer({
      serverUrl: MCP_URL,
      headers: {},
      strategy: 'http-first',
      mtls: {
        certPath: resolve(CERT_DIR, 'client.crt'),
        keyPath: resolve(CERT_DIR, 'client.key'),
        caPath: resolve(CERT_DIR, 'ca.crt'),
      },
      autoStart: false,
    })
    const client = new Client({ name: 'test-client', version: '0.0.1' }, { capabilities: {} })
    await client.connect(transport)
    return client
  }

  it('connects and retrieves server capabilities', async () => {
    const client = await makeClient()
    const caps = client.getServerCapabilities()
    expect(caps).toBeDefined()
    await client.close()
  }, 15_000)

  it('lists tools – echo, get-time, add', async () => {
    const client = await makeClient()
    const { tools } = await client.listTools()
    const names = tools.map((t) => t.name)
    expect(names).toContain('echo')
    expect(names).toContain('get-time')
    expect(names).toContain('add')
    await client.close()
  }, 15_000)

  it('calls echo tool and gets response', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'echo', arguments: { message: 'hello mTLS' } })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toBe('Echo: hello mTLS')
    await client.close()
  }, 15_000)

  it('calls add tool with two numbers', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'add', arguments: { a: 7, b: 3 } })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toBe('10')
    await client.close()
  }, 15_000)

  it('calls get-time tool and returns ISO date string', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'get-time', arguments: {} })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
    await client.close()
  }, 15_000)

  it('echo handles empty string', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'echo', arguments: { message: '' } })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toBe('Echo: ')
    await client.close()
  }, 15_000)

  it('echo handles special characters', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'echo', arguments: { message: 'héllo "wörld" & <tags>' } })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toBe('Echo: héllo "wörld" & <tags>')
    await client.close()
  }, 15_000)

  it('add with negative numbers', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'add', arguments: { a: -5, b: 3 } })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toBe('-2')
    await client.close()
  }, 15_000)

  it('add with decimals', async () => {
    const client = await makeClient()
    const result = await client.callTool({ name: 'add', arguments: { a: 1.5, b: 2.5 } })
    const text = (result.content as Array<{ type: string; text: string }>)[0]?.text
    expect(text).toBe('4')
    await client.close()
  }, 15_000)

  it('multiple sequential tool calls on same connection', async () => {
    const client = await makeClient()
    const r1 = await client.callTool({ name: 'echo', arguments: { message: 'first' } })
    const r2 = await client.callTool({ name: 'add', arguments: { a: 1, b: 2 } })
    expect((r1.content as Array<{ text: string }>)[0].text).toBe('Echo: first')
    expect((r2.content as Array<{ text: string }>)[0].text).toBe('3')
    await client.close()
  }, 15_000)
})

// ---------------------------------------------------------------------------
// MCP over mTLS – PFX (PKCS#12) bundle
// ---------------------------------------------------------------------------
describe('MCP over mTLS – pfx bundle', () => {
  it('connects and lists tools using PFX (no passphrase)', async () => {
    const transport = await connectToRemoteServer({
      serverUrl: MCP_URL,
      headers: {},
      strategy: 'http-first',
      mtls: {
        pfxPath: resolve(CERT_DIR, 'client.p12'),
        passphrase: '',
        caPath: resolve(CERT_DIR, 'ca.crt'),
      },
      autoStart: false,
    })
    const client = new Client({ name: 'pfx-test', version: '0.0.1' }, { capabilities: {} })
    await client.connect(transport)
    const { tools } = await client.listTools()
    expect(tools.map((t) => t.name)).toContain('echo')
    await client.close()
  }, 15_000)
})

// ---------------------------------------------------------------------------
// Transport strategy variants
// ---------------------------------------------------------------------------
describe('MCP – transport strategy http-only', () => {
  it('connects with http-only strategy', async () => {
    const transport = await connectToRemoteServer({
      serverUrl: MCP_URL,
      headers: {},
      strategy: 'http-only',
      mtls: {
        certPath: resolve(CERT_DIR, 'client.crt'),
        keyPath: resolve(CERT_DIR, 'client.key'),
        caPath: resolve(CERT_DIR, 'ca.crt'),
      },
      autoStart: false,
    })
    const client = new Client({ name: 'http-only-test', version: '0.0.1' }, { capabilities: {} })
    await client.connect(transport)
    const caps = client.getServerCapabilities()
    expect(caps).toBeDefined()
    await client.close()
  }, 15_000)
})

// ---------------------------------------------------------------------------
// Connection failure scenarios
// ---------------------------------------------------------------------------
describe('connectToRemoteServer – failure scenarios', () => {
  it('throws when connecting without client cert (mTLS required)', async () => {
    // Server requires client cert; TLS handshake fails when client.connect() is called
    const transport = await connectToRemoteServer({
      serverUrl: MCP_URL,
      headers: {},
      strategy: 'http-only',
      mtls: {
        caPath: resolve(CERT_DIR, 'ca.crt'),
        // deliberately no cert/key
      },
      autoStart: false,
    })
    const client = new Client({ name: 'no-cert', version: '0.0.1' }, { capabilities: {} })
    await expect(client.connect(transport)).rejects.toThrow()
  }, 15_000)

  it('throws when not trusting server CA and rejectUnauthorized is true', async () => {
    // No caPath — default system CAs won't trust our private CA
    const transport = await connectToRemoteServer({
      serverUrl: MCP_URL,
      headers: {},
      strategy: 'http-only',
      mtls: {
        certPath: resolve(CERT_DIR, 'client.crt'),
        keyPath: resolve(CERT_DIR, 'client.key'),
      },
      autoStart: false,
    })
    const client = new Client({ name: 'no-ca', version: '0.0.1' }, { capabilities: {} })
    await expect(client.connect(transport)).rejects.toThrow()
  }, 15_000)
})
