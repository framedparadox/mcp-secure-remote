import { afterEach, describe, expect, it } from 'vitest'
import { parseCommandLineArgs, sanitizeServerUrlForLog } from '../../src/lib/args.js'

const ORIGINAL_ENV = { ...process.env }

afterEach(() => {
  process.env = { ...ORIGINAL_ENV }
})

describe('parseCommandLineArgs', () => {
  it('parses required URL and common flags', () => {
    const parsed = parseCommandLineArgs([
      'https://example.com/mcp',
      '--transport',
      'sse-only',
      '--allow-http',
      '--debug',
      '--header',
      'X-Test: abc',
    ])

    expect(parsed.serverUrl).toBe('https://example.com/mcp')
    expect(parsed.transportStrategy).toBe('sse-only')
    expect(parsed.allowHttp).toBe(true)
    expect(parsed.debug).toBe(true)
    expect(parsed.headers['X-Test']).toBe('abc')
  })

  it('rejects invalid transport value', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com/mcp', '--transport', 'invalid']),
    ).toThrow('--transport must be one of')
  })

  it('rejects http URLs unless --allow-http is set', () => {
    expect(() => parseCommandLineArgs(['http://example.com/mcp'])).toThrow(
      'Refusing to use http:// without --allow-http',
    )
  })

  it('rejects unsafe header values with CRLF', () => {
    expect(() =>
      parseCommandLineArgs(['https://example.com/mcp', '--header', 'X-Test: ok\nInjected: nope']),
    ).toThrow('must not contain CR, LF, or NUL')
  })

  it('rejects invalid env TLS min version values', () => {
    process.env.MCP_REMOTE_TLS_MIN_VERSION = 'TLSv1.1'
    expect(() => parseCommandLineArgs(['https://example.com/mcp'])).toThrow(
      'MCP_REMOTE_TLS_MIN_VERSION must be "TLSv1.2" or "TLSv1.3"',
    )
  })
})

describe('sanitizeServerUrlForLog', () => {
  it('strips credentials from URLs', () => {
    expect(sanitizeServerUrlForLog('https://user:pass@example.com/mcp')).toBe('https://example.com/mcp')
  })

  it('returns placeholder for invalid URLs', () => {
    expect(sanitizeServerUrlForLog('not-a-url')).toBe('<invalid-url>')
  })
})
