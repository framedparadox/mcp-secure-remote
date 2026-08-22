import { describe, expect, it } from 'vitest'
import { buildAuthHeaders, mergeAuthHeaders } from '../../src/lib/auth-headers.js'

describe('buildAuthHeaders', () => {
  it('builds bearer auth', () => {
    expect(buildAuthHeaders({ bearer: 'tok' })).toEqual({ Authorization: 'Bearer tok' })
  })

  it('builds basic auth', () => {
    expect(buildAuthHeaders({ basic: 'user:pass' })).toEqual({
      Authorization: 'Basic dXNlcjpwYXNz',
    })
  })

  it('rejects bearer and basic together', () => {
    expect(() => buildAuthHeaders({ bearer: 'tok', basic: 'u:p' })).toThrow('only one')
  })
})

describe('mergeAuthHeaders', () => {
  it('lets --header override auth env for the same header', () => {
    const merged = mergeAuthHeaders({ Authorization: 'Bearer override' }, { bearer: 'tok' })
    expect(merged.Authorization).toBe('Bearer override')
  })

  it('rejects conflicting auth and header values by letting --header win', () => {
    const merged = mergeAuthHeaders({ Authorization: 'Bearer other' }, { bearer: 'tok' })
    expect(merged.Authorization).toBe('Bearer other')
  })
})
