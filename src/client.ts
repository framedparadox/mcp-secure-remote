/**
 * mcp-secure-remote-client – standalone client for exercising a remote MCP server
 * over mTLS without running a stdio proxy. Useful for verifying certificate
 * configuration and listing the tools/resources/prompts exposed by the server.
 */
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { parseCommandLineArgs, printUsage } from './lib/args.js'
import { debugLog, log, setDebug } from './lib/log.js'
import { connectToRemoteServer } from './lib/transport.js'
import type { MtlsOptions } from './lib/mtls.js'

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

function sanitizeParsedArgsForLog(parsed: {
  serverUrl: string
  transportStrategy: string
  allowHttp: boolean
  headers: Record<string, string>
  mtls: MtlsOptions
}): Record<string, unknown> {
  return {
    serverUrl: parsed.serverUrl,
    transportStrategy: parsed.transportStrategy,
    allowHttp: parsed.allowHttp,
    headers: Object.keys(parsed.headers),
    mtls: sanitizeMtlsForLog(parsed.mtls),
  }
}

function sanitizeMtlsForLog(mtls: MtlsOptions): Record<string, unknown> {
  return {
    certPath: mtls.certPath,
    keyPath: mtls.keyPath,
    caPath: mtls.caPath,
    pfxPath: mtls.pfxPath,
    servername: mtls.servername,
    minVersion: mtls.minVersion,
    rejectUnauthorized: mtls.rejectUnauthorized,
    passphrase: mtls.passphrase ? '***' : undefined,
  }
}

/**
 * Escape control and bidi-override characters before writing remote-supplied
 * metadata to a terminal so malicious servers cannot inject terminal control
 * sequences or spoof visible text ordering.
 */
function sanitizeTerminalText(value: string): string {
  return value.replace(
    /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`,
  )
}

main().catch((err) => {
  log('Fatal error:', err)
  process.exit(1)
})
