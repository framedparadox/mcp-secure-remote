let debugEnabled = false

export function setDebug(enabled: boolean): void {
  debugEnabled = enabled
}

export function isDebug(): boolean {
  return debugEnabled
}

/** Log to stderr so we never pollute the stdio MCP channel on stdout. */
export function log(message: string, ...rest: unknown[]): void {
  const prefix = `[mcp-secure-remote ${new Date().toISOString()}]`
  if (rest.length > 0) {
    process.stderr.write(`${prefix} ${message} ${rest.map(serialize).join(' ')}\n`)
  } else {
    process.stderr.write(`${prefix} ${message}\n`)
  }
}

export function debugLog(message: string, ...rest: unknown[]): void {
  if (!debugEnabled) return
  log(`[debug] ${message}`, ...rest)
}

function serialize(value: unknown): string {
  if (value instanceof Error) return value.stack ?? value.message
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
