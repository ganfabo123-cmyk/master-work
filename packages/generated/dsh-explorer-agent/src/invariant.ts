/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-explorer-agent`.
 * @module @deepseek-ai/dsh-explorer-agent/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-explorer-agent'

/** Cordis companion plugin name. */
export const name = 'explorer-agent-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: the workflow keeps only per-question process-local
 * result records keyed by the incoming question, and every record's lifetime
 * is bounded by the subagent run it belongs to (cleaned in `run`'s finally);
 * nothing durable or cross-plugin references them.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
