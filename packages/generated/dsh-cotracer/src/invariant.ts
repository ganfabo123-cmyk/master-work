/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-cotracer`.
 * @module @deepseek-ai/dsh-cotracer/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-cotracer'

/** Cordis companion plugin name. */
export const name = 'cotracer-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: this plugin owns no data of its own — it registers a
 * runtime skill whose disposal is Cordis-effect owned, and the composed
 * experiment tree, explorer results, and Detector runs belong to the
 * infrastructure plugins loaded beside it (`dsh-experiment-state`,
 * `dsh-explorer-agent`, `dsh-detector`), whose lifecycle and result contracts
 * those packages enforce; nothing durable or cross-plugin references this
 * package.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
