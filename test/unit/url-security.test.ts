import { describe, expect, it } from 'vitest'
import { validateRemoteUrl } from '../../src/lib/url-security.js'

describe('validateRemoteUrl', () => {
  it('allows public hosts', () => {
    expect(() => validateRemoteUrl(new URL('https://example.com/mcp'), { allowPrivateUrls: false })).not.toThrow()
  })

  it('blocks localhost by default', () => {
    expect(() => validateRemoteUrl(new URL('https://localhost/mcp'), { allowPrivateUrls: false })).toThrow(
      'private or restricted host',
    )
  })

  it('blocks loopback IPs by default', () => {
    expect(() => validateRemoteUrl(new URL('https://127.0.0.1:8443/mcp'), { allowPrivateUrls: false })).toThrow(
      'private or restricted host',
    )
  })

  it('allows private hosts with --allow-private-urls', () => {
    expect(() =>
      validateRemoteUrl(new URL('https://127.0.0.1:8443/mcp'), { allowPrivateUrls: true }),
    ).not.toThrow()
  })
})
