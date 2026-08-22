import { describe, expect, it } from 'vitest'
import {
  DEFAULT_MAX_MESSAGE_BYTES,
  isWithinMessageLimit,
  messageByteLength,
  parseMaxMessageBytes,
} from '../../src/lib/message-size.js'

describe('message-size', () => {
  it('uses a 10 MiB default', () => {
    expect(DEFAULT_MAX_MESSAGE_BYTES).toBe(10 * 1024 * 1024)
  })

  it('parses valid byte limits', () => {
    expect(parseMaxMessageBytes('4096', '--max-message-bytes')).toBe(4096)
  })

  it('rejects invalid byte limits', () => {
    expect(() => parseMaxMessageBytes('0', '--max-message-bytes')).toThrow(/positive integer/)
    expect(() => parseMaxMessageBytes('abc', '--max-message-bytes')).toThrow(/positive integer/)
  })

  it('measures serialized JSON-RPC message size', () => {
    const message = { jsonrpc: '2.0', method: 'ping', id: 1 }
    expect(messageByteLength(message)).toBeGreaterThan(0)
    expect(isWithinMessageLimit(message, messageByteLength(message))).toBe(true)
    expect(isWithinMessageLimit(message, messageByteLength(message) - 1)).toBe(false)
  })
})
