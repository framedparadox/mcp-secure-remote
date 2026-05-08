import { describe, expect, it } from 'vitest'
import { sanitizeMtlsForLog, sanitizeParsedArgsForLog, sanitizeTerminalText } from '../../src/lib/sanitize.js'

describe('sanitizeMtlsForLog', () => {
  it('redacts passphrase while preserving other fields', () => {
    const sanitized = sanitizeMtlsForLog({
      certPath: '/tmp/client.crt',
      keyPath: '/tmp/client.key',
      passphrase: 'top-secret',
      minVersion: 'TLSv1.3',
    })

    expect(sanitized.certPath).toBe('/tmp/client.crt')
    expect(sanitized.keyPath).toBe('/tmp/client.key')
    expect(sanitized.minVersion).toBe('TLSv1.3')
    expect(sanitized.passphrase).toBe('***')
  })
})

describe('sanitizeParsedArgsForLog', () => {
  it('strips URL credentials and header values', () => {
    const sanitized = sanitizeParsedArgsForLog({
      serverUrl: 'https://user:pass@example.com/mcp',
      transportStrategy: 'http-first',
      allowHttp: false,
      headers: { Authorization: 'Bearer secret', 'X-Token': 'abc' },
      mtls: { passphrase: 'super-secret' },
    })

    expect(sanitized.serverUrl).toBe('https://example.com/mcp')
    expect(sanitized.headers).toEqual(['Authorization', 'X-Token'])
    expect((sanitized.mtls as { passphrase: string }).passphrase).toBe('***')
  })
})

describe('sanitizeTerminalText', () => {
  it('escapes terminal control and bidi characters', () => {
    const raw = 'ok\u001b[31mred\u001b[0m\u202Eabc'
    const escaped = sanitizeTerminalText(raw)

    expect(escaped).toContain('\\u001b')
    expect(escaped).toContain('\\u202e')
    expect(escaped).not.toContain('\u001b')
  })
})
