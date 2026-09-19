/**
 * @deepseek-ai/dsh-word-editor — a personal Word (.docx) quick-editing plugin.
 * Exposes `read` / `find` / `str_replace` / `add_to` / `delete` /
 * `formula_scan` / `formula_convert` / `generate` model tools over a docx
 * working copy:
 * the caller agent reads the structure, plans, edits through session target
 * ids (pure OOXML with a style whitelist, table-row cloning, and atomic save),
 * and converts cleaned-up linear math to native Word OMath via Windows Word
 * COM. A formula-cleanup subagent handles ambiguous LaTeX when formula_scan
 * requests it. Nothing ever overwrites the source; output is a new file next
 * to it.
 * @module @deepseek-ai/dsh-word-editor
 */

import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
// Side-effect type imports: activate the `ctx.subprocess` and `ctx.subagents`
// declaration merges.
import type {} from '@deepseek-ai/dsh-subprocess'
import type {} from '@deepseek-ai/dsh-subagent'
import { EditorCoordinator } from './coordinator.js'
import { addToTool, deleteTool, findTool, formulaConvertTool, formulaScanTool, generateFromMarkdownTool, openTool, readTool, saveTool, strReplaceTool, superscriptTool } from './tools.js'
import type { LogicalStyle } from './types.js'

export const name = 'word-editor'
export const inject = ['tools', 'subprocess', 'subagents'] as const

/** Plugin configuration. */
export interface Config {
  /**
   * Absolute path of the default template `.docx` used when the model writes
   * a fresh manuscript without a source document (default empty: creation must
   * then name a template explicitly through read/open inputs).
   */
  template: string
  /**
   * Absolute path of the first-adapted template with the dedicated proposal
   * table style; mirrors the document used in the requirements.
   */
  proposalTableTemplate: string
  /**
   * Logical style names a write tool may set explicitly. The fixed mapping
   * (body→Normal (Web), heading_1→heading 2, …) is always available; these
   * are extra logical names from the template that may be addressed by name.
   */
  allowlist: string[]
  /** The `ctx.subagents` provider on which the formula-cleanup subagent runs. */
  subagentProvider: string
  /** Whether to refresh the document's TOC fields through Word on save (default true). */
  updateToc: boolean
}

export const Config: z<Config> = z.object({
  template: z.string().default(''),
  proposalTableTemplate: z.string().default(''),
  allowlist: z.array(z.string()).default(['reference', 'table_content']),
  subagentProvider: z.string().default('spawn'),
  updateToc: z.boolean().default(true),
})

/**
 * Assemble the coordinator and register the editing, formula, and generate
 * tools.
 * @param ctx - Cordis context with tools, subprocess, and subagents services.
 * @param config - plugin configuration.
 */
export function apply(ctx: Context, config: Config): void {
  const styles: LogicalStyle[] = ['body', 'heading_1', 'heading_2', 'heading_3', 'toc_1', 'toc_2', 'toc_3', 'table_content', 'reference']
  const coordinator = new EditorCoordinator({
    allowlist: [...new Set([...styles, ...config.allowlist])],
    subagentProvider: config.subagentProvider,
    updateToc: config.updateToc,
  })
  ctx.effect(() => {
    const disposers = [
      ctx.tools.register(openTool(coordinator, config.template)),
      ctx.tools.register(readTool(coordinator)),
      ctx.tools.register(findTool(coordinator)),
      ctx.tools.register(strReplaceTool(coordinator)),
      ctx.tools.register(addToTool(coordinator)),
      ctx.tools.register(deleteTool(coordinator)),
      ctx.tools.register(formulaScanTool(coordinator, ctx, config.subagentProvider)),
      ctx.tools.register(formulaConvertTool(coordinator, ctx)),
      ctx.tools.register(generateFromMarkdownTool(coordinator, config.template)),
      ctx.tools.register(superscriptTool(coordinator)),
      ctx.tools.register(saveTool(coordinator)),
    ]
    return () => {
      for (const dispose of disposers) dispose()
    }
  }, 'word-editor tools')
}

export { EditorCoordinator } from './coordinator.js'
export { DocxSession } from './services/session.js'
export { loadDocx } from './services/oooxml.js'
export { scanCandidates } from './services/formula.js'
export { buildWordScript } from './services/wordcom.js'
export { parseMarkdown, parseInline } from './services/markdown.js'
export { generateDocument, makeTable, makeStyledParagraph } from './services/generate.js'
export { superscriptDoc } from './services/superscript.js'
