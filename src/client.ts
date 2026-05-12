/**
 * mcp-secure-remote-client – standalone client for exercising a remote MCP server
 * over mTLS without running a stdio proxy. Useful for verifying certificate
 * configuration and listing the tools/resources/prompts exposed by the server.
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { parseCommandLineArgs, printUsage } from './lib/args.js'
import { debugLog, log, setDebug } from './lib/log.js'
import { connectToRemoteServer } from './lib/transport.js'
import { sanitizeParsedArgsForLog, sanitizeTerminalText } from './lib/sanitize.js'

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
  debugLog('parsed arguments', sanitizeParsedArgsForLog(parsed))

  const transport = await connectToRemoteServer({
    serverUrl: parsed.serverUrl,
    headers: parsed.headers,
    strategy: parsed.transportStrategy,
    mtls: parsed.mtls,
    autoStart: false,
  })

  const client = new Client(
    { name: 'mcp-secure-remote-client', version: '0.1.0' },
    { capabilities: {} },
  )

  try {
    await client.connect(transport)
    log('Connected.')

    const capabilities = client.getServerCapabilities() ?? {}
    log('Server capabilities:', JSON.stringify(capabilities))

    if (capabilities.tools) {
      const tools = await client.listTools()
      log(`Tools (${tools.tools.length}):`)
      for (const tool of tools.tools) {
        process.stdout.write(
          `  - ${sanitizeTerminalText(tool.name)}${tool.description ? ` – ${sanitizeTerminalText(tool.description)}` : ''}\n`,
        )
      }
    }
    if (capabilities.resources) {
      const resources = await client.listResources()
      log(`Resources (${resources.resources.length}):`)
      for (const res of resources.resources) {
        process.stdout.write(
          `  - ${sanitizeTerminalText(res.uri)}${res.name ? ` (${sanitizeTerminalText(res.name)})` : ''}\n`,
        )
      }
    }
    if (capabilities.prompts) {
      const prompts = await client.listPrompts()
      log(`Prompts (${prompts.prompts.length}):`)
      for (const prompt of prompts.prompts) {
        process.stdout.write(`  - ${sanitizeTerminalText(prompt.name)}\n`)
      }
    }
  } finally {
    await client.close().catch(() => {})
  }
}

main().catch((err) => {
  log('Fatal error:', err)
  process.exit(1)
})
