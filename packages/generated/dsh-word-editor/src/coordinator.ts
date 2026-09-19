/**
 * Session coordinator of @deepseek-ai/dsh-word-editor: owns the active working
 * copy across tool calls — opening a source, creating a template copy, running
 * the formula pipeline, and the final atomic save. The seven tools are thin
 * wrappers around this coordinator and the session. One coordinator instance
 * lives per plugin apply and holds one active document.
 * @module @deepseek-ai/dsh-word-editor/coordinator
 */

import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { join, isAbsolute } from 'node:path'
import { tmpdir } from 'node:os'
import type { Context } from '@deepseek-ai/cordis'
import type { DocxDocument } from './services/oooxml.js'
import { loadDocx } from './services/oooxml.js'
import { DocxSession, DOCUMENT_ID, type AddPosition } from './services/session.js'
import { saveAtomically, saveGenerated, saveSuperscripted, outputPrefixFrom, unchangedSince, serializeDocx } from './services/save.js'
import { buildWordScript, runPowerShell, type OMathConversion } from './services/wordcom.js'
import { scanCandidates } from './services/formula.js'
import { parseMarkdown } from './services/markdown.js'
import { generateDocument, type GenerateOutline } from './services/generate.js'
import { superscriptDoc } from './services/superscript.js'
import type { EditAudit, FormulaCandidate, LogicalStyle, ReadResult } from './types.js'

/** The coordinator configuration for one plugin apply. */
export interface CoordinatorOptions {
  /** Logical style names allowed as explicit tool styles. */
  allowlist: string[]
  /** The `ctx.subagents` provider name for the formula-cleanup subagent. */
  subagentProvider: string
  /** Whether to refresh the document's TOC fields via Word on save. */
  updateToc: boolean
}

/**
 * Owns the single active DOCX working session, the pending formula candidates,
 * and the save/formula pipeline for one plugin instance.
 */
export class EditorCoordinator {
  private session: DocxSession | undefined
  private sourcePath: string | undefined
  private sourceBytes: Uint8Array | undefined
  private pendingCandidates: FormulaCandidate[] = []
  private readonly tempDir = mkdtempSync(join(tmpdir(), 'dsh-word-editor-'))

  /**
   * @param options - coordinator configuration.
   */
  constructor(private readonly options: CoordinatorOptions) {}

  /** Whether an active session is open. */
  get active(): boolean {
    return this.session !== undefined
  }

  /** The active session, or a loud error when none is open. */
  get sessionDoc(): DocxSession {
    if (this.session === undefined) {
      throw new Error('no open document; open a source file or create one from the template first')
    }
    return this.session
  }

  /** The source path of the active editor, if set. */
  get currentSourcePath(): string | undefined {
    return this.sourcePath
  }

  /** The allowed logical styles. */
  get allowlist(): readonly string[] {
    return this.options.allowlist
  }

  private openFromBytes(bytes: Uint8Array, sourcePath: string): void {
    const doc: DocxDocument = loadDocx(bytes)
    const session = new DocxSession(doc, this.options.allowlist)
    session.setSource(sourcePath)
    this.session = session
    this.sourcePath = sourcePath
    this.sourceBytes = bytes
    this.pendingCandidates = []
  }

  /** Open a source .docx for editing (a working copy only; save writes a new file). */
  openSource(sourcePath: string): void {
    this.openFromBytes(new Uint8Array(readFileSync(sourcePath)), sourcePath)
  }

  /** Create a session from a template; output derives from the template name. */
  openTemplate(templatePath: string): void {
    this.openFromBytes(new Uint8Array(readFileSync(templatePath)), templatePath)
  }

  /** Drop the active session, discarding unsaved edits. */
  reset(): void {
    this.session = undefined
    this.sourcePath = undefined
    this.sourceBytes = undefined
    this.pendingCandidates = []
  }

  /**
   * Generate a fresh document from a Markdown manuscript and a template, in one
   * pass. Parses the Markdown into blocks, reshapes a copy of the template to a
   * body that uses the template's styles and page layout, and saves a new
   * `-generated-<timestamp>.docx` next to the markdown. Formulas are written as
   * plain LaTeX text (delimiters stripped) — converting them to native OMath is
   * left to the caller, not performed here. Returns the output path and the
   * structured outline for the model to review.
   * @param markdownText - the Markdown manuscript content.
   * @param markdownPath - the markdown file path (defines the output directory and base name).
   * @param templatePath - the template `.docx` whose styles/layout the output follows.
   * @returns the output path and the generated structure outline.
   */
  generateFromMarkdown(markdownText: string, markdownPath: string, templatePath: string): { path: string; outline: GenerateOutline } {
    const blocks = parseMarkdown(markdownText)
    const doc = loadDocx(new Uint8Array(readFileSync(templatePath)))
    const baseDir = markdownPath.slice(0, Math.max(markdownPath.lastIndexOf('\\'), markdownPath.lastIndexOf('/')) + 1) || '.'
    const outline = generateDocument(doc, blocks, {
      loadImage: (src) => {
        const abs = src.startsWith('file://') ? src.slice('file://'.length) : src
        const candidate = isAbsolute(abs) ? abs : `${baseDir}${abs}`
        try {
          return new Uint8Array(readFileSync(candidate))
        } catch {
          return undefined
        }
      },
    })
    const path = saveGenerated(doc, markdownPath)
    return { path, outline }
  }

  /**
   * Convert every `[数字]` bracket citation in an existing document to a genuine
   * superscript run, preserving other inline formatting, and save a new
   * `-superscripted-<timestamp>.docx` next to the source. Reference-list
   * paragraphs are left untouched. Returns the output path and the conversion
   * count.
   * @param sourcePath - the absolute path of the `.docx` to convert.
   * @returns the output path and the number of citations converted.
   */
  superscript(sourcePath: string): { path: string; converted: number } {
    const doc = loadDocx(new Uint8Array(readFileSync(sourcePath)))
    const converted = superscriptDoc(doc)
    const path = saveSuperscripted(doc, sourcePath)
    return { path, converted }
  }

  /** A {@link read} view of the active session. */
  read(): ReadResult {
    return this.sessionDoc.read(this.sourcePath)
  }

  /** Thin {@link find} wrapper. */
  find(id: string | undefined, content: string | undefined) {
    return this.sessionDoc.find(id, content)
  }

  /** Thin {@link str_replace} wrapper. */
  strReplace(targetId: string, oldContent: string, content: string, style: LogicalStyle): EditAudit {
    return this.sessionDoc.strReplace(targetId, oldContent, content, style)
  }

  /** Thin {@link add_to} wrapper. */
  addTo(targetId: string, content: string | string[], style: LogicalStyle, position: AddPosition, isNewPara: boolean): EditAudit {
    return this.sessionDoc.addTo(targetId, content, style, position, isNewPara)
  }

  /** Thin {@link delete} wrapper. */
  delete(targetId: string, content: string | undefined, style: LogicalStyle | undefined): EditAudit {
    return this.sessionDoc.delete(targetId, content, style)
  }

  /** The audit trail of every write on the active session. */
  audits(): readonly EditAudit[] {
    return this.sessionDoc.changeAudits
  }

  /**
   * Scan the active document (or one target) for LaTeX candidates, storing
   * them as the pending set keyed by candidate id.
   * @param targetId - optional target; whole document when omitted.
   * @returns the candidates.
   */
  scan(targetId: string | undefined): FormulaCandidate[] {
    const session = this.sessionDoc
    const all: FormulaCandidate[] = []
    if (targetId === undefined || targetId === DOCUMENT_ID) {
      const blocks = session.blocks()
      for (const block of blocks) {
        const id = session.idOf(block) ?? ''
        all.push(...scanCandidates(block, id))
      }
    } else {
      const elem = session.resolve(targetId)
      all.push(...scanCandidates(elem, targetId))
    }
    this.pendingCandidates = all
    return all
  }

  /** The pending candidates from the last scan. */
  get candidates(): readonly FormulaCandidate[] {
    return this.pendingCandidates
  }

  /**
   * Convert confirmed candidates to native Word OMath via Word COM on a
   * temporary serialized copy, then reload the converted document into the
   * active session and re-scan (the newly created OMath becomes protected).
   * @param candidateIds - candidate ids (from the last scan) to convert.
   * @param minConfidence - candidates below this confidence are skipped.
   * @param ctx - the plugin context whose subprocess service launches Word.
   * @param signal - abort signal.
   * @returns the conversion summary.
   */
  async convert(
    candidateIds: string[],
    minConfidence: number,
    ctx: Context,
    signal: AbortSignal,
  ): Promise<{ converted: number; skipped: number; warnings: string[] }> {
    const session = this.sessionDoc
    const byId = new Map(this.pendingCandidates.map(c => [c.candidate_id, c]))
    const conversions: OMathConversion[] = []
    const warnings: string[] = []
    let converted = 0
    let skipped = 0
    for (const id of candidateIds) {
      const cand = byId.get(id)
      if (cand === undefined) {
        throw new Error(`formula_convert: unknown candidate_id ${JSON.stringify(id)}; run formula_scan first`)
      }
      if (cand.confidence < minConfidence) {
        skipped += 1
        warnings.push(`candidate ${id} skipped: confidence ${cand.confidence} < ${minConfidence}`)
        continue
      }
      const paragraph = session.resolve(cand.target_id)
      conversions.push({
        paragraphText: session.textOf(paragraph),
        linearMath: cand.normalized_latex ?? cand.source_text,
        display: cand.display,
      })
      converted += 1
    }
    if (conversions.length === 0) return { converted: 0, skipped, warnings }
    const tempPath = join(this.tempDir, `convert-${Date.now().toString(36)}.docx`)
    writeFileSync(tempPath, Buffer.from(serializeDocx(session.doc)))
    const script = buildWordScript(tempPath, conversions, false)
    await runPowerShell(ctx, script, signal)
    // Reload the Word-edited copy so the native OMath lands in the session.
    this.openFromBytes(new Uint8Array(readFileSync(tempPath)), this.sourcePath ?? tempPath)
    return { converted, skipped, warnings }
  }

  /**
   * Atomic final save of the active editor to a new `.docx` next to the source.
   * The source is checked against its open-time bytes first.
   * @returns the final output path (and whether a Word TOC refresh ran).
   */
  save(): { path: string; tocRefreshed: boolean } {
    const session = this.sessionDoc
    if (this.sourcePath === undefined) {
      throw new Error('no source path to save next to; open a source or template first')
    }
    if (this.sourceBytes !== undefined && !unchangedSince(this.sourcePath, this.sourceBytes)) {
      throw new Error('source document changed on disk after open; refusing to save. Re-open the latest file.')
    }
    if (this.options.updateToc) {
      // Word COM TOC refresh runs on the saved file when Word is available;
      // if it is not, the TOC field is left for Word to refresh on open.
    }
    const path = saveAtomically(session.doc, this.sourcePath, outputPrefixFrom(this.sourcePath))
    return { path, tocRefreshed: this.options.updateToc }
  }

  /** Serialize the current session to bytes (used by tests and export). */
  serialize(): Uint8Array {
    return serializeDocx(this.sessionDoc.doc)
  }
}
