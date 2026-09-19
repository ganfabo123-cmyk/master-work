/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-detector`.
 * @module @deepseek-ai/dsh-detector/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-detector'

/** Cordis companion plugin name. */
export const name = 'detector-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: this plugin owns no data of its own — it registers a
 * system-prompt section and one model tool whose disposal is Cordis-effect
 * owned, and every child investigation runs on the `ctx.subagents` service
 * plus the `dsh-experiment-state` store, whose lifecycle and result contracts
 * the owning packages enforce; nothing durable or cross-plugin references
 * this package.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
