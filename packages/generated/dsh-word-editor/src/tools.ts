/**
 * Model-facing tools of @deepseek-ai/dsh-word-editor: `read`, `find`,
 * `str_replace`, `add_to`, `delete`, `formula_scan`, `formula_convert`. Each
 * is a thin wrapper over the {@link EditorCoordinator} and {@link DocxSession}
 * with a model-shaped result. All edits happen in the session's working copy;
 * nothing touches the source until a final save.
 * @module @deepseek-ai/dsh-word-editor/tools
 */

import type { Context } from '@deepseek-ai/cordis'
import type { Agent } from '@deepseek-ai/dsh-agent'
import { defineTool, type JsonValue } from '@deepseek-ai/dsh-tools'
import { readFile } from 'node:fs/promises'
import type { EditorCoordinator } from './coordinator.js'
import { hasZeroWidth, normalizeLinearMath } from './services/formula.js'
import { runFormulaCleanup } from './workflow/formula-cleanup.js'
import type { FormulaCandidate } from './types.js'

/** Render any tool value as indented JSON text. */
function renderJson(_args: unknown, value: JsonValue): [{ type: 'text'; text: string }] {
  return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
}

/** Project an arbitrary data value to a lossless JSON value for tool output. */
function toJson(value: unknown): JsonValue {
  return JSON.parse(JSON.stringify(value)) as JsonValue
}

/** Tool: open a source .docx (or create a working copy from the template). */
export function openTool(coordinator: EditorCoordinator, configTemplate: string) {
  return defineTool({
    name: 'word_open',
    description: [
      'Open a source .docx for editing, or create a fresh working copy from the configured template.',
      'Provide source_path to edit an existing document (edits go to a working copy; nothing is overwritten until save). With template=true, a copy of the configured template is created for writing a new manuscript.',
      'Call word_open before editing; word_read reflects the opened working copy and reports its document_path.',
    ].join(' '),
    parameters: {
      source_path: { type: 'string', description: 'Absolute path of the source .docx to open for editing.' },
      from_template: { type: 'boolean', description: 'Create a working copy from the configured template instead of opening a source file.' },
    },
    output: {
      schema: { type: 'json', description: 'The open result: the working copy path and whether it was created from the template.' },
      render: renderJson,
    },
    async execute(args: { source_path?: string | undefined; from_template?: boolean | undefined }) {
      const useTemplate = args.from_template === true
      if (useTemplate) {
        if (configTemplate === '') throw new Error('open(from_template) requires a configured template; set word-editor.template')
        coordinator.openTemplate(configTemplate)
        return toJson({ document_path: configTemplate, from_template: true })
      }
      if (args.source_path === undefined || args.source_path === '') {
        throw new Error('open requires a source_path, or from_template=true with a configured template')
      }
      coordinator.openSource(args.source_path)
      return toJson({ document_path: args.source_path, from_template: false })
    },
  })
}

/** Tool: atomically save the working copy to a new document and return the link. */
export function saveTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_save',
    description: [
      'Atomically save the working copy to a new .docx next to the source (name `{base}-edited-{timestamp}.docx`) and return its real path and clickable local link.',
      'The source is checked against its open-time bytes and a changed source refuses the save. Returns a short change summary from the audit trail. The source file is never overwritten.',
    ].join(' '),
    parameters: {},
    output: {
      schema: { type: 'json', description: 'The save result: status, document_path, document_link, summary, change count, and warnings.' },
      render: renderJson,
    },
    async execute() {
      const { path, tocRefreshed } = coordinator.save()
      const audits = coordinator.audits()
      const summary = audits.length === 0
        ? 'no edits recorded'
        : `${audits.length} edit(s) applied`
      return toJson({
        status: 'completed',
        document_path: path,
        document_link: `[打开修改后的文档](${path})`,
        summary,
        changes: audits.length,
        warnings: tocRefreshed ? [] : ['Word was unavailable; the TOC field is left for Word to refresh on open'],
      })
    },
  })
}

/** Tool: read the working document's full structure with target ids. */
export function readTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_read',
    description: [
      'Return the working document\'s full block structure: every paragraph, heading, table (rows/cells), content control, OMath, and section property, in document order, each with its session target_id, style, and content.',
      'Body paragraphs return only their first sentence preview plus structure flags (contains formula/picture/field); non-body elements and all table-cell paragraphs return their full text.',
      'Call word_read first to see the whole document and collect target_ids; use word_find to read a specific paragraph in full.',
    ].join(' '),
    parameters: {},
    output: {
      schema: { type: 'json', description: 'The read result: { document_path, truncated, elements }. Body paragraphs show content_preview; table cells appear under their table\'s children.' },
      render: renderJson,
    },
    async execute() {
      return toJson(coordinator.read())
    },
  })
}

/** Tool: find a paragraph by id or by local text. */
export function findTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_find',
    description: [
      'Read a paragraph in full by its target_id, or find all paragraphs containing a substring, and return each match\'s full content, style, parent, formula/picture/field children, and neighbor previews.',
      'Provide id, content, or both. With both, only the named paragraph is checked and must contain the substring. No argument returns a parameter error. A non-paragraph id returns a type error.',
    ].join(' '),
    parameters: {
      id: {
        type: 'string',
        description: 'The target_id of the paragraph to read in full (from word_read).',
      },
      content: {
        type: 'string',
        description: 'A substring to search for across full paragraph texts.',
      },
    },
    output: {
      schema: { type: 'json', description: 'Matching paragraph records. Empty when the id/content combination did not match.' },
      render: renderJson,
    },
    async execute(args: { id?: string | undefined; content?: string | undefined }) {
      return toJson(coordinator.find(args.id, args.content))
    },
  })
}

/** Tool: exact text replacement of a paragraph. */
export function strReplaceTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_str_replace',
    description: [
      'Replace an exact substring of a paragraph (or its whole text) with new content, then audit before/after and styles.',
      'old_content must appear exactly in the target, else the edit is refused. Multi-line content is split into separate paragraphs (never embedded as newlines in one paragraph). style defaults to keep and preserves formatting; only whitelisted styles may be named.',
      'Refuses plain-text replacement across a formula, drawing, or field — use the formula tools instead.',
    ].join(' '),
    parameters: {
      target_id: { type: 'string', required: true, description: 'The paragraph target_id to edit.' },
      old_content: { type: 'string', required: true, description: 'The exact existing text to replace.' },
      content: { type: 'string', required: true, description: 'The replacement text; \\n splits into separate paragraphs.' },
      style: { type: 'string', description: 'Logical style to apply to the result (default keep).' },
    },
    output: {
      schema: { type: 'json', description: 'The edit audit record (location, before, after, styles, flags).' },
      render: renderJson,
    },
    async execute(args: { target_id: string; old_content: string; content: string; style?: string | undefined }) {
      const style = (args.style ?? 'keep') as import('./types.js').LogicalStyle
      return toJson(coordinator.strReplace(args.target_id, args.old_content, args.content, style))
    },
  })
}

/** Tool: add content at a paragraph, cell, table row, or the whole document. */
export function addToTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_add_to',
    description: [
      'Add content at a paragraph, cell, table row, or the whole document.',
      'For a paragraph/cell with is_new_para=true, insert a new paragraph (applying the logical style); with false, append text inside the paragraph. For target_id document use position start/end.',
      'To add a table ROW, target_id must be a row (tN-rM); pass content_cells (one string per column) and the target row is cloned before/after it, preserving widths, borders, shading, merges, and height. For a paragraph/cell target, use content as free text.',
      'The table keeps its dedicated table style; rows are never rebuilt from a default table.',
    ].join(' '),
    parameters: {
      target_id: { type: 'string', required: true, description: 'document, a paragraph/cell target_id, or a table-row target_id (tN-rM) to clone.' },
      content: { type: 'string', description: 'Free text to add to a paragraph/cell (or the whole document). Optional when target_id is a table row.' },
      content_cells: { type: 'array', description: 'For a table-row target_id: one cell value per column, in order.', items: { type: 'string' } },
      style: { type: 'string', description: 'Logical style for new content (default keep).' },
      position: { type: 'string', enum: ['before', 'after', 'start', 'end'], description: 'Placement anchor (default after). Required start/end when targeting document.' },
      is_new_para: { type: 'boolean', description: 'Whether to create a new paragraph instead of appending inside the target.' },
    },
    output: {
      schema: { type: 'json', description: 'The edit audit record.' },
      render: renderJson,
    },
    async execute(args: {
      target_id: string
      content?: string | undefined
      content_cells?: string[] | undefined
      style?: string | undefined
      position?: string | undefined
      is_new_para?: boolean | undefined
    }) {
      const style = (args.style ?? 'keep') as import('./types.js').LogicalStyle
      const position = (args.position ?? 'after') as import('./services/session.js').AddPosition
      if (args.content === undefined && args.content_cells === undefined) {
        throw new Error('word_add_to requires content (for a paragraph/cell/document) or content_cells (for a table row)')
      }
      const body = args.content_cells ?? args.content ?? ''
      return toJson(coordinator.addTo(args.target_id, body, style, position, args.is_new_para ?? false))
    },
  })
}

/** Tool: delete exact text, or a whole paragraph/table-row/table. */
export function deleteTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_delete',
    description: [
      'Delete an exact substring of a target, or remove a whole paragraph, table row, or table.',
      'Omitting content deletes the entire target; with content, only the exact text is removed. Optionally assert the current style with style (a mismatch refuses). Deleting a table row keeps the remaining rows\' borders, merges, and table style. No implicit delete-all.',
    ].join(' '),
    parameters: {
      target_id: { type: 'string', required: true, description: 'The paragraph/table-row/table target_id to delete.' },
      content: { type: 'string', description: 'Optional exact text to delete from the target.' },
      style: { type: 'string', description: 'Optional assertion on the target\'s current logical style.' },
    },
    output: {
      schema: { type: 'json', description: 'The edit audit record.' },
      render: renderJson,
    },
    async execute(args: { target_id: string; content?: string | undefined; style?: string | undefined }) {
      const style = args.style === undefined ? undefined : (args.style as import('./types.js').LogicalStyle)
      return toJson(coordinator.delete(args.target_id, args.content, style))
    },
  })
}

/** Tool: scan for not-yet-converted formulas (LaTeX) in the document. */
export function formulaScanTool(coordinator: EditorCoordinator, ctx: Context, provider: string) {
  return defineTool({
    name: 'word_formula_scan',
    description: [
      'Scan the document (or one target) for LaTeX / OLaTeX that is not yet a Word OMath, returning candidates with source spans, display kind, and confidence.',
      'Candidates a static scanner cannot trust are handed to a cleanup subagent that normalizes them (stripping markdown, zero-width chars, and split-run noise) and returns normalized_latex. Existing OMath is always protected and never re-scanned.',
      'Call word_formula_convert with returned candidate_ids to build them up as native Word OMath.',
    ].join(' '),
    parameters: {
      target_id: { type: 'string', description: 'Optional target to scan; the whole document when omitted.' },
    },
    output: {
      schema: { type: 'json', description: 'Detected formula candidates with candidate_id, target_id, source span, display, confidence, reason, and normalized_latex (when cleaned).' },
      render: renderJson,
    },
    async execute(args: { target_id?: string | undefined }, exec) {
      const found = coordinator.scan(args.target_id)
      const ambiguous = found.filter(c => c.confidence < 0.8 || hasZeroWidth(c.source_text))
      if (ambiguous.length > 0) {
        const agent = exec.agent as Agent | undefined
        const session = coordinator.sessionDoc
        const paragraph = session.resolve(ambiguous[0]!.target_id)
        try {
          const cleaned = await runFormulaCleanup(
            ctx,
            provider,
            agent,
            exec.signal,
            {
              candidates: ambiguous,
              paragraphText: session.textOf(paragraph),
              omathMasked: normalizeLinearMath(session.textOf(paragraph)),
            },
          )
          const merged: FormulaCandidate[] = found.map((c) => {
            const hit = cleaned.candidates.find(cc => cc.source_start === c.source_start && cc.source_end === c.source_end)
            return hit === undefined ? c : { ...c, normalized_latex: hit.normalized_latex, confidence: hit.confidence, display: hit.display }
          })
          return toJson(merged)
        } catch (error: unknown) {
          return toJson(found.map(c => ({ ...c, reason: `${c.reason}; cleanup subagent unavailable (${error instanceof Error ? error.message : String(error)})` })))
        }
      }
      return toJson(found)
    },
  })
}

/** Tool: convert confirmed formula candidates to native Word OMath. */
export function formulaConvertTool(coordinator: EditorCoordinator, ctx: Context) {
  return defineTool({
    name: 'word_formula_convert',
    description: [
      'Convert confirmed formula candidates (from word_formula_scan) to native Word OMath using Microsoft Word automation on this Windows host.',
      'Candidates below minimum_confidence are skipped with a warning. Requires Microsoft Word installed; when it is unavailable this returns a runtime-environment error and stores nothing (LaTeX is never kept as a fake conversion).',
      'After conversion the working copy is reloaded so the new OMath is protected from a later word_formula_scan.',
    ].join(' '),
    parameters: {
      candidate_ids: { type: 'array', required: true, description: 'candidate_id values to convert.', items: { type: 'string' } },
      minimum_confidence: { type: 'number', description: 'Candidates below this 0..1 confidence are skipped (default 0).' },
    },
    output: {
      schema: { type: 'json', description: 'Conversion summary: converted and skipped counts plus warnings.' },
      render: renderJson,
    },
    async execute(args: { candidate_ids: string[]; minimum_confidence?: number | undefined }, exec) {
      return toJson(await coordinator.convert(args.candidate_ids, args.minimum_confidence ?? 0, ctx, exec.signal))
    },
  })
}

/** Tool: generate a fresh document from a Markdown manuscript and a template. */
export function generateFromMarkdownTool(coordinator: EditorCoordinator, configTemplate: string) {
  return defineTool({
    name: 'word_generate',
    description: [
      'Generate a new .docx from a Markdown manuscript and a template, in one pass: the plugin parses the Markdown itself (headings, body paragraphs, lists, tables, images, and inline math $...$ / $\\)...\\($ / block `$$...$$`) and reshapes a copy of the template into a body that uses the template\'s styles and page layout.',
      'Formula text is written as plain LaTeX (delimiters stripped); converting those to native Word OMath is done separately with word_formula_scan + word_formula_convert.',
      'Provide markdown_path (and optionally template_path to override the configured default). Cover and TOC are not generated — the caller handles those. Returns the output document link plus a structured outline (headings, paragraph/table/reference/image counts) so you can confirm the structure without reading the whole document.',
    ].join(' '),
    parameters: {
      markdown_path: {
        type: 'string',
        required: true,
        description: 'Absolute path of the Markdown manuscript to parse and convert.',
      },
      template_path: {
        type: 'string',
        description: 'Optional template .docx whose styles/layout the output follows; defaults to the configured word-editor.template.',
      },
    },
    output: {
      schema: { type: 'json', description: 'The generate result: output document path and link plus the parsed structure outline.' },
      render: renderJson,
    },
    async execute(args: { markdown_path: string; template_path?: string | undefined }) {
      const markdownText = await readFile(args.markdown_path, 'utf8')
      const tmpl = args.template_path ?? configTemplate
      if (tmpl === '') throw new Error('word_generate needs a template: pass template_path or set word-editor.template')
      const { path, outline } = coordinator.generateFromMarkdown(markdownText, args.markdown_path, tmpl)
      return toJson({
        status: 'completed',
        document_path: path,
        document_link: `[打开生成的文档](${path})`,
        outline,
      })
    },
  })
}

/** Tool: convert bracket citations in an existing document to superscript runs. */
export function superscriptTool(coordinator: EditorCoordinator) {
  return defineTool({
    name: 'word_superscript',
    description: [
      'Convert every bracket citation like [1], [1-4], [1,2,5], or [1、2] in an existing .docx to genuine superscript runs, preserving all other inline formatting (bold, italic, font size).',
      'Provide source_path (absolute path of the .docx to convert). The plugin opens that document, converts the citations in its body and table cells, and saves a new `-superscripted-<timestamp>.docx` next to the source; the source is never overwritten.',
      'The reference-LIST paragraphs (styled 参考文献) are left untouched so their leading [1] markers stay as list numbering, not superscripts. Returns the output link and the conversion count.',
    ].join(' '),
    parameters: {
      source_path: {
        type: 'string',
        required: true,
        description: 'Absolute path of the .docx whose bracket citations to superscript.',
      },
    },
    output: {
      schema: { type: 'json', description: 'The superscript result: output document path and link plus the number of citations converted.' },
      render: renderJson,
    },
    async execute(args: { source_path: string }) {
      const { path, converted } = coordinator.superscript(args.source_path)
      return toJson({
        status: 'completed',
        document_path: path,
        document_link: `[打开转换后的文档](${path})`,
        converted,
      })
    },
  })
}
