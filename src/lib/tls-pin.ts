import { createHash, X509Certificate } from 'node:crypto'
import { checkServerIdentity, type PeerCertificate } from 'node:tls'

export function normalizeTlsPin(pin: string): string {
  const trimmed = pin.trim()
  if (trimmed.startsWith('sha256/')) {
    return trimmed.slice('sha256/'.length)
  }
  return trimmed
}

export function parseTlsPins(rawPins: string[], flag: string): string[] {
  const pins = rawPins.map(normalizeTlsPin).filter(Boolean)
  if (pins.length === 0) {
    throw new Error(`${flag} requires at least one non-empty SHA-256 SPKI pin`)
  }
  for (const pin of pins) {
    if (!/^[A-Za-z0-9+/=]+$/.test(pin) && !/^[0-9a-fA-F]{64}$/.test(pin)) {
      throw new Error(
        `${flag} pin "${pin}" must be base64 or hex SHA-256 of the server certificate SPKI`,
      )
    }
  }
  return pins
}

export function computeSpkiPin(certDer: Buffer): { base64: string; hex: string } {
  const x509 = new X509Certificate(certDer)
  const spki = x509.publicKey.export({ type: 'spki', format: 'der' }) as Buffer
  const hash = createHash('sha256').update(spki).digest()
  return { base64: hash.toString('base64'), hex: hash.toString('hex') }
}

export function buildTlsPinChecker(pins: string[], servername?: string) {
  const normalized = pins.map(normalizeTlsPin)
  return (hostname: string, cert: PeerCertificate): Error | undefined => {
    const identityError = checkServerIdentity(servername ?? hostname, cert)
    if (identityError) return identityError

    const raw = cert.raw
    if (!raw) {
      return new Error('Certificate missing raw bytes for SPKI pin verification')
    }

    const { base64, hex } = computeSpkiPin(raw)
    if (!normalized.some((pin) => pin === base64 || pin.toLowerCase() === hex)) {
      return new Error('TLS certificate SPKI pin mismatch')
    }
    return undefined
  }
}
