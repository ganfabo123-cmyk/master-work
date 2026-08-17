/**
 * Model-facing, user-approved cross-workspace session history search.
 *
 * The opt-in tool searches the live-preferred logical session corpus across
 * every workspace through `ctx.sessionQuery`. Unlike the workspace-scoped
 * `session_search` in `@deepseek-ai/dsh-tool-session-query`, this tool reaches
 * sessions created in other working directories, so every call first passes a
 * per-call user-approval gate through `ctx.approval`; only an `'allowed-once'`
 * answer authorizes the search, and its outcome plus the audit pair land on
 * the caller's durable session log.
 *
 * @module @deepseek-ai/dsh-tool-cross-session-search
 */

import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type {} from '@deepseek-ai/dsh-system-prompt'
import '@deepseek-ai/dsh-user-approval'
import { crossSessionSearchParameters } from './input.ts'
import { executeCrossSessionSearch } from './operations.ts'
import { presentCrossSessionSearchCall } from './presentation.ts'

/** Cordis plugin name used by Loader diagnostics. */
export const name = 'tool-cross-session-search'

/** Capability services required by the model-facing consumer. */
export const inject = ['tools', 'systemPrompt', 'sessionQuery', 'approval']

/** Default maximum number of approved cross-workspace hits returned by one call. */
export const DEFAULT_MAX_SEARCH_RESULTS = 20

/** Deployment-owned search count bound. */
export interface Config {
  /** Maximum approved cross-workspace hits returned by one search call. Defaults to 20. */
  maxSearchResults?: number
}

/** Schemastery config for Loader defaults and generated configuration docs. */
export const Config: z<Config> = z.object({
  maxSearchResults: z.number().step(1).min(1).default(DEFAULT_MAX_SEARCH_RESULTS),
})

interface ResolvedConfig {
  readonly maxSearchResults: number
}

const TEXT_OUTPUT = {
  schema: { type: 'string' as const },
  render: (_args: unknown, value: string) => [{ type: 'text' as const, text: value }],
}

const PROMPT_TEXT =
  'Use session_cross_search to find relevant work across prior sessions in ANY workspace. '
  + 'Each call asks the user for approval before searching. Results are cursor-free and bounded. '
  + 'The search reaches sessions created in other working directories only after the user approves this call.'

/** Register the cross-workspace search tool and its model guidance. */
export function apply(ctx: Context, config: Config): void {
  const resolved = resolveConfig(config)
  ctx.systemPrompt.section({
    name: 'tool:cross-session-search',
    order: 114,
    text: PROMPT_TEXT,
  })

  ctx.tools.register(defineTool({
    name: 'cross_session_search',
    description: 'Search prior sessions across every workspace and return the strongest matching event from each session. Requires per-call user approval.',
    parameters: crossSessionSearchParameters,
    output: TEXT_OUTPUT,
    execute: (args, exec) => executeCrossSessionSearch(ctx, args, exec, resolved.maxSearchResults),
    presentCall: args => presentCrossSessionSearchCall(args),
  }))
}

function resolveConfig(config: Config): ResolvedConfig {
  const maxSearchResults = config.maxSearchResults ?? DEFAULT_MAX_SEARCH_RESULTS
  if (!Number.isSafeInteger(maxSearchResults) || maxSearchResults < 1) {
    throw new TypeError('tool-cross-session-search: maxSearchResults must be a positive safe integer')
  }
  return { maxSearchResults }
}
