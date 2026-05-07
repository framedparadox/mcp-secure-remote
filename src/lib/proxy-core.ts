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
    debugLog('client -> server', message)
    transportToServer.send(message).catch((err) => {
      log('Error forwarding client message to server:', err)
    })
  }

  transportToServer.onmessage = (message) => {
    debugLog('server -> client', message)
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
