import type { AuthOptions } from './auth-headers.js'
import type { MtlsOptions } from './mtls.js'
import { sanitizeServerUrlForLog } from './args.js'

export function sanitizeParsedArgsForLog(parsed: {
  serverUrl: string
  transportStrategy: string
  allowHttp: boolean
  allowPrivateUrls: boolean
  headers: Record<string, string>
  mtls: MtlsOptions
  auth: AuthOptions
}): Record<string, unknown> {
  return {
    serverUrl: sanitizeServerUrlForLog(parsed.serverUrl),
    transportStrategy: parsed.transportStrategy,
    allowHttp: parsed.allowHttp,
    allowPrivateUrls: parsed.allowPrivateUrls,
    headers: Object.keys(parsed.headers),
    auth: sanitizeAuthForLog(parsed.auth),
    mtls: sanitizeMtlsForLog(parsed.mtls),
  }
}

export function sanitizeAuthForLog(auth: AuthOptions): Record<string, unknown> {
  return {
    bearer: auth.bearer ? '***' : undefined,
    basic: auth.basic ? '***' : undefined,
    apiKey: auth.apiKey ? '***' : undefined,
    apiKeyHeader: auth.apiKeyHeader,
  }
}

export function sanitizeMtlsForLog(mtls: MtlsOptions): Record<string, unknown> {
  return {
    certPath: mtls.certPath,
    keyPath: mtls.keyPath,
    caPath: mtls.caPath,
    pfxPath: mtls.pfxPath,
    servername: mtls.servername,
    minVersion: mtls.minVersion,
    rejectUnauthorized: mtls.rejectUnauthorized,
    passphrase: mtls.passphrase ? '***' : undefined,
    pinCount: mtls.pinSha256?.length ?? 0,
  }
}

/**
 * Escape control, invisible, and bidi-override characters before writing
 * remote-supplied metadata to a terminal so malicious servers cannot inject
 * terminal control sequences, spoof visible text ordering, or embed hidden
 * characters inside otherwise-clean strings.
 *
 * Covered ranges:
 *   \\u0000-\\u001f  C0 controls (includes ESC \\u001b used to start ANSI sequences)
 *   \\u007f-\\u009f  DEL + C1 controls (includes CSI \\u009b, OSC \\u009d)
 *   \\u00ad          Soft Hyphen - invisible word-split marker
 *   \\u200b-\\u200f  ZWSP, ZWNJ, ZWJ, LTR mark, RTL mark
 *   \\u2028-\\u2029  Unicode line / paragraph separators
 *   \\u202a-\\u202e  Bidi embedding / override characters
 *   \\u2060          Word Joiner - invisible separator
 *   \\u2066-\\u2069  Bidi isolate characters
 *   \\ufeff          BOM / Zero Width No-Break Space
 */
export function sanitizeTerminalText(value: string): string {
  return value.replace(
    /[\u0000-\u001f\u007f-\u009f\u00ad\u200b-\u200f\u2028-\u2029\u202a-\u202e\u2060\u2066-\u2069\ufeff]/g,
    (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`,
  )
}
