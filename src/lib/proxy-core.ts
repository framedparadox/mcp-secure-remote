import type { Transport } from '@modelcontextprotocol/sdk/shared/transport.js'
import { debugLog, log } from './log.js'

export interface McpProxyOptions {
  transportToClient: Transport
  transportToServer: Transport
}

/**
 * Bidirectionally forward JSON-RPC messages between the local stdio transport
 * (transportToClient) and the remote HTTPS transport (transportToServer).
 *
 * When either side closes or errors, the opposite side is torn down so the
 * process can exit cleanly.
 */
export function mcpProxy({ transportToClient, transportToServer }: McpProxyOptions): void {
  let clientClosed = false
  let serverClosed = false

  transportToClient.onmessage = (message) => {
    debugLog('client -> server', summarizeMessage(message))
    transportToServer.send(message).catch((err) => {
      log('Error forwarding client message to server:', err)
    })
  }

  transportToServer.onmessage = (message) => {
    debugLog('server -> client', summarizeMessage(message))
    transportToClient.send(message).catch((err) => {
      log('Error forwarding server message to client:', err)
    })
  }

  transportToClient.onclose = () => {
    if (serverClosed) return
    clientClosed = true
    transportToServer.close().catch(() => {})
  }

  transportToServer.onclose = () => {
    if (clientClosed) return
    serverClosed = true
    transportToClient.close().catch(() => {})
  }

  transportToClient.onerror = (err) => log('Local transport error:', err)
  transportToServer.onerror = (err) => log('Remote transport error:', err)
}

function summarizeMessage(message: unknown): Record<string, unknown> {
  if (Array.isArray(message)) {
    return {
      kind: 'batch',
      count: message.length,
      entries: message.slice(0, 5).map(summarizeSingleMessage),
      truncated: message.length > 5,
    }
  }

  return summarizeSingleMessage(message)
}

function summarizeSingleMessage(message: unknown): Record<string, unknown> {
  if (!message || typeof message !== 'object') {
    return { kind: typeof message }
  }

  const record = message as Record<string, unknown>
  const id = typeof record.id === 'string' || typeof record.id === 'number' || record.id === null ? record.id : undefined
  const method = typeof record.method === 'string' ? record.method : undefined
  const error = record.error && typeof record.error === 'object' ? (record.error as Record<string, unknown>) : undefined
  const errorCode = typeof error?.code === 'number' || typeof error?.code === 'string' ? error.code : undefined

  return {
    kind: messageKind(record),
    id,
    method,
    hasParams: Object.hasOwn(record, 'params'),
    hasResult: Object.hasOwn(record, 'result'),
    hasError: Object.hasOwn(record, 'error'),
    errorCode,
  }
}

function messageKind(message: Record<string, unknown>): string {
  if (Object.hasOwn(message, 'error')) return 'error'
  if (Object.hasOwn(message, 'result')) return 'response'
  if (typeof message.method === 'string' && Object.hasOwn(message, 'id')) return 'request'
  if (typeof message.method === 'string') return 'notification'
  return 'unknown'
}
