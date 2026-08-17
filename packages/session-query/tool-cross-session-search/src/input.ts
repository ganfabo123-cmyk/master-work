/**
 * Cross-session search tool argument schema and normalization.
 *
 * @module @deepseek-ai/dsh-tool-cross-session-search/input
 */

import { SessionId } from '@deepseek-ai/dsh-session'
import { SessionQueryError } from '@deepseek-ai/dsh-session-query'

/** Model-supplied arguments for the cross-session search tool. */
export interface CrossSessionSearchArgs {
  /** Literal full-text query over prior session history in every workspace. */
  query: string
  /** Optional session ids to include. */
  session_ids?: string[]
  /** Inclusive timezone-qualified ISO 8601 creation-time lower bound. */
  created_at_from?: string
  /** Inclusive timezone-qualified ISO 8601 creation-time upper bound. */
  created_at_to?: string
  /** Optional direct parent session ids. */
  parent_session_ids?: string[]
  /** Include root sessions in the parent filter. */
  include_root_sessions?: boolean
}

/** Model-visible parameter schema for the cross-session search tool. */
export const crossSessionSearchParameters = {
  query: { type: 'string', required: true, description: 'Literal full-text query over prior session history in every workspace.' },
  session_ids: { type: 'array', items: { type: 'string' }, description: 'Optional session ids to include.' },
  created_at_from: { type: 'string', description: 'Inclusive timezone-qualified ISO 8601 creation-time lower bound.' },
  created_at_to: { type: 'string', description: 'Inclusive timezone-qualified ISO 8601 creation-time upper bound.' },
  parent_session_ids: { type: 'array', items: { type: 'string' }, description: 'Optional direct parent session ids.' },
  include_root_sessions: { type: 'boolean', description: 'Include sessions with no parent in the parent filter.' },
} as const

/**
 * Normalize the model search query for the provider.
 * @param value - raw query string.
 * @returns collapsed single-space trimmed text.
 * @throws {SessionQueryError} when the query is empty or contains NUL.
 */
export function normalizeQuery(value: string): string {
  const query = value.trim().replace(/\s+/gu, ' ')
  if (query.length === 0) {
    throw new SessionQueryError(
      'cross-session-search query must contain non-whitespace text',
      'SESSION_QUERY_INVALID_QUERY',
    )
  }
  if (query.includes('\0')) {
    throw new SessionQueryError(
      'cross-session-search query must not contain NUL',
      'SESSION_QUERY_INVALID_QUERY',
    )
  }
  return query
}

/**
 * Materialize an optional, deduplicated session-id set for a parent filter.
 * @param values - raw string session ids, or undefined for no filter.
 * @returns branded session ids, or undefined when no parent filter was supplied.
 * @throws {SessionQueryError} when the array is empty.
 */
export function materializeSessionIds(values: readonly string[] | undefined): SessionId[] | undefined {
  if (values === undefined) return undefined
  if (values.length === 0) {
    throw new SessionQueryError(
      'session_ids must contain at least one value when supplied',
      'SESSION_QUERY_INVALID_FILTER',
    )
  }
  return [...new Set(values.map(SessionId))]
}
