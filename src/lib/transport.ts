import { fetch as undiciFetch, type Agent as UndiciAgent } from 'undici'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'
import { SSEClientTransport } from '@modelcontextprotocol/sdk/client/sse.js'
import type { Transport } from '@modelcontextprotocol/sdk/shared/transport.js'
import { buildMtlsDispatcher, hasMtlsConfig, type MtlsOptions } from './mtls.js'
import type { TransportStrategy } from './args.js'
import { debugLog, log } from './log.js'

function resolveRequestUrl(input: Parameters<typeof fetch>[0]): URL {
  if (input instanceof URL) return input
  if (typeof input === 'string') return new URL(input)
  return new URL(input.url)
}

/**
 * Build a fetch implementation that routes through undici, optionally attaches
 * our mTLS dispatcher, and refuses redirects or origin pivots so a remote MCP
 * endpoint cannot bounce the client to an unexpected host.
 */
function buildOutboundFetch(expectedOrigin: string, dispatcher?: UndiciAgent): typeof fetch {
  return ((input: Parameters<typeof fetch>[0], init?: RequestInit) => {
    const requestUrl = resolveRequestUrl(input)
    if (requestUrl.origin !== expectedOrigin) {
      debugLog('blocked outbound request to unexpected origin', {
        expectedOrigin,
        actualOrigin: requestUrl.origin,
      })
      throw new Error('Refusing outbound request to an unexpected origin')
    }

    const merged = {
      ...(init ?? {}),
      redirect: 'error',
      ...(dispatcher ? { dispatcher } : {}),
    } as RequestInit & { dispatcher?: UndiciAgent }

    return undiciFetch(
      input as Parameters<typeof undiciFetch>[0],
      merged as Parameters<typeof undiciFetch>[1],
    ).then(async (response) => {
      if (!response.url) {
        await response.body?.cancel().catch(() => {})
        throw new Error('Response URL is missing; cannot verify origin')
      }
      const responseUrl = new URL(response.url)
      if (responseUrl.origin !== expectedOrigin) {
        debugLog('blocked redirect to unexpected origin', {
          expectedOrigin,
          actualOrigin: responseUrl.origin,
        })
        await response.body?.cancel().catch(() => {})
        throw new Error('Remote server redirected to an unexpected origin')
      }
      return response as unknown as Response
    })
  }) as typeof fetch
}

export interface BuildTransportOptions {
  serverUrl: string
  headers: Record<string, string>
  strategy: TransportStrategy
  mtls: MtlsOptions
  /**
   * When true (default), the selected transport is started before being
   * returned so protocol errors can drive fallback to the alternate transport.
   * Set false when the caller hands the transport to an SDK `Client`, whose
   * `connect()` will call `start()` itself — starting twice throws.
   */
  autoStart?: boolean
}

/**
 * Connect to the remote MCP server using the configured strategy. Returns the
 * first transport that successfully starts. When the first attempt fails with
 * a recoverable protocol error, the fallback transport is tried.
 */
export async function connectToRemoteServer({
  serverUrl,
  headers,
  strategy,
  mtls,
  autoStart = true,
}: BuildTransportOptions): Promise<Transport> {
  let dispatcher: UndiciAgent | undefined
  if (hasMtlsConfig(mtls)) {
    dispatcher = buildMtlsDispatcher(mtls)
    log('mTLS enabled for outbound requests')
  } else {
    debugLog('no mTLS configuration supplied; using default fetch')
  }

  const url = new URL(serverUrl)
  const outboundFetch = buildOutboundFetch(url.origin, dispatcher)
  const requestInit: RequestInit = { headers }

  const buildHttp = () =>
    new StreamableHTTPClientTransport(url, {
      requestInit,
      fetch: outboundFetch,
    })

  const buildSse = () =>
    new SSEClientTransport(url, {
      requestInit,
      eventSourceInit: { fetch: outboundFetch },
      fetch: outboundFetch,
    })

  const order: Array<'http' | 'sse'> =
    strategy === 'http-only' || strategy === 'http-first'
      ? ['http', 'sse']
      : ['sse', 'http']
  const allowFallback = strategy === 'http-first' || strategy === 'sse-first'

  if (!autoStart) {
    const kind = order[0]
    log(`Building ${kind === 'http' ? 'Streamable HTTP' : 'SSE'} transport (caller will start)`)
    return kind === 'http' ? buildHttp() : buildSse()
  }

  const attempt = async (label: string, build: () => Transport): Promise<Transport> => {
    const transport = build()
    try {
      await transport.start()
      log(`Connected using ${label} transport`)
      return transport
    } catch (err) {
      await transport.close().catch(() => {})
      throw err
    }
  }

  let lastError: unknown
  for (let i = 0; i < order.length; i++) {
    const kind = order[i]
    try {
      return await attempt(kind === 'http' ? 'Streamable HTTP' : 'SSE', kind === 'http' ? buildHttp : buildSse)
    } catch (err) {
      lastError = err
      log(`${kind} transport failed:`, err instanceof Error ? err.message : err)
      if (!allowFallback) break
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Unable to establish remote transport')
}
