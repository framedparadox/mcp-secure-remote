import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { debugLog, isDebug, log, setDebug } from '../../src/lib/log.js'

afterEach(() => {
  setDebug(false)
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// setDebug / isDebug
// ---------------------------------------------------------------------------
describe('setDebug / isDebug', () => {
  it('isDebug returns false initially', () => {
    expect(isDebug()).toBe(false)
  })

  it('isDebug returns true after setDebug(true)', () => {
    setDebug(true)
    expect(isDebug()).toBe(true)
  })

  it('isDebug returns false after setDebug(false)', () => {
    setDebug(true)
    setDebug(false)
    expect(isDebug()).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// log
// ---------------------------------------------------------------------------
describe('log', () => {
  beforeEach(() => {
    vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
  })

  it('writes to stderr', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('hello')
    expect(spy).toHaveBeenCalled()
  })

  it('writes to stderr, not stdout', () => {
    const stdoutSpy = vi.spyOn(process.stdout, 'write').mockImplementation(() => true)
    log('hello')
    expect(stdoutSpy).not.toHaveBeenCalled()
  })

  it('includes the message in the output', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('test-message')
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('test-message')
  })

  it('includes a timestamp prefix', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('msg')
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toMatch(/\[mcp-secure-remote \d{4}-\d{2}-\d{2}T/)
  })

  it('serializes extra string arguments', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('prefix', 'extra')
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('extra')
  })

  it('serializes extra object arguments as JSON', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('prefix', { key: 'value' })
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('"key"')
    expect(output).toContain('"value"')
  })

  it('serializes Error using stack/message', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    const err = new Error('oops')
    log('prefix', err)
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('oops')
  })

  it('serializes Error without stack using message', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    const err = new Error('no-stack')
    delete err.stack
    log('prefix', err)
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('no-stack')
  })

  it('handles multiple extra arguments', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('msg', 'a', 'b', 'c')
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('a')
    expect(output).toContain('b')
    expect(output).toContain('c')
  })

  it('output ends with newline', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    log('msg')
    const output = (spy.mock.calls[0][0] as string)
    expect(output.endsWith('\n')).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// debugLog
// ---------------------------------------------------------------------------
describe('debugLog', () => {
  it('does NOT write to stderr when debug is disabled', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    debugLog('should not appear')
    expect(spy).not.toHaveBeenCalled()
  })

  it('writes to stderr when debug is enabled', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    setDebug(true)
    debugLog('debug message')
    expect(spy).toHaveBeenCalled()
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('[debug]')
    expect(output).toContain('debug message')
  })

  it('includes extra arguments in debug output', () => {
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true)
    setDebug(true)
    debugLog('key', { data: 42 })
    const output = (spy.mock.calls[0][0] as string)
    expect(output).toContain('42')
  })
})
