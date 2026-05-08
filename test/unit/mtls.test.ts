import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it } from 'vitest'
import { buildSecureContextOptions, hasMtlsConfig } from '../../src/lib/mtls.js'

describe('hasMtlsConfig', () => {
  it('returns true when rejectUnauthorized is explicitly false', () => {
    expect(hasMtlsConfig({ rejectUnauthorized: false })).toBe(true)
  })

  it('returns false when no mTLS options were provided', () => {
    expect(hasMtlsConfig({})).toBe(false)
  })
})

describe('buildSecureContextOptions', () => {
  it('requires cert and key together', () => {
    expect(() => buildSecureContextOptions({ certPath: './client.crt' })).toThrow(
      'Both --tls-cert and --tls-key must be provided together.',
    )
  })

  it('rejects passphrase without cert/key or pfx', () => {
    expect(() => buildSecureContextOptions({ passphrase: 'secret' })).toThrow(
      '--tls-passphrase requires --tls-pfx OR --tls-cert/--tls-key',
    )
  })

  it('rejects mixed pfx and cert/key configuration', () => {
    expect(() =>
      buildSecureContextOptions({ pfxPath: './client.p12', certPath: './client.crt', keyPath: './client.key' }),
    ).toThrow('Use either --tls-pfx OR --tls-cert/--tls-key, not both.')
  })

  it('loads cert, key, and ca from disk into secure context', () => {
    const dir = mkdtempSync(join(tmpdir(), 'mcp-secure-remote-test-'))
    const certPath = join(dir, 'client.crt')
    const keyPath = join(dir, 'client.key')
    const caPath = join(dir, 'ca.pem')

    writeFileSync(certPath, 'CERT_DATA')
    writeFileSync(keyPath, 'KEY_DATA')
    writeFileSync(caPath, 'CA_DATA')

    const tls = buildSecureContextOptions({
      certPath,
      keyPath,
      caPath,
      passphrase: 'super-secret',
      minVersion: 'TLSv1.3',
      servername: 'mcp.example.com',
      rejectUnauthorized: false,
    })

    expect(Buffer.isBuffer(tls.cert)).toBe(true)
    expect(Buffer.isBuffer(tls.key)).toBe(true)
    expect(Buffer.isBuffer(tls.ca)).toBe(true)
    expect((tls.cert as Buffer).toString()).toBe('CERT_DATA')
    expect((tls.key as Buffer).toString()).toBe('KEY_DATA')
    expect((tls.ca as Buffer).toString()).toBe('CA_DATA')
    expect(tls.passphrase).toBe('super-secret')
    expect(tls.minVersion).toBe('TLSv1.3')
    expect(tls.servername).toBe('mcp.example.com')
    expect(tls.rejectUnauthorized).toBe(false)

    rmSync(dir, { recursive: true, force: true })
  })
})
