import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { Agent as UndiciAgent } from 'undici'
import type { SecureContextOptions } from 'node:tls'

/**
 * User-supplied mTLS configuration gathered from CLI flags or env vars.
 * Paths are resolved against process.cwd() when not absolute.
 */
export interface MtlsOptions {
  /** Path to a PEM-encoded client certificate (or certificate chain). */
  certPath?: string
  /** Path to the PEM-encoded private key for the client certificate. */
  keyPath?: string
  /** Path to a PEM-encoded CA bundle used to verify the remote server. */
  caPath?: string
  /** Passphrase protecting the private key, if any. */
  passphrase?: string
  /** Path to a PKCS#12 (.pfx/.p12) bundle; alternative to cert/key pair. */
  pfxPath?: string
  /**
   * Whether to reject TLS handshakes that fail server certificate validation.
   * Defaults to true. Set to false only for local development.
   */
  rejectUnauthorized?: boolean
  /** Optional SNI servername override (useful when hostnames don't match). */
  servername?: string
  /** Minimum TLS version, e.g. "TLSv1.2" or "TLSv1.3". */
  minVersion?: SecureContextOptions['minVersion']
}

/** Returns true when any mTLS-related option was provided. */
export function hasMtlsConfig(opts: MtlsOptions): boolean {
  return Boolean(
    opts.certPath ||
      opts.keyPath ||
      opts.caPath ||
      opts.pfxPath ||
      opts.passphrase ||
      opts.servername ||
      opts.minVersion ||
      opts.rejectUnauthorized === false,
  )
}

function readFileOrThrow(label: string, path: string): Buffer {
  try {
    return readFileSync(resolve(path))
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    throw new Error(`Unable to read ${label} at "${path}": ${msg}`)
  }
}

/**
 * Build a Node.js tls.SecureContextOptions-compatible object from the CLI
 * flags. Validates that a coherent combination of inputs was provided.
 */
export function buildSecureContextOptions(opts: MtlsOptions): SecureContextOptions & {
  rejectUnauthorized: boolean
  servername?: string
} {
  const tls: SecureContextOptions & { rejectUnauthorized: boolean; servername?: string } = {
    rejectUnauthorized: opts.rejectUnauthorized !== false,
  }

  if (opts.pfxPath) {
    if (opts.certPath || opts.keyPath) {
      throw new Error('Use either --tls-pfx OR --tls-cert/--tls-key, not both.')
    }
    tls.pfx = readFileOrThrow('PKCS#12 bundle', opts.pfxPath)
  }

  if (opts.certPath || opts.keyPath) {
    if (!opts.certPath || !opts.keyPath) {
      throw new Error('Both --tls-cert and --tls-key must be provided together.')
    }
    tls.cert = readFileOrThrow('client certificate', opts.certPath)
    tls.key = readFileOrThrow('client private key', opts.keyPath)
  }

  if (opts.caPath) {
    tls.ca = readFileOrThrow('CA bundle', opts.caPath)
  }

  if (opts.passphrase) {
    if (!opts.pfxPath && !opts.certPath) {
      throw new Error(
        '--tls-passphrase requires --tls-pfx OR --tls-cert/--tls-key; passphrase alone has nothing to decrypt.',
      )
    }
    tls.passphrase = opts.passphrase
  }
  if (opts.servername) tls.servername = opts.servername
  if (opts.minVersion) tls.minVersion = opts.minVersion

  return tls
}

/**
 * Build an undici Dispatcher configured with the mTLS secure context.
 * This dispatcher can be passed to fetch() via the `dispatcher` option and is
 * what the MCP SDK transports will use for their outbound HTTPS requests.
 */
export function buildMtlsDispatcher(opts: MtlsOptions): UndiciAgent {
  const tls = buildSecureContextOptions(opts)
  return new UndiciAgent({
    connect: tls,
  })
}
