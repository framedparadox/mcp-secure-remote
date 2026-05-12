import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it } from 'vitest'
import { buildSecureContextOptions, buildMtlsDispatcher, hasMtlsConfig } from '../../src/lib/mtls.js'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTempDir() {
  return mkdtempSync(join(tmpdir(), 'mcp-mtls-test-'))
}

function writeFakeFiles(dir: string, files: Record<string, string>) {
  for (const [name, content] of Object.entries(files)) {
    writeFileSync(join(dir, name), content)
  }
}

// ---------------------------------------------------------------------------
// hasMtlsConfig
// ---------------------------------------------------------------------------
describe('hasMtlsConfig', () => {
  it('returns false for empty options', () => {
    expect(hasMtlsConfig({})).toBe(false)
  })

  it('returns true when certPath provided', () => {
    expect(hasMtlsConfig({ certPath: '/tmp/c.crt' })).toBe(true)
  })

  it('returns true when keyPath provided', () => {
    expect(hasMtlsConfig({ keyPath: '/tmp/c.key' })).toBe(true)
  })

  it('returns true when caPath provided', () => {
    expect(hasMtlsConfig({ caPath: '/tmp/ca.pem' })).toBe(true)
  })

  it('returns true when pfxPath provided', () => {
    expect(hasMtlsConfig({ pfxPath: '/tmp/bundle.p12' })).toBe(true)
  })

  it('returns true when passphrase provided', () => {
    expect(hasMtlsConfig({ passphrase: 'secret' })).toBe(true)
  })

  it('returns true when servername provided', () => {
    expect(hasMtlsConfig({ servername: 'override.example.com' })).toBe(true)
  })

  it('returns true when minVersion provided', () => {
    expect(hasMtlsConfig({ minVersion: 'TLSv1.3' })).toBe(true)
  })

  it('returns true when rejectUnauthorized is explicitly false', () => {
    expect(hasMtlsConfig({ rejectUnauthorized: false })).toBe(true)
  })

  it('returns false when rejectUnauthorized is explicitly true (not a "mTLS" flag, just default)', () => {
    expect(hasMtlsConfig({ rejectUnauthorized: true })).toBe(false)
  })

  it('returns false when rejectUnauthorized is undefined', () => {
    expect(hasMtlsConfig({ rejectUnauthorized: undefined })).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// buildSecureContextOptions – validation errors
// ---------------------------------------------------------------------------
describe('buildSecureContextOptions – validation', () => {
  it('throws when certPath is given without keyPath', () => {
    expect(() => buildSecureContextOptions({ certPath: '/tmp/c.crt' })).toThrow(
      'Both --tls-cert and --tls-key must be provided together.',
    )
  })

  it('throws when keyPath is given without certPath', () => {
    expect(() => buildSecureContextOptions({ keyPath: '/tmp/c.key' })).toThrow(
      'Both --tls-cert and --tls-key must be provided together.',
    )
  })

  it('throws when both pfxPath and certPath are supplied', () => {
    expect(() =>
      buildSecureContextOptions({ pfxPath: '/tmp/b.p12', certPath: '/tmp/c.crt', keyPath: '/tmp/c.key' }),
    ).toThrow('Use either --tls-pfx OR --tls-cert/--tls-key, not both.')
  })

  it('throws when both pfxPath and keyPath are supplied', () => {
    expect(() =>
      buildSecureContextOptions({ pfxPath: '/tmp/b.p12', keyPath: '/tmp/c.key' }),
    ).toThrow('Use either --tls-pfx OR --tls-cert/--tls-key, not both.')
  })

  it('throws passphrase without any certificate source', () => {
    expect(() => buildSecureContextOptions({ passphrase: 'secret' })).toThrow(
      '--tls-passphrase requires --tls-pfx OR --tls-cert/--tls-key',
    )
  })

  it('throws when file path does not exist', () => {
    expect(() =>
      buildSecureContextOptions({ certPath: '/nonexistent/c.crt', keyPath: '/nonexistent/c.key' }),
    ).toThrow('Unable to read client certificate')
  })

  it('throws when CA file path does not exist', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'c.crt': 'CERT', 'c.key': 'KEY' })
    try {
      expect(() =>
        buildSecureContextOptions({
          certPath: join(dir, 'c.crt'),
          keyPath: join(dir, 'c.key'),
          caPath: join(dir, 'nonexistent-ca.pem'),
        }),
      ).toThrow('Unable to read CA bundle')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('throws when PFX file path does not exist', () => {
    expect(() => buildSecureContextOptions({ pfxPath: '/nonexistent/bundle.p12' })).toThrow(
      'Unable to read PKCS#12 bundle',
    )
  })
})

// ---------------------------------------------------------------------------
// buildSecureContextOptions – happy paths
// ---------------------------------------------------------------------------
describe('buildSecureContextOptions – success', () => {
  it('returns rejectUnauthorized=true by default', () => {
    const tls = buildSecureContextOptions({})
    expect(tls.rejectUnauthorized).toBe(true)
  })

  it('returns rejectUnauthorized=false when explicitly set', () => {
    const tls = buildSecureContextOptions({ rejectUnauthorized: false })
    expect(tls.rejectUnauthorized).toBe(false)
  })

  it('loads cert and key buffers from disk', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'c.crt': 'MY_CERT', 'c.key': 'MY_KEY' })
    try {
      const tls = buildSecureContextOptions({ certPath: join(dir, 'c.crt'), keyPath: join(dir, 'c.key') })
      expect(Buffer.isBuffer(tls.cert)).toBe(true)
      expect(Buffer.isBuffer(tls.key)).toBe(true)
      expect((tls.cert as Buffer).toString()).toBe('MY_CERT')
      expect((tls.key as Buffer).toString()).toBe('MY_KEY')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('loads CA from disk', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'c.crt': 'CERT', 'c.key': 'KEY', 'ca.pem': 'CA_CERT' })
    try {
      const tls = buildSecureContextOptions({
        certPath: join(dir, 'c.crt'),
        keyPath: join(dir, 'c.key'),
        caPath: join(dir, 'ca.pem'),
      })
      expect(Buffer.isBuffer(tls.ca)).toBe(true)
      expect((tls.ca as Buffer).toString()).toBe('CA_CERT')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('loads PFX from disk', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'bundle.p12': 'PFX_DATA' })
    try {
      const tls = buildSecureContextOptions({ pfxPath: join(dir, 'bundle.p12') })
      expect(Buffer.isBuffer(tls.pfx)).toBe(true)
      expect((tls.pfx as Buffer).toString()).toBe('PFX_DATA')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('sets passphrase with cert+key', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'c.crt': 'CERT', 'c.key': 'KEY' })
    try {
      const tls = buildSecureContextOptions({
        certPath: join(dir, 'c.crt'),
        keyPath: join(dir, 'c.key'),
        passphrase: 'the-secret',
      })
      expect(tls.passphrase).toBe('the-secret')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('sets passphrase with pfx', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'bundle.p12': 'PFX' })
    try {
      const tls = buildSecureContextOptions({ pfxPath: join(dir, 'bundle.p12'), passphrase: 'pfx-secret' })
      expect(tls.passphrase).toBe('pfx-secret')
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })

  it('sets servername', () => {
    const tls = buildSecureContextOptions({ servername: 'override.example.com' })
    expect(tls.servername).toBe('override.example.com')
  })

  it('sets minVersion', () => {
    const tls = buildSecureContextOptions({ minVersion: 'TLSv1.3' })
    expect(tls.minVersion).toBe('TLSv1.3')
  })

  it('does not set cert/key/ca/pfx when not provided', () => {
    const tls = buildSecureContextOptions({})
    expect(tls.cert).toBeUndefined()
    expect(tls.key).toBeUndefined()
    expect(tls.ca).toBeUndefined()
    expect(tls.pfx).toBeUndefined()
  })

  it('sets all options together with cert+key+ca', () => {
    const dir = makeTempDir()
    writeFakeFiles(dir, { 'c.crt': 'CERT_DATA', 'c.key': 'KEY_DATA', 'ca.pem': 'CA_DATA' })
    try {
      const tls = buildSecureContextOptions({
        certPath: join(dir, 'c.crt'),
        keyPath: join(dir, 'c.key'),
        caPath: join(dir, 'ca.pem'),
        passphrase: 'super-secret',
        minVersion: 'TLSv1.3',
        servername: 'mcp.example.com',
        rejectUnauthorized: false,
      })
      expect((tls.cert as Buffer).toString()).toBe('CERT_DATA')
      expect((tls.key as Buffer).toString()).toBe('KEY_DATA')
      expect((tls.ca as Buffer).toString()).toBe('CA_DATA')
      expect(tls.passphrase).toBe('super-secret')
      expect(tls.minVersion).toBe('TLSv1.3')
      expect(tls.servername).toBe('mcp.example.com')
      expect(tls.rejectUnauthorized).toBe(false)
    } finally {
      rmSync(dir, { recursive: true, force: true })
    }
  })
})

// ---------------------------------------------------------------------------
// buildMtlsDispatcher
// ---------------------------------------------------------------------------
describe('buildMtlsDispatcher', () => {
  it('returns an undici Agent instance', async () => {
    // We can't easily import UndiciAgent class in ESM without a type trick,
    // so just assert it's an object with a dispatch method.
    const dispatcher = buildMtlsDispatcher({})
    expect(dispatcher).toBeDefined()
    expect(typeof dispatcher.dispatch).toBe('function')
    await dispatcher.close()
  })

  it('creates dispatcher with rejectUnauthorized=false when specified', async () => {
    const dispatcher = buildMtlsDispatcher({ rejectUnauthorized: false })
    expect(dispatcher).toBeDefined()
    await dispatcher.close()
  })
})
