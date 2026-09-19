/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-swebench`.
 * @module @deepseek-ai/dsh-swebench/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-swebench'

/** Cordis companion plugin name. */
export const name = 'swebench-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: the plugin only registers stateless tools whose
 * effects are one throwaway docker run per call — every generated run
 * directory is removed in the tool's `finally`, the case registry is rebuilt
 * per call from the manifest on disk, and nothing durable or cross-plugin
 * references this plugin's state.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
