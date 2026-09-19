/**
 * Package-owned invariant companion for `@deepseek-ai/dsh-word-editor`.
 * @module @deepseek-ai/dsh-word-editor/invariant
 */

import type { Context } from '@deepseek-ai/cordis'
import type { InvariantInstaller } from '@deepseek-ai/dsh-invariants'

const PACKAGE_NAME = '@deepseek-ai/dsh-word-editor'

/** Cordis companion plugin name. */
export const name = 'word-editor-invariant'
/** Service required before the companion can reserve package ownership. */
export const inject = ['invariants'] as const

/**
 * No runtime invariant: the plugin registers stateless model tools over one
 * process-local editing session plus a one-shot Markdown generator. Session
 * state is owned by the applying coordinator closure and discarded on reload;
 * nothing durable or cross-plugin references the working copy, and all
 * registrations are disposed by the apply effect.
 */
const install: InvariantInstaller = () => {}

/**
 * Register this package's invariant companion.
 * @param ctx - Cordis context carrying the invariant service.
 * @returns the installed registration's disposer after setup succeeds.
 */
export const apply = (ctx: Context): Promise<() => void> =>
  Promise.resolve(ctx.invariants.register(PACKAGE_NAME, install))
