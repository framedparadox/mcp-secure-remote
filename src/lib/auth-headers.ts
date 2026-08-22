import { validateHttpHeader } from './args.js'

export interface AuthOptions {
  bearer?: string
  basic?: string
  apiKey?: string
  apiKeyHeader?: string
}

export function buildAuthHeaders(auth: AuthOptions): Record<string, string> {
  if (auth.bearer && auth.basic) {
    throw new Error('Use only one of --auth-bearer or --auth-basic, not both.')
  }

  const headers: Record<string, string> = {}

  if (auth.bearer) {
    validateHttpHeader('Authorization', `Bearer ${auth.bearer}`)
    headers.Authorization = `Bearer ${auth.bearer}`
  } else if (auth.basic) {
    if (!auth.basic.includes(':')) {
      throw new Error('--auth-basic expects "username:password".')
    }
    const encoded = Buffer.from(auth.basic, 'utf8').toString('base64')
    validateHttpHeader('Authorization', `Basic ${encoded}`)
    headers.Authorization = `Basic ${encoded}`
  }

  if (auth.apiKey) {
    const headerName = auth.apiKeyHeader ?? 'X-Api-Key'
    validateHttpHeader(headerName, auth.apiKey)
    headers[headerName] = auth.apiKey
  }

  return headers
}

export function mergeAuthHeaders(
  headers: Record<string, string>,
  auth: AuthOptions,
): Record<string, string> {
  const authHeaders = buildAuthHeaders(auth)
  return { ...authHeaders, ...headers }
}
