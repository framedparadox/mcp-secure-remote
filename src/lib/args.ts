import type { MtlsOptions } from './mtls.js'

export type TransportStrategy = 'http-first' | 'sse-first' | 'http-only' | 'sse-only'

export interface ParsedArgs {
  serverUrl: string
  headers: Record<string, string>
  transportStrategy: TransportStrategy
  debug: boolean
  allowHttp: boolean
  mtls: MtlsOptions
}

const VALID_TRANSPORTS: TransportStrategy[] = ['http-first', 'sse-first', 'http-only', 'sse-only']

function envOrUndefined(name: string): string | undefined {
  const v = process.env[name]
  return v && v.length > 0 ? v : undefined
}

/**
 * Parse CLI arguments for the proxy/client.
 *
 * The first positional argument is the remote MCP server URL. All other
 * configuration is supplied via named flags. Values may also be provided
 * through environment variables (see README) so that secrets like the key
 * passphrase don't have to live on the command line.
 */
export function parseCommandLineArgs(argv: string[]): ParsedArgs {
  const args = [...argv]
  let serverUrl: string | undefined
  const headers: Record<string, string> = {}
  let transportStrategy: TransportStrategy = 'http-first'
  let debug = false
  let allowHttp = false

  const envMinVersion = envOrUndefined('MCP_REMOTE_TLS_MIN_VERSION')
  if (envMinVersion && envMinVersion !== 'TLSv1.2' && envMinVersion !== 'TLSv1.3') {
    throw new Error('MCP_REMOTE_TLS_MIN_VERSION must be "TLSv1.2" or "TLSv1.3"')
  }
  const envInsecure = envOrUndefined('MCP_REMOTE_TLS_INSECURE')

  const mtls: MtlsOptions = {
    certPath: envOrUndefined('MCP_REMOTE_TLS_CERT'),
    keyPath: envOrUndefined('MCP_REMOTE_TLS_KEY'),
    caPath: envOrUndefined('MCP_REMOTE_TLS_CA'),
    passphrase: envOrUndefined('MCP_REMOTE_TLS_PASSPHRASE'),
    pfxPath: envOrUndefined('MCP_REMOTE_TLS_PFX'),
    servername: envOrUndefined('MCP_REMOTE_TLS_SERVERNAME'),
    minVersion: envMinVersion as MtlsOptions['minVersion'],
    rejectUnauthorized: envInsecure && /^(1|true|yes)$/i.test(envInsecure) ? false : undefined,
  }

  const take = (flag: string): string => {
    const value = args.shift()
    if (value === undefined) throw new Error(`Missing value for ${flag}`)
    return value
  }

  while (args.length > 0) {
    const arg = args.shift() as string

    switch (arg) {
      case '--header': {
        const raw = take('--header')
        const idx = raw.indexOf(':')
        if (idx === -1) throw new Error(`--header expects "Name: value", got "${raw}"`)
        const name = raw.slice(0, idx).trim()
        const value = raw.slice(idx + 1).trim()
        if (!name) throw new Error(`--header has empty name: "${raw}"`)
        headers[name] = value
        break
      }
      case '--transport': {
        const value = take('--transport')
        if (!VALID_TRANSPORTS.includes(value as TransportStrategy)) {
          throw new Error(`--transport must be one of ${VALID_TRANSPORTS.join(', ')}`)
        }
        transportStrategy = value as TransportStrategy
        break
      }
      case '--debug':
        debug = true
        break
      case '--allow-http':
        allowHttp = true
        break

      // mTLS flags
      case '--tls-cert':
        mtls.certPath = take('--tls-cert')
        break
      case '--tls-key':
        mtls.keyPath = take('--tls-key')
        break
      case '--tls-ca':
        mtls.caPath = take('--tls-ca')
        break
      case '--tls-passphrase':
        mtls.passphrase = take('--tls-passphrase')
        break
      case '--tls-pfx':
        mtls.pfxPath = take('--tls-pfx')
        break
      case '--tls-servername':
        mtls.servername = take('--tls-servername')
        break
      case '--tls-min-version': {
        const v = take('--tls-min-version')
        if (v !== 'TLSv1.2' && v !== 'TLSv1.3') {
          throw new Error('--tls-min-version must be "TLSv1.2" or "TLSv1.3"')
        }
        mtls.minVersion = v
        break
      }
      case '--tls-insecure-skip-verify':
      case '--tls-no-verify':
        mtls.rejectUnauthorized = false
        break

      case '-h':
      case '--help':
        printUsage()
        process.exit(0)
        break

      default:
        if (arg.startsWith('--')) {
          throw new Error(`Unknown flag: ${arg}`)
        }
        if (serverUrl) {
          throw new Error(`Unexpected positional argument: ${arg}`)
        }
        serverUrl = arg
    }
  }

  if (!serverUrl) {
    printUsage()
    throw new Error('Missing required positional argument: <server-url>')
  }

  let parsed: URL
  try {
    parsed = new URL(serverUrl)
  } catch {
    throw new Error(`Invalid server URL: ${serverUrl}`)
  }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    throw new Error(`Server URL must use http(s), got: ${parsed.protocol}`)
  }
  if (parsed.protocol === 'http:' && !allowHttp) {
    throw new Error('Refusing to use http:// without --allow-http; mTLS requires https://.')
  }
  if (parsed.protocol === 'http:' && hasAnyMtlsFlag(mtls)) {
    process.stderr.write(
      'WARNING: mTLS options supplied with http:// URL; client certificate will NOT be sent over plain HTTP.\n',
    )
  }
  if (mtls.rejectUnauthorized === false) {
    process.stderr.write(
      'WARNING: TLS server certificate verification disabled. This is insecure; use only for local development.\n',
    )
  }

  return { serverUrl, headers, transportStrategy, debug, allowHttp, mtls }
}

function hasAnyMtlsFlag(m: MtlsOptions): boolean {
  return Boolean(m.certPath || m.keyPath || m.pfxPath || m.caPath || m.passphrase || m.servername || m.minVersion)
}

export function printUsage(): void {
  const lines = [
    'Usage: mcp-secure-remote <server-url> [options]',
    '',
    'Bridges a local stdio MCP client to a remote MCP server, authenticating',
    'with a mutual-TLS client certificate.',
    '',
    'Options:',
    '  --header "Name: value"      Add a custom HTTP header (repeatable).',
    '  --transport <strategy>      http-first | sse-first | http-only | sse-only (default: http-first).',
    '  --allow-http                Allow plain http:// URLs (disables the default https-only check).',
    '  --debug                     Verbose logging to stderr.',
    '',
    'mTLS options:',
    '  --tls-cert <path>           PEM client certificate (or chain).',
    '  --tls-key <path>            PEM private key matching --tls-cert.',
    '  --tls-ca <path>             PEM CA bundle used to verify the remote server.',
    '  --tls-passphrase <value>    Passphrase protecting the private key.',
    '  --tls-pfx <path>            PKCS#12 bundle (alternative to --tls-cert/--tls-key).',
    '  --tls-servername <name>     SNI servername override.',
    '  --tls-min-version <ver>     TLSv1.2 or TLSv1.3.',
    '  --tls-insecure-skip-verify  Disable server certificate validation (NOT for production).',
    '',
    'Environment variables (fallbacks for flags):',
    '  MCP_REMOTE_TLS_CERT, MCP_REMOTE_TLS_KEY, MCP_REMOTE_TLS_CA,',
    '  MCP_REMOTE_TLS_PASSPHRASE, MCP_REMOTE_TLS_PFX, MCP_REMOTE_TLS_SERVERNAME,',
    '  MCP_REMOTE_TLS_MIN_VERSION, MCP_REMOTE_TLS_INSECURE (=1 to skip server cert verify)',
  ]
  process.stderr.write(lines.join('\n') + '\n')
}
