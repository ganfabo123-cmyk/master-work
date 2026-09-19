/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-experiment-state`.
 * @module @deepseek-ai/dsh-experiment-state/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-experiment-state'

/** Cordis companion plugin name. */
export const name = 'experiment-state-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: the store holds only process-local experiment records
 * keyed by generated ids; reference integrity between a child and its parent
 * is enforced at the single write point (`ExperimentStore.create` rejects an
 * unknown parent id and no record is ever deleted), and nothing durable or
 * cross-plugin references the store.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
