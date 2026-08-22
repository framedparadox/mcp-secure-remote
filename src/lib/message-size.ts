import { log } from './log.js'

/** Default JSON-RPC message size cap (10 MiB). */
export const DEFAULT_MAX_MESSAGE_BYTES = 10 * 1024 * 1024

const MAX_MESSAGE_BYTES_FLOOR = 1024
const MAX_MESSAGE_BYTES_CEILING = 256 * 1024 * 1024

export function parseMaxMessageBytes(raw: string, flag: string): number {
  const value = Number.parseInt(raw, 10)
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${flag} must be a positive integer`)
  }
  if (value < MAX_MESSAGE_BYTES_FLOOR) {
    throw new Error(`${flag} must be at least ${MAX_MESSAGE_BYTES_FLOOR} bytes`)
  }
  if (value > MAX_MESSAGE_BYTES_CEILING) {
    throw new Error(`${flag} must not exceed ${MAX_MESSAGE_BYTES_CEILING} bytes`)
  }
  return value
}

export function messageByteLength(message: unknown): number {
  if (message instanceof Error) return 0
  return Buffer.byteLength(JSON.stringify(message), 'utf8')
}

export function isWithinMessageLimit(message: unknown, maxBytes: number): boolean {
  return messageByteLength(message) <= maxBytes
}

export function logOversizedMessage(direction: string, size: number, maxBytes: number): void {
  log(`Dropping oversized ${direction} message (${size} bytes > ${maxBytes} byte limit)`)
}
