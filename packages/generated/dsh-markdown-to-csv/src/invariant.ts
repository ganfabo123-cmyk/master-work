/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-markdown-to-csv`.
 * @module @deepseek-ai/dsh-markdown-to-csv/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-markdown-to-csv'

/** Cordis companion plugin name. */
export const name = 'markdown-to-csv-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: the download store is process-local scratch whose
 * entries are reachable only through random tokens already delivered to the
 * model; nothing durable references them, and route teardown is the web
 * server's own lifecycle contract.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
