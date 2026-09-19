/**
 * @deepseek-ai/dsh-markdown-to-csv — convert a markdown table into a
 * downloadable CSV. The calling agent normalizes the user's pasted text into a
 * clean markdown table before invoking the tool; the tool parses it locally,
 * serializes RFC 4180 CSV, and serves it over a token-gated route on the web
 * server, returning the download URL.
 * @module @deepseek-ai/dsh-markdown-to-csv
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { Config, type Config as PluginConfig } from './config.js'
import { toCsv, toCsvBody, sanitizeFilename } from './csv.js'
import { downloadRouteHandler, DownloadStore } from './download.js'
import { parseMarkdownTable } from './parse.js'

export const name = 'markdown-to-csv'
export const inject = ['tools'] as const
export { Config }
export type { PluginConfig }

/** The web-route prefix under which every generated download lives. */
export const DOWNLOAD_ROUTE_PREFIX = '/api/md-table-csv'

export function apply(ctx: Context, config: PluginConfig): void {
  const ttlMs = (config.downloadTtlSeconds ?? 3600) * 1000
  const maxPendingDownloads = config.maxPendingDownloads ?? 128
  const store = new DownloadStore({ ttlMs, maxEntries: maxPendingDownloads })

  let routeMounted = false
  let routeDisposer: (() => void) | undefined
  const mountRoute = (): void => {
    if (routeMounted) return
    const server = ctx.get('webServer')
    if (server === undefined) return
    routeDisposer = server.register({
      kind: 'prefix',
      path: DOWNLOAD_ROUTE_PREFIX,
      handler: downloadRouteHandler(store, DOWNLOAD_ROUTE_PREFIX),
    })
    routeMounted = true
  }

  ctx.effect(() => {
    const disposeTool = ctx.tools.register(defineTool({
      name: 'markdown_to_csv',
      description: [
        'Convert a markdown table into a downloadable CSV file.',
        'Normalize the user\'s raw markdown into a clean markdown table FIRST (fix broken pipes, missing header delimiter rows, inconsistent column counts, and stray formatting),',
        'then call this tool with that table; it parses it locally, serializes RFC 4180 CSV (UTF-8 BOM), and returns a clickable download URL.',
        'Present the returned URL to the user as a markdown download link.',
      ].join(' '),
      parameters: {
        markdown: {
          type: 'string',
          required: true,
          description: 'The markdown table to convert (header row with pipe-separated cells, optional delimiter row, then the data rows).',
        },
        filename: {
          type: 'string',
          description: 'Optional CSV filename (default "table.csv"); sanitized to a safe basename before download.',
        },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            filename: { type: 'string', required: true, description: 'The CSV filename served by the download link.' },
            downloadUrl: { type: 'string', required: true, description: 'The http URL that downloads the CSV with Content-Disposition: attachment.' },
            rowCount: { type: 'integer', required: true, description: 'Number of data rows in the converted table.' },
            columnCount: { type: 'integer', required: true, description: 'Number of columns in the converted table.' },
          },
        },
        render: (_args, value) => [{
          type: 'text',
          text: `${value.rowCount} rows × ${value.columnCount} columns converted to CSV. Download link: ${value.downloadUrl}`,
        }],
      },
      async execute(args) {
        mountRoute()
        const server = ctx.get('webServer')
        if (server === undefined) {
          throw new Error(
            'markdown_to_csv: the download route requires the web server; '
            + 'compose @deepseek-ai/dsh-host-webserver in this process',
          )
        }
        const markdown = args.markdown.trim()
        if (markdown.length === 0) {
          throw new Error('markdown must be a non-empty string')
        }
        const table = parseMarkdownTable(markdown)
        const filename = sanitizeFilename(args.filename ?? 'table.csv')
        const token = store.put(toCsvBody(toCsv(table.columns, table.rows)), filename)
        return {
          filename,
          downloadUrl: `http://${server.host}:${server.port}${DOWNLOAD_ROUTE_PREFIX}/${token}`,
          rowCount: table.rows.length,
          columnCount: table.columns.length,
        }
      },
    }))
    mountRoute()
    return () => {
      disposeTool()
      if (routeDisposer !== undefined) routeDisposer()
      routeMounted = false
      store.clear()
    }
  }, 'markdown-to-csv.tools')
}
