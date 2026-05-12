import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { parseCommandLineArgs, sanitizeServerUrlForLog } from '../../src/lib/args.js'

const ORIGINAL_ENV = { ...process.env }

afterEach(() => {
  process.env = { ...ORIGINAL_ENV }
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// parseCommandLineArgs – positional argument
// ---------------------------------------------------------------------------
describe('parseCommandLineArgs – server URL', () => {
  it('parses a bare https URL', () => {
    const parsed = parseCommandLineArgs(['https://example.com/mcp'])
    expect(parsed.serverUrl).toBe('https://example.com/mcp')
  })

  it('throws when server URL is missing', () => {
    expect(() => parseCommandLineArgs([])).toThrow('Missing required positional argument: <server-url>')
  })

  it('throws on a second positional argument', () => {
    expect(() => parseCommandLineArgs(['https://example.com/mcp', 'extra'])).toThrow(
      'Unexpected positional argument: extra',
    )
  })

  it('throws on a non-http(s) protocol', () => {
    expect(() => parseCommandLineArgs(['ftp://example.com/mcp'])).toThrow(
      'Server URL must use http(s)',
    )
  })

  it('throws on an unparseable URL', () => {
    expect(() => parseCommandLineArgs(['not a url'])).toThrow('Invalid server URL')
  })

  it('throws when URL contains embedded credentials', () => {
    expect(() => parseCommandLineArgs(['https://user:pass@example.com/mcp'])).toThrow(
      'Server URL must not contain embedded credentials',
    )
  })

  it('throws on http:// without --allow-http', () => {
    expect(() => parseCommandLineArgs(['http://example.com/mcp'])).toThrow(
      'Refusing to use http:// without --allow-http',
    )
  })

  it('accepts http:// when --allow-http is set', () => {
    const parsed = parseCommandLineArgs(['http://example.com/mcp', '--allow-http'])
    expect(parsed.serverUrl).toBe('http://example.com/mcp')
    expect(parsed.allowHttp).toBe(true)
  })

  it('emits a warning when mTLS options are supplied with http://', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    parseCommandLineArgs([
      'http://example.com/mcp',
      '--allow-http',
      '--tls-cert',
      '/tmp/c.crt',
      '--tls-key',
      '/tmp/c.key',
    ])
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('client certificate will NOT be sent'))
  })
})

// ---------------------------------------------------------------------------
// parseCommandLineArgs – --transport
// ---------------------------------------------------------------------------
describe('parseCommandLineArgs – --transport', () => {
  it.each(['http-first', 'sse-first', 'http-only', 'sse-only'])(
    'accepts %s',
    (strategy) => {
      const parsed = parseCommandLineArgs(['https://example.com', '--transport', strategy])
      expect(parsed.transportStrategy).toBe(strategy)
    },
  )

  it('defaults to http-first', () => {
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.transportStrategy).toBe('http-first')
  })

  it('throws on unknown transport value', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--transport', 'websocket']),
    ).toThrow('--transport must be one of')
  })

  it('throws when --transport is missing its value', () => {
    expect(() => parseCommandLineArgs(['https://example.com', '--transport'])).toThrow(
      'Missing value for --transport',
    )
  })
})

// ---------------------------------------------------------------------------
// parseCommandLineArgs – --header
// ---------------------------------------------------------------------------
describe('parseCommandLineArgs – --header', () => {
  it('parses a single header', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--header', 'Authorization: Bearer tok'])
    expect(parsed.headers['Authorization']).toBe('Bearer tok')
  })

  it('parses multiple --header flags', () => {
    const parsed = parseCommandLineArgs([
      'https://example.com',
      '--header', 'X-A: 1',
      '--header', 'X-B: 2',
    ])
    expect(parsed.headers['X-A']).toBe('1')
    expect(parsed.headers['X-B']).toBe('2')
  })

  it('trims whitespace from header name and value', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--header', 'X-Trimmed :   spaced   '])
    expect(parsed.headers['X-Trimmed']).toBe('spaced')
  })

  it('throws when header has no colon', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--header', 'NoColon']),
    ).toThrow('--header expects "Name: value"')
  })

  it('throws when header name is empty', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--header', ': value']),
    ).toThrow('--header has empty name')
  })

  it('throws on CRLF injection in header value', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--header', 'X-Bad: val\r\nInjected: evil']),
    ).toThrow('must not contain CR, LF, or NUL')
  })

  it('throws on LF in header value', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--header', 'X-LF: val\nInjected']),
    ).toThrow('must not contain CR, LF, or NUL')
  })

  it('throws on NUL in header value', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--header', 'X-NUL: val\x00end']),
    ).toThrow('must not contain CR, LF, or NUL')
  })

  it('throws on invalid header name characters', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--header', 'X Bad: val']),
    ).toThrow('Invalid header name')
  })

  it('throws when --header flag has no value', () => {
    expect(() => parseCommandLineArgs(['https://example.com', '--header'])).toThrow(
      'Missing value for --header',
    )
  })
})

// ---------------------------------------------------------------------------
// parseCommandLineArgs – mTLS flags
// ---------------------------------------------------------------------------
describe('parseCommandLineArgs – mTLS flags', () => {
  it('sets certPath from --tls-cert', () => {
    const parsed = parseCommandLineArgs([
      'https://example.com', '--tls-cert', '/tmp/c.crt', '--tls-key', '/tmp/c.key',
    ])
    expect(parsed.mtls.certPath).toBe('/tmp/c.crt')
    expect(parsed.mtls.keyPath).toBe('/tmp/c.key')
  })

  it('sets caPath from --tls-ca', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-ca', '/tmp/ca.pem'])
    expect(parsed.mtls.caPath).toBe('/tmp/ca.pem')
  })

  it('sets pfxPath from --tls-pfx', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-pfx', '/tmp/bundle.p12'])
    expect(parsed.mtls.pfxPath).toBe('/tmp/bundle.p12')
  })

  it('sets passphrase from --tls-passphrase', () => {
    const parsed = parseCommandLineArgs([
      'https://example.com', '--tls-cert', '/tmp/c.crt', '--tls-key', '/tmp/c.key',
      '--tls-passphrase', 'secret',
    ])
    expect(parsed.mtls.passphrase).toBe('secret')
  })

  it('sets servername from --tls-servername', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-servername', 'override.example.com'])
    expect(parsed.mtls.servername).toBe('override.example.com')
  })

  it('accepts --tls-min-version TLSv1.2', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-min-version', 'TLSv1.2'])
    expect(parsed.mtls.minVersion).toBe('TLSv1.2')
  })

  it('accepts --tls-min-version TLSv1.3', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-min-version', 'TLSv1.3'])
    expect(parsed.mtls.minVersion).toBe('TLSv1.3')
  })

  it('throws on invalid --tls-min-version', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--tls-min-version', 'TLSv1.1']),
    ).toThrow('--tls-min-version must be "TLSv1.2" or "TLSv1.3"')
  })

  it('sets rejectUnauthorized=false for --tls-insecure-skip-verify', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-insecure-skip-verify'])
    expect(parsed.mtls.rejectUnauthorized).toBe(false)
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('TLS server certificate verification disabled'))
  })

  it('sets rejectUnauthorized=false for --tls-no-verify alias', () => {
    vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-no-verify'])
    expect(parsed.mtls.rejectUnauthorized).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// parseCommandLineArgs – environment variable fallbacks
// ---------------------------------------------------------------------------
describe('parseCommandLineArgs – environment variable fallbacks', () => {
  beforeEach(() => {
    // wipe all MCP_REMOTE_TLS_* vars before each test in this suite
    for (const key of Object.keys(process.env)) {
      if (key.startsWith('MCP_REMOTE_TLS_')) delete process.env[key]
    }
  })

  it('reads MCP_REMOTE_TLS_CERT', () => {
    process.env.MCP_REMOTE_TLS_CERT = '/env/client.crt'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.certPath).toBe('/env/client.crt')
  })

  it('reads MCP_REMOTE_TLS_KEY', () => {
    process.env.MCP_REMOTE_TLS_KEY = '/env/client.key'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.keyPath).toBe('/env/client.key')
  })

  it('reads MCP_REMOTE_TLS_CA', () => {
    process.env.MCP_REMOTE_TLS_CA = '/env/ca.pem'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.caPath).toBe('/env/ca.pem')
  })

  it('reads MCP_REMOTE_TLS_PASSPHRASE', () => {
    process.env.MCP_REMOTE_TLS_PASSPHRASE = 'env-secret'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.passphrase).toBe('env-secret')
  })

  it('reads MCP_REMOTE_TLS_PFX', () => {
    process.env.MCP_REMOTE_TLS_PFX = '/env/bundle.p12'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.pfxPath).toBe('/env/bundle.p12')
  })

  it('reads MCP_REMOTE_TLS_SERVERNAME', () => {
    process.env.MCP_REMOTE_TLS_SERVERNAME = 'env.example.com'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.servername).toBe('env.example.com')
  })

  it('reads MCP_REMOTE_TLS_MIN_VERSION TLSv1.2', () => {
    process.env.MCP_REMOTE_TLS_MIN_VERSION = 'TLSv1.2'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.minVersion).toBe('TLSv1.2')
  })

  it('throws on invalid MCP_REMOTE_TLS_MIN_VERSION', () => {
    process.env.MCP_REMOTE_TLS_MIN_VERSION = 'TLSv1.0'
    expect(() => parseCommandLineArgs(['https://example.com'])).toThrow(
      'MCP_REMOTE_TLS_MIN_VERSION must be "TLSv1.2" or "TLSv1.3"',
    )
  })

  it.each(['1', 'true', 'yes', 'TRUE', 'YES'])(
    'MCP_REMOTE_TLS_INSECURE=%s disables server cert verification',
    (val) => {
      vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
      process.env.MCP_REMOTE_TLS_INSECURE = val
      const parsed = parseCommandLineArgs(['https://example.com'])
      expect(parsed.mtls.rejectUnauthorized).toBe(false)
    },
  )

  it('MCP_REMOTE_TLS_INSECURE=0 keeps verification enabled', () => {
    process.env.MCP_REMOTE_TLS_INSECURE = '0'
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.rejectUnauthorized).toBeUndefined()
  })

  it('CLI flags override env vars', () => {
    process.env.MCP_REMOTE_TLS_CERT = '/env/client.crt'
    const parsed = parseCommandLineArgs(['https://example.com', '--tls-cert', '/cli/client.crt', '--tls-key', '/cli/client.key'])
    expect(parsed.mtls.certPath).toBe('/cli/client.crt')
  })

  it('ignores empty-string env vars', () => {
    process.env.MCP_REMOTE_TLS_CERT = ''
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.mtls.certPath).toBeUndefined()
  })
})

// ---------------------------------------------------------------------------
// parseCommandLineArgs – misc
// ---------------------------------------------------------------------------
describe('parseCommandLineArgs – misc', () => {
  it('throws on an unknown flag', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com', '--unknown-flag']),
    ).toThrow('Unknown flag: --unknown-flag')
  })

  it('sets debug=false by default', () => {
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.debug).toBe(false)
  })

  it('sets debug=true with --debug', () => {
    const parsed = parseCommandLineArgs(['https://example.com', '--debug'])
    expect(parsed.debug).toBe(true)
  })

  it('returns empty headers by default', () => {
    const parsed = parseCommandLineArgs(['https://example.com'])
    expect(parsed.headers).toEqual({})
  })
})

// ---------------------------------------------------------------------------
// sanitizeServerUrlForLog
// ---------------------------------------------------------------------------
describe('sanitizeServerUrlForLog', () => {
  it('strips username and password', () => {
    expect(sanitizeServerUrlForLog('https://user:pass@example.com/mcp')).toBe('https://example.com/mcp')
  })

  it('returns placeholder for invalid URL', () => {
    expect(sanitizeServerUrlForLog('not-a-url')).toBe('<invalid-url>')
  })

  it('leaves URLs without credentials unchanged', () => {
    expect(sanitizeServerUrlForLog('https://example.com/mcp')).toBe('https://example.com/mcp')
  })

  it('strips only username (no password)', () => {
    expect(sanitizeServerUrlForLog('https://user@example.com/mcp')).toBe('https://example.com/mcp')
  })

  it('preserves query string and path', () => {
    expect(sanitizeServerUrlForLog('https://example.com/mcp?foo=bar')).toBe(
      'https://example.com/mcp?foo=bar',
    )
  })
})
