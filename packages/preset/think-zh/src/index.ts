/**
 * A single non-complete system-prompt section directing intermediate reasoning
 * and drafting to Chinese, independent of the persona and tool guidance.
 *
 * Mounted inside an agent preset (or any systemPrompt-scoped context) it
 * contributes one extra section while leaving every other section — persona,
 * harness identity, and the English tool guidance — untouched. `complete` is
 * deliberately not set, so by design this package never suppresses other
 * sections: it is the companion in an A/B language experiment, not a prompt
 * replacement.
 * @module @deepseek-ai/dsh-think-zh
 */

import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-system-prompt'

/** Cordis plugin name. */
export const name = 'think-zh'

/** The prompt registry this row contributes to. */
export const inject = ['systemPrompt']

/** Section order: after the persona (0), before tool guidance (100+). */
export const THINK_ZH_ORDER = 50

/** Stable section name this package owns. */
export const THINK_ZH_SECTION = 'i18n:think-zh'

/** Chinese guidance for intermediate reasoning and drafting. */
export const THINK_ZH_TEXT =
  '在逐步推演、草拟方案、以及以草稿或中间形式记录思考与推理过程时，请使用中文书写。'
  + '这一指令只约束你的中间思考与草稿语言，不约束面向用户的最终答复；'
  + '最终答复的语言仍遵循用户所使用语言。'

/**
 * Register the Chinese-thinking section for the mounting context's scope.
 * @param ctx - a context carrying the `systemPrompt` registry.
 */
export function apply(ctx: Context): void {
  ctx.effect(() => ctx.systemPrompt.section({
    name: THINK_ZH_SECTION,
    order: THINK_ZH_ORDER,
    text: THINK_ZH_TEXT,
  }), 'thinkZh.section()')
}
