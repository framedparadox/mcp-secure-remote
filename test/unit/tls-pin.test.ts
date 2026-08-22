import { describe, expect, it } from 'vitest'
import { normalizeTlsPin, parseTlsPins } from '../../src/lib/tls-pin.js'

describe('tls-pin helpers', () => {
  it('normalizes sha256/ prefixed pins', () => {
    expect(normalizeTlsPin('sha256/abc123==')).toBe('abc123==')
    expect(normalizeTlsPin('  sha256/def456==  ')).toBe('def456==')
  })

  it('parses valid pin lists', () => {
    const hexPin = 'a'.repeat(64)
    expect(parseTlsPins(['abc123==', hexPin], '--tls-pin-sha256')).toEqual(['abc123==', hexPin])
  })

  it('rejects empty pin lists', () => {
    expect(() => parseTlsPins([], '--tls-pin-sha256')).toThrow(/at least one/)
    expect(() => parseTlsPins(['   '], '--tls-pin-sha256')).toThrow(/at least one/)
  })

  it('rejects malformed pins', () => {
    expect(() => parseTlsPins(['not-a-pin!'], '--tls-pin-sha256')).toThrow(/must be base64 or hex/)
  })
})
