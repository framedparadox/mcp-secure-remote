import { describe, expect, it, vi } from 'vitest'
import type { Transport } from '@modelcontextprotocol/sdk/shared/transport.js'
import { mcpProxy } from '../../src/lib/proxy-core.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTransport(): Transport & {
  sentMessages: unknown[]
  closed: boolean
  closeError?: Error
} {
  const t = {
    sentMessages: [] as unknown[],
    closed: false,
    closeError: undefined as Error | undefined,
    onmessage: undefined as ((msg: unknown) => void) | undefined,
    onclose: undefined as (() => void) | undefined,
    onerror: undefined as ((err: Error) => void) | undefined,
    send: vi.fn(async (msg: unknown) => {
      t.sentMessages.push(msg)
    }),
    close: vi.fn(async () => {
      if (t.closeError) throw t.closeError
      t.closed = true
    }),
    start: vi.fn(async () => {}),
  }
  return t
}

// ---------------------------------------------------------------------------
// Message forwarding
// ---------------------------------------------------------------------------
describe('mcpProxy – message forwarding', () => {
  it('forwards client messages to server', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    client.onmessage!({ jsonrpc: '2.0', method: 'ping', id: 1 })
    await vi.waitFor(() => server.sentMessages.length > 0)
    expect(server.sentMessages[0]).toMatchObject({ method: 'ping' })
  })

  it('forwards server messages to client', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    server.onmessage!({ jsonrpc: '2.0', result: {}, id: 1 })
    await vi.waitFor(() => client.sentMessages.length > 0)
    expect(client.sentMessages[0]).toMatchObject({ result: {} })
  })

  it('forwards multiple messages in sequence', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    for (let i = 0; i < 5; i++) {
      client.onmessage!({ id: i, method: 'tools/list' })
    }
    await vi.waitFor(() => server.sentMessages.length === 5)
    expect(server.sentMessages).toHaveLength(5)
  })

  it('logs error but does not throw when server.send fails', async () => {
    const client = makeTransport()
    const server = makeTransport()
    server.send.mockRejectedValueOnce(new Error('send failure'))
    const errSpy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    mcpProxy({ transportToClient: client, transportToServer: server })

    client.onmessage!({ method: 'ping', id: 1 })
    await vi.waitFor(() => errSpy.mock.calls.length > 0)
    const output = errSpy.mock.calls.map((c) => c[0]).join('')
    expect(output).toContain('Error forwarding client message to server')
  })

  it('logs error but does not throw when client.send fails', async () => {
    const client = makeTransport()
    const server = makeTransport()
    client.send.mockRejectedValueOnce(new Error('client send failure'))
    const errSpy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    mcpProxy({ transportToClient: client, transportToServer: server })

    server.onmessage!({ result: {}, id: 1 })
    await vi.waitFor(() => errSpy.mock.calls.length > 0)
    const output = errSpy.mock.calls.map((c) => c[0]).join('')
    expect(output).toContain('Error forwarding server message to client')
  })
})

// ---------------------------------------------------------------------------
// Close propagation
// ---------------------------------------------------------------------------
describe('mcpProxy – close propagation', () => {
  it('closes server when client closes first', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    client.onclose!()
    await vi.waitFor(() => server.close.mock.calls.length > 0)
    expect(server.close).toHaveBeenCalled()
  })

  it('closes client when server closes first', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    server.onclose!()
    await vi.waitFor(() => client.close.mock.calls.length > 0)
    expect(client.close).toHaveBeenCalled()
  })

  it('does not re-close server if it already closed', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    // server closes first
    server.onclose!()
    await vi.waitFor(() => client.close.mock.calls.length > 0)
    // now client's onclose fires (which it might in real teardown)
    client.onclose!()
    // server.close should not have been called again
    expect(server.close).not.toHaveBeenCalled()
  })

  it('does not re-close client if it already closed', async () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })

    client.onclose!()
    await vi.waitFor(() => server.close.mock.calls.length > 0)
    server.onclose!()
    expect(client.close).not.toHaveBeenCalled()
  })

  it('swallows errors from close when propagating', async () => {
    const client = makeTransport()
    const server = makeTransport()
    server.closeError = new Error('close failed')
    mcpProxy({ transportToClient: client, transportToServer: server })

    // Should not throw even if server.close() rejects
    expect(() => client.onclose!()).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Error handlers
// ---------------------------------------------------------------------------
describe('mcpProxy – error handlers', () => {
  it('sets onerror on client transport', () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })
    expect(client.onerror).toBeDefined()
    expect(typeof client.onerror).toBe('function')
  })

  it('sets onerror on server transport', () => {
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })
    expect(server.onerror).toBeDefined()
    expect(typeof server.onerror).toBe('function')
  })

  it('logs local transport errors to stderr', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })
    client.onerror!(new Error('local err'))
    const output = spy.mock.calls.map((c) => c[0]).join('')
    expect(output).toContain('Local transport error')
  })

  it('logs remote transport errors to stderr', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    const client = makeTransport()
    const server = makeTransport()
    mcpProxy({ transportToClient: client, transportToServer: server })
    server.onerror!(new Error('remote err'))
    const output = spy.mock.calls.map((c) => c[0]).join('')
    expect(output).toContain('Remote transport error')
  })
})
