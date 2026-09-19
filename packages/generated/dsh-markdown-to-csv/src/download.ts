import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

/**
 * Token-gated in-memory download store and its web-route helpers. Every
 * conversion stores one BOM-prefixed CSV body under a random token; the route
 * resolves the token and streams it as an attachment.
 */

export interface StoredDownload {
  /** The BOM-prefixed CSV body as UTF-8 text. */
  readonly csv: string
  /** The safe basename used in the Content-Disposition header. */
  readonly filename: string
  readonly expiresAt: number
}

export interface DownloadStoreOptions {
  readonly ttlMs: number
  readonly maxEntries: number
}

export class DownloadStore {
  private readonly entries = new Map<string, StoredDownload>()

  constructor(private readonly options: DownloadStoreOptions) {}

  /**
   * Store a download body under a fresh random token, evicting expired
   * entries and then the oldest entries beyond the cap.
   * @param csv - The CSV body to serve.
   * @param filename - The safe download basename.
   * @param now - Clock source (test seam).
   * @returns The token.
   */
  put(csv: string, filename: string, now = Date.now()): string {
    this.evictExpired(now)
    const token = randomUUID()
    this.entries.set(token, { csv, filename, expiresAt: now + this.options.ttlMs })
    while (this.entries.size > this.options.maxEntries) {
      const oldest = this.entries.keys().next().value
      if (oldest === undefined) break
      this.entries.delete(oldest)
    }
    return token
  }

  /**
   * Resolve a token; an expired entry is removed on access.
   * @param token - The route token.
   * @param now - Clock source (test seam).
   * @returns The stored download, or undefined when unknown or expired.
   */
  resolve(token: string, now = Date.now()): StoredDownload | undefined {
    const entry = this.entries.get(token)
    if (entry === undefined) return undefined
    if (entry.expiresAt <= now) {
      this.entries.delete(token)
      return undefined
    }
    return entry
  }

  /** The number of currently stored downloads. */
  get size(): number {
    return this.entries.size
  }

  clear(): void {
    this.entries.clear()
  }

  private evictExpired(now: number): void {
    for (const [token, entry] of this.entries) {
      if (entry.expiresAt <= now) this.entries.delete(token)
    }
  }
}

/**
 * Extract the single token segment from a request pathname under a prefix
 * route, e.g. `/api/md-table-csv/<token>`.
 * @param pathname - The parsed request pathname.
 * @param prefix - The registered route prefix (no trailing slash).
 * @returns The token, or undefined when the path is not a token request.
 */
export function tokenFromPath(pathname: string, prefix: string): string | undefined {
  if (!pathname.startsWith(`${prefix}/`)) return undefined
  const rest = pathname.slice(prefix.length + 1)
  if (rest.length === 0 || rest.includes('/')) return undefined
  return rest
}

/**
 * A Content-Disposition header value with an ASCII fallback and an RFC 5987
 * UTF-8 filename, so non-ASCII names download correctly in modern browsers.
 * @param filename - The safe basename.
 * @returns The header value.
 */
export function contentDisposition(filename: string): string {
  const ascii = filename.replace(/[^\x20-\x7e]/g, '_')
  return `attachment; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(filename)}`
}

/**
 * The download route handler: resolve the token and stream the stored CSV
 * with attachment headers; unknown or expired tokens answer 404.
 * @param store - The download store.
 * @param prefix - The registered route prefix.
 * @returns The `ctx.webServer` route handler.
 */
export function downloadRouteHandler(store: DownloadStore, prefix: string): (req: IncomingMessage, res: ServerResponse) => void {
  return (req, res) => {
    let pathname: string
    try {
      pathname = new URL(req.url ?? '/', 'http://x').pathname
    } catch {
      res.writeHead(400)
      res.end('bad request')
      return
    }
    const token = tokenFromPath(pathname, prefix)
    const entry = token === undefined ? undefined : store.resolve(token)
    if (entry === undefined) {
      res.writeHead(404)
      res.end('not found')
      return
    }
    const body = Buffer.from(entry.csv, 'utf8')
    res.writeHead(200, {
      'content-type': 'text/csv; charset=utf-8',
      'content-disposition': contentDisposition(entry.filename),
      'content-length': String(body.length),
      'cache-control': 'no-store',
    })
    res.end(body)
  }
}
