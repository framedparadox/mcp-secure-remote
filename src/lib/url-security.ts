import { isIP } from 'node:net'

export interface UrlSecurityOptions {
  allowPrivateUrls: boolean
}

/**
 * Reject private, link-local, and metadata hosts unless explicitly allowed.
 * Blocks SSRF-style targeting of internal services from agent configs.
 */
export function validateRemoteUrl(url: URL, options: UrlSecurityOptions): void {
  if (options.allowPrivateUrls) return

  const host = normalizeHostname(url.hostname)
  if (isRestrictedHost(host)) {
    throw new Error(
      `Refusing to connect to private or restricted host "${host}"; ` +
        'pass --allow-private-urls for local/dev targets.',
    )
  }
}

function normalizeHostname(hostname: string): string {
  const trimmed = hostname.trim().toLowerCase()
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return trimmed.slice(1, -1)
  }
  return trimmed
}

function isRestrictedHost(host: string): boolean {
  if (host === 'localhost' || host.endsWith('.localhost')) return true
  if (host === '0.0.0.0' || host === '::') return true

  const version = isIP(host)
  if (version === 4) return isPrivateIpv4(host)
  if (version === 6) return isPrivateIpv6(host)

  return false
}

function isPrivateIpv4(host: string): boolean {
  const parts = host.split('.').map((part) => Number(part))
  if (parts.some((part) => Number.isNaN(part) || part < 0 || part > 255)) return false

  const [a, b] = parts
  if (a === 10) return true
  if (a === 127) return true
  if (a === 169 && b === 254) return true
  if (a === 172 && b >= 16 && b <= 31) return true
  if (a === 192 && b === 168) return true
  if (a === 100 && b >= 64 && b <= 127) return true
  if (a === 0) return true
  return false
}

function isPrivateIpv6(host: string): boolean {
  const normalized = host.toLowerCase()
  if (normalized === '::1') return true
  if (normalized.startsWith('fc') || normalized.startsWith('fd')) return true
  if (normalized.startsWith('fe80')) return true
  return false
}
