/**
 * Cross-session search result rendering and generic tool-call presentation.
 *
 * @module @deepseek-ai/dsh-tool-cross-session-search/presentation
 */

import type { SessionSearchHit } from '@deepseek-ai/dsh-session-query'
import type { GenericCallView } from '@deepseek-ai/dsh-tools'

/** One bounded collection of cross-workspace hits. */
export interface CrossSessionCollection {
  readonly items: readonly SessionSearchHit[]
  readonly capped: boolean
}

/**
 * Render cross-session search hits as plain text for the model. Each displayed
 * hit carries its owning workspace (`cwd`), folded title, and best-match
 * excerpt so the model can reason about cross-workspace context without a
 * second lookup.
 * @param query - the normalized query that produced the hits.
 * @param collected - the bounded hit collection.
 * @param titles - folded title text per hit session id.
 * @returns model-facing text.
 */
export function formatCrossSessionSearch(
  query: string,
  collected: CrossSessionCollection,
  titles: ReadonlyMap<string, string> = new Map(),
): string {
  if (collected.items.length === 0) {
    return `No session matches for "${query}" in any workspace.`
  }
  const lines = [`Cross-workspace session search results (${collected.items.length}) for "${query}":`]
  for (const [index, hit] of collected.items.entries()) {
    const cwd = hit.header.cwd === undefined ? '(no workspace)' : hit.header.cwd
    const title = titles.get(hit.header.id) ?? 'untitled'
    const availability = [
      hit.live ? 'live' : undefined,
      hit.persisted ? 'persisted' : undefined,
    ].filter((value): value is string => value !== undefined).join(', ') || 'unavailable'
    lines.push(
      '',
      `${index + 1}. Session ${hit.header.id} — ${title}`,
      `   Workspace: ${cwd}`,
      `   Created: ${formatTime(hit.header.createdAt)}`,
      `   Availability: ${availability}`,
      `   Best match: seq ${hit.bestMatch.seq} | ${hit.bestMatch.type} | ${formatTime(hit.bestMatch.time)}`,
      `   Snippet: ${hit.bestMatch.snippet}`,
    )
  }
  if (collected.capped) {
    lines.push('', 'Result cap reached. Narrow the query or add filters to find additional matches.')
  }
  return lines.join('\n')
}

/**
 * Pending-state call card for the search tool.
 * @param args - model-supplied arguments.
 * @returns a generic search card.
 */
export function presentCrossSessionSearchCall(args: { readonly query: string }): GenericCallView {
  return {
    card: 'generic',
    kind: 'search',
    title: 'Search prior sessions across all workspaces',
    rawInput: args.query,
  }
}

function formatTime(timestamp: number): string {
  if (timestamp <= 0) return String(timestamp)
  return new Date(timestamp).toISOString()
}
