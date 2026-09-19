/**
 * Superscript citation service of @deepseek-ai/dsh-word-editor: turns bracket
 * citation markers like `[1]`, `[1-4]`, `[1,2,5]` and `[1、2]` in a document's
 * body into genuine Word superscript runs (`w:vertAlign val="superscript"`),
 * preserving all other inline formatting (bold, italic, size, …). Reference
 * entries (paragraphs in the `参考文献` logical style) are left untouched — their
 * leading `[1]` markers are list numbering, not in-text citations. The source
 * is never modified; the caller saves a fresh copy.
 * @module @deepseek-ai/dsh-word-editor/services/superscript
 */

import { createEl, NS, classifyParagraph } from './oooxml.js'
import type { DocxDocument } from './oooxml.js'

/** A bracket digit-list citation: `[1]`, `[1-4]`, `[1,2,5]`, `[1、2]`, `[1, 2]`. */
const CITATION_RE = /(\[\d+(?:\s*[,\-、]\s*\d+)*\])/g

/**
 * Convert every bracket citation in the document's body (including table cells)
 * to a superscript run, preserving other inline formatting. Reference-styled
 * paragraphs are skipped. Paragraphs containing structural content (math,
 * drawing, field) or non-text runs (`w:br`/`w:tab`) are left untouched.
 * @param doc - the loaded document container to mutate.
 * @returns the number of citation markers converted.
 */
export function superscriptDoc(doc: DocxDocument): number {
  const body = Array.from(doc.document.getElementsByTagNameNS(NS.word, 'body'))[0]
  if (body === undefined) throw new Error('malformed document: no w:body')
  let converted = 0
  for (const p of Array.from(body.getElementsByTagNameNS(NS.word, 'p'))) {
    // A paragraph already in the reference-list style keeps its leading `[1]`
    // marker as list numbering, not a superscript citation.
    if (classifyParagraph(p, doc.styleMap) === 'reference') continue
    converted += superscriptParagraph(p, doc)
  }
  return converted
}

/** True when a paragraph carries structural content a text rewrite must not clear. */
function hasConflict(p: Element): boolean {
  return (
    p.getElementsByTagNameNS(NS.math, 'oMath').length > 0 ||
    p.getElementsByTagNameNS(NS.math, 'oMathPara').length > 0 ||
    p.getElementsByTagNameNS(NS.word, 'drawing').length > 0 ||
    p.getElementsByTagNameNS(NS.word, 'pict').length > 0 ||
    p.getElementsByTagNameNS(NS.word, 'fldChar').length > 0 ||
    p.getElementsByTagNameNS(NS.word, 'instrText').length > 0
  )
}

/**
 * Convert the citations of one paragraph. A paragraph is only rewritten when
 * it has no structural conflict and every direct child run is a plain text run
 * (`w:rPr` + `w:t` only); otherwise it is skipped untouched.
 * @param p - the paragraph element.
 * @param doc - the document container for element creation.
 * @returns the number of citations converted in this paragraph.
 */
function superscriptParagraph(p: Element, doc: DocxDocument): number {
  if (hasConflict(p)) return 0
  const runs = Array.from(p.childNodes).filter((n): n is Element => n.nodeType === 1 && (n as Element).localName === 'r')
  if (runs.length === 0) return 0
  for (const r of runs) {
    const kids = Array.from(r.childNodes).filter((n): n is Element => n.nodeType === 1)
    if (kids.some(k => k.localName !== 'rPr' && k.localName !== 't')) return 0
  }
  // Concatenate text and record each run's absolute span.
  const pieces: Array<{ run: Element; text: string; start: number }> = []
  let cursor = 0
  for (const r of runs) {
    const text = wText(r)
    pieces.push({ run: r, text, start: cursor })
    cursor += text.length
  }
  const whole = pieces.map(x => x.text).join('')
  if (whole.length === 0) return 0

  const spans: Array<{ start: number; end: number }> = []
  CITATION_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = CITATION_RE.exec(whole)) !== null) {
    spans.push({ start: m.index, end: m.index + m[0].length })
  }
  if (spans.length === 0) return 0

  // Split each run into slices aligned to citation-span boundaries.
  const newRuns: Element[] = []
  for (const piece of pieces) {
    const ps = piece.start
    const pe = piece.start + piece.text.length
    const within = spans
      .map(s => ({ start: Math.max(s.start, ps), end: Math.min(s.end, pe) }))
      .filter(s => s.end > s.start)
    const boundarySet = new Set<number>([ps, pe])
    for (const s of within) {
      boundarySet.add(s.start)
      boundarySet.add(s.end)
    }
    const boundaries = Array.from(boundarySet).filter(b => b >= ps && b <= pe).sort((a, b) => a - b)
    for (let i = 0; i < boundaries.length - 1; i++) {
      const b0 = boundaries[i]!
      const b1 = boundaries[i + 1]!
      if (b1 <= b0) continue
      const inSpan = within.some(s => b0 >= s.start && b1 <= s.end)
      const sliceText = piece.text.slice(b0 - ps, b1 - ps)
      if (sliceText.length === 0) continue
      newRuns.push(buildRun(doc, piece.run, sliceText, inSpan))
    }
  }
  if (newRuns.length === 0) return 0
  replaceRuns(p, runs, newRuns)
  return spans.length
}

/** The `w:t` text of a run. */
function wText(r: Element): string {
  return Array.from(r.getElementsByTagNameNS(NS.word, 't')).map(t => t.textContent ?? '').join('')
}

/**
 * Build a rebuilt run: clone the source run (preserving `w:rPr`), replace its
 * text with `text` and, when superscript, force `w:vertAlign val="superscript"`.
 * @param doc - the document container.
 * @param source - the original run to clone.
 * @param text - the text the rebuilt run carries.
 * @param superscript - whether to mark it superscript.
 * @returns the rebuilt run element.
 */
function buildRun(doc: DocxDocument, source: Element, text: string, superscript: boolean): Element {
  const clone = source.cloneNode(true) as Element
  for (const t of Array.from(clone.getElementsByTagNameNS(NS.word, 't'))) t.parentNode?.removeChild(t)
  for (const t of Array.from(clone.getElementsByTagNameNS(NS.math, 't'))) t.parentNode?.removeChild(t)
  if (superscript) {
    let rPr = Array.from(clone.getElementsByTagNameNS(NS.word, 'rPr'))[0]
    if (rPr === undefined) {
      rPr = createEl(doc.document, NS.word, 'w:rPr')
      clone.insertBefore(rPr, clone.firstChild)
    }
    let vert = Array.from(rPr.getElementsByTagNameNS(NS.word, 'vertAlign'))[0]
    if (vert === undefined) {
      vert = createEl(doc.document, NS.word, 'w:vertAlign')
      rPr.appendChild(vert)
    }
    vert.setAttributeNS(NS.word, 'w:val', 'superscript')
  }
  const t = createEl(doc.document, NS.word, 'w:t')
  if (text.length === 0 || /^[\s\u3000]/.test(text) || /[\s\u3000]$/.test(text)) {
    t.setAttributeNS(NS.xml, 'xml:space', 'preserve')
  }
  t.textContent = text
  clone.appendChild(t)
  return clone
}

/** Remove the original runs and insert the rebuilt runs in their place. */
function replaceRuns(p: Element, oldRuns: Element[], newRuns: Element[]): void {
  // The rebuilt runs belong where the first old run sat: just after `w:pPr`
  // when present, else at the start; any sibling following the last run is kept.
  const anchor = oldRuns[oldRuns.length - 1]?.nextSibling ?? null
  for (const r of oldRuns) p.removeChild(r)
  for (const r of newRuns) {
    if (anchor !== null) p.insertBefore(r, anchor)
    else p.appendChild(r)
  }
}
