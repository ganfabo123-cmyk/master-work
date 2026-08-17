/**
 * Cross-session search orchestration and the user-approval gate.
 *
 * The approval gate is the single, non-bypassable entry to
 * `ctx.sessionQuery.searchSessions`: no cross-workspace hit is ever fetched
 * unless the composed approval answerers granted `'allowed-once'` for THAT
 * call. A rejected, cancelled, or unavailable outcome fails closed before any
 * provider interaction, and each gate emits a durable `approval/asked` +
 * `approval/decided` audit pair on the caller session.
 *
 * @module @deepseek-ai/dsh-tool-cross-session-search/operations
 */

import type { Context } from '@deepseek-ai/cordis'
import { HarnessError } from '@deepseek-ai/dsh-llm'
import type { SessionId } from '@deepseek-ai/dsh-session'
import type {
  SessionResultFilter,
  SessionSearchCursor,
  SessionSearchHit,
  SessionSearchPage,
} from '@deepseek-ai/dsh-session-query'
import { SessionQueryError } from '@deepseek-ai/dsh-session-query'
import type { ToolRunContext } from '@deepseek-ai/dsh-tools'
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval'
import { type CrossSessionSearchArgs, materializeSessionIds, normalizeQuery } from './input.ts'
import { formatCrossSessionSearch } from './presentation.ts'

/** Model-safe outcome sentence for each non-grant approval outcome. */
const DENIAL_MESSAGES: Readonly<Record<Exclude<ApprovalOutcome, 'allowed-once'>, string>> = {
  rejected: 'The user declined cross-workspace session search; no results were returned.',
  cancelled: 'Cross-workspace session search was cancelled; no results were returned.',
  unavailable: 'Cross-workspace session search is unavailable: no approval answerer is composed.',
}

/**
 * Request and enforce the per-call user-approval gate.
 * @param ctx - context carrying the approval service.
 * @param exec - the in-flight tool execution (agent, call id, signal).
 * @param query - the normalized search query shown to the answerer.
 * @throws {HarnessError} when the approval request throws or the outcome is
 *   anything other than `'allowed-once'`.
 */
async function requireApproval(
  ctx: Context,
  exec: ToolRunContext,
  query: string,
): Promise<void> {
  const agent = exec.agent
  if (agent === undefined) {
    throw new HarnessError(
      'cross-session search requires an agent-bound caller',
      'SESSION_CROSS_SEARCH_MISSING_AGENT',
    )
  }
  let outcome: ApprovalOutcome
  try {
    outcome = await ctx.approval.request({
      agent,
      toolName: 'cross_session_search',
      callId: exec.callId,
      reason: `Cross-workspace search over all persisted session history for query: ${query}`,
      signal: exec.signal,
    })
  } catch (error) {
    throw new HarnessError(
      'cross-session search could not obtain user approval',
      'SESSION_CROSS_SEARCH_APPROVAL_FAILED',
      { cause: error },
    )
  }
  if (outcome !== 'allowed-once') {
    throw new HarnessError(DENIAL_MESSAGES[outcome], 'SESSION_CROSS_SEARCH_DENIED')
  }
}

/**
 * Enforce the deployment max-hits cap in the service layer, independent of any
 * provider limit a backend fails to honor. The boolean `alreadyCapped` from the
 * page loop records whether more matches existed beyond the cap.
 */
function enforceCap(
  hits: readonly SessionSearchHit[],
  maxResults: number,
  alreadyCapped: boolean,
): { items: SessionSearchHit[]; capped: boolean } {
  if (hits.length > maxResults) {
    return { items: hits.slice(0, maxResults), capped: true }
  }
  return { items: [...hits], capped: alreadyCapped }
}

/**
 * Execute one approved cross-workspace full-text search and render text results.
 * @param ctx - context carrying the session-query service.
 * @param args - model-supplied search arguments.
 * @param exec - the tool execution context.
 * @param maxResults - deployment-owned result cap.
 * @returns rendered search result text.
 */
export async function executeCrossSessionSearch(
  ctx: Context,
  args: CrossSessionSearchArgs,
  exec: ToolRunContext,
  maxResults: number,
): Promise<string> {
  const query = normalizeQuery(args.query)
  if (exec.agent === undefined) {
    throw new HarnessError(
      'cross-session search requires an agent-bound caller',
      'SESSION_CROSS_SEARCH_MISSING_AGENT',
    )
  }
  // The gate MUST precede any session-query contact so an unwilling or
  // unavailable answerer never causes even a single look-up.
  await requireApproval(ctx, exec, query)

  const sessionFilters = buildSessionFilters(args)
  let cursor: SessionSearchCursor | undefined
  const collected: SessionSearchHit[] = []
  let capped = false
  while (true) {
    exec.signal.throwIfAborted()
    const page = await invokeSearch(ctx, exec, query, sessionFilters, cursor)
    exec.signal.throwIfAborted()
    for (const item of page.items) {
      if (collected.length >= maxResults) {
        capped = true
        break
      }
      collected.push(item)
    }
    if (capped || page.nextCursor === undefined) break
    cursor = page.nextCursor
  }
  const bounded = enforceCap(collected, maxResults, capped)
  const titles = await readTitles(ctx, exec, bounded.items.map(hit => hit.header.id))
  return formatCrossSessionSearch(query, bounded, titles)
}

/**
 * Fold the latest log-backed title for each unique hit session.
 * @param ctx - context carrying the session-query service.
 * @param exec - the tool execution context.
 * @param sessionIds - hit session ids to fold titles for.
 * @returns a per-session title map; failed folds degrade to the session id.
 */
async function readTitles(
  ctx: Context,
  exec: ToolRunContext,
  sessionIds: readonly SessionId[],
): Promise<ReadonlyMap<SessionId, string>> {
  const unique = [...new Set(sessionIds)]
  if (unique.length === 0) return new Map()
  const observations = await ctx.sessionQuery.readTitleSnapshots(unique, exec.signal)
  const titles = new Map<SessionId, string>()
  for (const observation of observations) {
    const text = observation.status === 'fulfilled'
      ? observation.value.title?.title ?? 'untitled'
      : 'untitled'
    titles.set(observation.sessionId, text)
  }
  return titles
}

/**
 * Build session metadata filters for a cross-workspace search. No `cwd` clause
 * is ever added, so the logical corpus spans every workspace.
 * @param args - model-supplied search arguments.
 * @returns ANDed session filters, cwd-free by construction.
 */
function buildSessionFilters(args: CrossSessionSearchArgs): SessionResultFilter[] {
  const filters: SessionResultFilter[] = []
  const idValues = materializeSessionIds(args.session_ids)
  if (idValues !== undefined) filters.push({ kind: 'id', values: idValues })
  const parentValues = materializeSessionIds(args.parent_session_ids)
  if (parentValues !== undefined || args.include_root_sessions === true) {
    const values: Array<SessionId | null> = [...(parentValues ?? [])]
    if (args.include_root_sessions === true) values.push(null)
    filters.push({ kind: 'parent', values })
  }
  const created = createdRange(args.created_at_from, args.created_at_to)
  if (created !== undefined) filters.push({ kind: 'created-at', ...created })
  return filters
}

/**
 * Materialize an inclusive epoch-millisecond created-at range from model ISO
 * timestamps.
 * @param from - optional ISO 8601 lower bound.
 * @param to - optional ISO 8601 upper bound.
 * @returns inclusive range, or undefined when neither bound is supplied.
 */
function createdRange(from: string | undefined, to: string | undefined): { from?: number; to?: number } | undefined {
  if (from === undefined && to === undefined) return undefined
  const fromValue = from === undefined ? undefined : parseIsoTimestamp(from)
  const toValue = to === undefined ? undefined : parseIsoTimestamp(to)
  if (fromValue !== undefined && toValue !== undefined && fromValue > toValue) {
    throw new SessionQueryError(
      'created_at_from must be less than or equal to created_at_to',
      'SESSION_QUERY_INVALID_FILTER',
    )
  }
  return {
    ...fromValue === undefined ? {} : { from: fromValue },
    ...toValue === undefined ? {} : { to: toValue },
  }
}

const ISO_TIMESTAMP =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|([+-])(\d{2}):(\d{2}))$/

function parseIsoTimestamp(value: string): number {
  const match = ISO_TIMESTAMP.exec(value)
  if (match === null) {
    throw new SessionQueryError(
      'workspace timestamps must be ISO 8601 with Z or a numeric offset',
      'SESSION_QUERY_INVALID_FILTER',
    )
  }
  const fraction = match[7] ?? ''
  const millisecondDigits = fraction.slice(0, 3).padEnd(3, '0')
  const normalized = `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}`
    + `:${match[6] ?? '00'}.${millisecondDigits}${match[8]}`
  const timestamp = Date.parse(normalized)
  if (!Number.isSafeInteger(timestamp)) {
    throw new SessionQueryError(
      'timestamp must be a valid ISO 8601 datetime',
      'SESSION_QUERY_INVALID_FILTER',
    )
  }
  return timestamp
}

/**
 * Invoke the session-query full-text provider for one page, forwarding the
 * caller signal for cancellation.
 */
async function invokeSearch(
  ctx: Context,
  exec: ToolRunContext,
  query: string,
  sessionFilters: readonly SessionResultFilter[],
  cursor: SessionSearchCursor | undefined,
): Promise<SessionSearchPage<SessionSearchHit>> {
  return ctx.sessionQuery.searchSessions({
    query,
    ...sessionFilters.length > 0 ? { sessionFilters } : {},
    ...cursor === undefined ? {} : { cursor },
  }, { signal: exec.signal })
}
