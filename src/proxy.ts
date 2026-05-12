/**
 * mcp-secure-remote proxy – stdio <-> remote MCP server bridge with mTLS support.
 *
 * Spawns as a local stdio MCP server and forwards traffic to a remote MCP
 * server over HTTPS. Client certificate authentication (mTLS) can be
 * configured via --tls-cert / --tls-key / --tls-ca (or the MCP_REMOTE_TLS_*
 * environment variables).
 */
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { parseCommandLineArgs, printUsage, sanitizeServerUrlForLog } from './lib/args.js'
import { debugLog, log, setDebug } from './lib/log.js'
import { connectToRemoteServer } from './lib/transport.js'
import { mcpProxy } from './lib/proxy-core.js'
import { sanitizeParsedArgsForLog } from './lib/sanitize.js'

async function main(): Promise<void> {
  let parsed
  try {
    parsed = parseCommandLineArgs(process.argv.slice(2))
  } catch (err) {
    log('Argument error:', err instanceof Error ? err.message : err)
    printUsage()
    process.exit(2)
  }

  setDebug(parsed.debug)
  const safeServerUrl = sanitizeServerUrlForLog(parsed.serverUrl)
  debugLog('parsed arguments', sanitizeParsedArgsForLog(parsed))

  const localTransport = new StdioServerTransport()

  const remoteTransport = await connectToRemoteServer({
    serverUrl: parsed.serverUrl,
    headers: parsed.headers,
    strategy: parsed.transportStrategy,
    mtls: parsed.mtls,
  })

  mcpProxy({ transportToClient: localTransport, transportToServer: remoteTransport })

  await localTransport.start()
  log(`Proxy established: stdio <-> ${safeServerUrl}`)

  let shuttingDown = false
  const shutdown = async (signal: NodeJS.Signals) => {
    if (shuttingDown) {
      log(`Received ${signal} again; forcing exit.`)
      process.exit(130)
    }
    shuttingDown = true
    log(`Received ${signal}; shutting down…`)
    await Promise.allSettled([remoteTransport.close(), localTransport.close()])
    process.exit(0)
  }
  process.on('SIGINT', () => void shutdown('SIGINT'))
  process.on('SIGTERM', () => void shutdown('SIGTERM'))
}


main().catch((err) => {
  log('Fatal error:', err)
  if (err instanceof Error && /self[- ]signed certificate|unable to verify/i.test(err.message)) {
    log(
      'TLS verification failed. If you are testing against a private CA, pass --tls-ca <path> ' +
        'to point at its bundle, or (for local dev only) --tls-insecure-skip-verify.',
    )
  }
  process.exit(1)
})
