import { describe, expect, it } from 'vitest'
import { sanitizeMtlsForLog, sanitizeParsedArgsForLog, sanitizeTerminalText } from '../../src/lib/sanitize.js'

// ---------------------------------------------------------------------------
// sanitizeTerminalText
// ---------------------------------------------------------------------------
describe('sanitizeTerminalText', () => {
  it('passes through plain ASCII unchanged', () => {
    expect(sanitizeTerminalText('Hello, world!')).toBe('Hello, world!')
  })

  it('escapes ESC (ANSI sequence start)', () => {
    const result = sanitizeTerminalText('[31mred[0m')
    expect(result).not.toContain('')
    expect(result).toContain('\\u001b')
  })

  it('escapes all C0 control characters (0x00–0x1f)', () => {
    for (let i = 0; i <= 0x1f; i++) {
      const char = String.fromCharCode(i)
      const result = sanitizeTerminalText(char)
      expect(result).not.toContain(char)
      expect(result).toContain('\\u')
    }
  })

  it('escapes DEL (0x7f)', () => {
    const result = sanitizeTerminalText('')
    expect(result).toContain('\\u007f')
  })

  it('escapes C1 controls (0x80–0x9f)', () => {
    for (let i = 0x80; i <= 0x9f; i++) {
      const char = String.fromCharCode(i)
      const result = sanitizeTerminalText(char)
      expect(result).not.toContain(char)
    }
  })

  it('escapes soft hyphen (U+00AD)', () => {
    const result = sanitizeTerminalText('­')
    expect(result).toContain('\\u00ad')
  })

  it('escapes zero-width space (U+200B)', () => {
    const result = sanitizeTerminalText('​')
    expect(result).toContain('\\u200b')
  })

  it('escapes ZWNJ (U+200C)', () => {
    const result = sanitizeTerminalText('‌')
    expect(result).toContain('\\u200c')
  })

  it('escapes ZWJ (U+200D)', () => {
    const result = sanitizeTerminalText('‍')
    expect(result).toContain('\\u200d')
  })

  it('escapes LTR mark (U+200E)', () => {
    const result = sanitizeTerminalText('‎')
    expect(result).toContain('\\u200e')
  })

  it('escapes RTL mark (U+200F)', () => {
    const result = sanitizeTerminalText('‏')
    expect(result).toContain('\\u200f')
  })

  it('escapes line separator (U+2028)', () => {
    const result = sanitizeTerminalText(' ')
    expect(result).toContain('\\u2028')
  })

  it('escapes paragraph separator (U+2029)', () => {
    const result = sanitizeTerminalText(' ')
    expect(result).toContain('\\u2029')
  })

  it('escapes bidi embedding/override characters (U+202A–U+202E)', () => {
    for (let i = 0x202a; i <= 0x202e; i++) {
      const char = String.fromCharCode(i)
      const result = sanitizeTerminalText(char)
      expect(result).not.toContain(char)
      expect(result).toContain('\\u')
    }
  })

  it('escapes right-to-left override (U+202E)', () => {
    const result = sanitizeTerminalText('‮')
    expect(result).toContain('\\u202e')
  })

  it('escapes word joiner (U+2060)', () => {
    const result = sanitizeTerminalText('⁠')
    expect(result).toContain('\\u2060')
  })

  it('escapes bidi isolates (U+2066–U+2069)', () => {
    for (let i = 0x2066; i <= 0x2069; i++) {
      const char = String.fromCharCode(i)
      const result = sanitizeTerminalText(char)
      expect(result).not.toContain(char)
    }
  })

  it('escapes BOM (U+FEFF)', () => {
    const result = sanitizeTerminalText('﻿')
    expect(result).toContain('\\ufeff')
  })

  it('preserves normal Unicode letters and symbols', () => {
    const safe = 'Héllo Wörld 日本語 émoji-free'
    expect(sanitizeTerminalText(safe)).toBe(safe)
  })

  it('replaces multiple dangerous chars in one string', () => {
    const raw = 'ok[31mred[0m‮abc'
    const result = sanitizeTerminalText(raw)
    expect(result).toContain('\\u001b')
    expect(result).toContain('\\u202e')
    expect(result).toContain('ok')
    expect(result).toContain('red')
    expect(result).toContain('abc')
  })

  it('formats escape codes as lowercase 4-digit hex', () => {
    // e.g. ESC should be , not \u1B or 
    const result = sanitizeTerminalText('')
    expect(result).toBe('\\u001b')
  })

  it('returns empty string unchanged', () => {
    expect(sanitizeTerminalText('')).toBe('')
  })
})

// ---------------------------------------------------------------------------
// sanitizeMtlsForLog
// ---------------------------------------------------------------------------
describe('sanitizeMtlsForLog', () => {
  it('redacts passphrase with ***', () => {
    const result = sanitizeMtlsForLog({ passphrase: 'top-secret' })
    expect(result.passphrase).toBe('***')
  })

  it('emits undefined for passphrase when not set', () => {
    const result = sanitizeMtlsForLog({})
    expect(result.passphrase).toBeUndefined()
  })

  it('preserves certPath', () => {
    const result = sanitizeMtlsForLog({ certPath: '/tmp/c.crt' })
    expect(result.certPath).toBe('/tmp/c.crt')
  })

  it('preserves keyPath', () => {
    const result = sanitizeMtlsForLog({ keyPath: '/tmp/c.key' })
    expect(result.keyPath).toBe('/tmp/c.key')
  })

  it('preserves caPath', () => {
    const result = sanitizeMtlsForLog({ caPath: '/tmp/ca.pem' })
    expect(result.caPath).toBe('/tmp/ca.pem')
  })

  it('preserves pfxPath', () => {
    const result = sanitizeMtlsForLog({ pfxPath: '/tmp/b.p12' })
    expect(result.pfxPath).toBe('/tmp/b.p12')
  })

  it('preserves servername', () => {
    const result = sanitizeMtlsForLog({ servername: 'override.example.com' })
    expect(result.servername).toBe('override.example.com')
  })

  it('preserves minVersion', () => {
    const result = sanitizeMtlsForLog({ minVersion: 'TLSv1.3' })
    expect(result.minVersion).toBe('TLSv1.3')
  })

  it('preserves rejectUnauthorized', () => {
    const result = sanitizeMtlsForLog({ rejectUnauthorized: false })
    expect(result.rejectUnauthorized).toBe(false)
  })

  it('handles fully populated options', () => {
    const result = sanitizeMtlsForLog({
      certPath: '/tmp/c.crt',
      keyPath: '/tmp/c.key',
      caPath: '/tmp/ca.pem',
      pfxPath: '/tmp/b.p12',
      passphrase: 'secret',
      servername: 'host',
      minVersion: 'TLSv1.2',
      rejectUnauthorized: true,
    })
    expect(result.certPath).toBe('/tmp/c.crt')
    expect(result.passphrase).toBe('***')
    expect(result.minVersion).toBe('TLSv1.2')
  })
})

// ---------------------------------------------------------------------------
// sanitizeParsedArgsForLog
// ---------------------------------------------------------------------------
describe('sanitizeParsedArgsForLog', () => {
  it('strips URL credentials', () => {
    const result = sanitizeParsedArgsForLog({
      serverUrl: 'https://user:pass@example.com/mcp',
      transportStrategy: 'http-first',
      allowHttp: false,
      headers: {},
      mtls: {},
    })
    expect(result.serverUrl).toBe('https://example.com/mcp')
  })

  it('returns only header names, not values', () => {
    const result = sanitizeParsedArgsForLog({
      serverUrl: 'https://example.com',
      transportStrategy: 'http-first',
      allowHttp: false,
      headers: { Authorization: 'Bearer secret', 'X-Token': 'abc' },
      mtls: {},
    })
    expect(result.headers).toEqual(['Authorization', 'X-Token'])
  })

  it('redacts passphrase in mtls', () => {
    const result = sanitizeParsedArgsForLog({
      serverUrl: 'https://example.com',
      transportStrategy: 'http-first',
      allowHttp: false,
      headers: {},
      mtls: { passphrase: 'super-secret' },
    })
    expect((result.mtls as { passphrase: string }).passphrase).toBe('***')
  })

  it('includes transportStrategy', () => {
    const result = sanitizeParsedArgsForLog({
      serverUrl: 'https://example.com',
      transportStrategy: 'sse-only',
      allowHttp: false,
      headers: {},
      mtls: {},
    })
    expect(result.transportStrategy).toBe('sse-only')
  })

  it('includes allowHttp', () => {
    const result = sanitizeParsedArgsForLog({
      serverUrl: 'https://example.com',
      transportStrategy: 'http-first',
      allowHttp: true,
      headers: {},
      mtls: {},
    })
    expect(result.allowHttp).toBe(true)
  })

  it('handles empty headers', () => {
    const result = sanitizeParsedArgsForLog({
      serverUrl: 'https://example.com',
      transportStrategy: 'http-first',
      allowHttp: false,
      headers: {},
      mtls: {},
    })
    expect(result.headers).toEqual([])
  })
})
