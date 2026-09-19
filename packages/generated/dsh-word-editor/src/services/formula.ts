/**
 * Formula candidate scanning of @deepseek-ai/dsh-word-editor: detect LaTeX /
 * OLaTeX that is not yet a Word OMath and is safe to hand to a cleanup
 * subagent. Static signals (delimiters, backslash commands, math unicode,
 * split-run markers) plus delimiter balance are checked; protected OMath
 * regions are skipped so repeated scans never re-convert an existing formula.
 * @module @deepseek-ai/dsh-word-editor/services/formula
 */

import type { FormulaCandidate } from '../types.js'
import { elementText, NS } from './oooxml.js'

/** Characters that strongly indicate math content (womb Unicode math glyphs). */
const MATH_UNICODE = /[\u2212\u2211\u220f\u222b\u221a\u2264\u2265\u2248\u2200\u2203\u230a\u230b\u2070-\u209f]/u

/** Backslash command that strongly indicates a LaTeX formula. */
const LATEX_COMMAND = /\\(?:frac|sqrt|sum|int|partial|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|omega|cdot|times|geq|leq|rightarrow|leftrightarrow|underline|overline|begin|end)/

/** A run boundary tag indicating a formula split across Word runs. */
const ZERO_WIDTH = /[\u200b\u200c\u200d\ufeff]/g

/**
 * Guard against an existing OMath by masking its text extent before scanning,
 * so an already-converted formula is never reported as a candidate again.
 */
function maskOMath(elem: Element, text: string): string {
  const oMaths = Array.from(elem.getElementsByTagNameNS(NS.math, 'oMath'))
  if (oMaths.length === 0) return text
  let masked = text
  for (const om of oMaths) {
    const start = elementText(om as unknown as Element)
    const at = masked.indexOf(start)
    if (at !== -1) {
      masked = masked.slice(0, at) + masked.slice(at).replace(start, '\uFFFD'.repeat(Math.max(start.length, 1)))
    }
  }
  return masked
}

/**
 * Scan an element for LaTeX candidates. Returns candidates in text order;
 * does not modify the document.
 * @param target - the paragraph or cell element to scan.
 * @param baseTargetId - the target id for the returned candidates.
 * @returns the detected candidates.
 */
export function scanCandidates(target: Element, baseTargetId: string): FormulaCandidate[] {
  const full = elementText(target)
  const masked = maskOMath(target, full)
  const candidates: FormulaCandidate[] = []
  const start = 0
  const push = (s: number, e: number, display: 'inline' | 'block', reason: string, confidence: number): void => {
    candidates.push({
      candidate_id: `f${start}-${e}`,
      target_id: baseTargetId,
      source_start: s,
      source_end: e,
      source_text: full.slice(s, e),
      display,
      confidence,
      reason,
    })
  }
  // Delimiter-driven scan with balance checking.
  let i = 0
  while (i < masked.length) {
    const ch = masked[i]
    if (ch === undefined) break
    if (masked.startsWith('$$', i)) {
      const end = masked.indexOf('$$', i + 2)
      if (end !== -1) { push(i, end + 2, 'block', 'double-dollar block', 0.9); i = end + 2; continue }
    }
    if (ch === '$') {
      const end = masked.indexOf('$', i + 1)
      if (end !== -1) { push(i, end + 1, 'inline', 'dollar-inline', 0.85); i = end + 1; continue }
    }
    if (masked.startsWith('\\(', i)) {
      const end = masked.indexOf('\\)', i + 2)
      if (end !== -1) { push(i, end + 2, 'inline', 'escaped-paren inline', 0.9); i = end + 2; continue }
    }
    if (masked.startsWith('\\[', i)) {
      const end = masked.indexOf('\\]', i + 2)
      if (end !== -1) { push(i, end + 2, 'block', 'escaped-bracket block', 0.9); i = end + 2; continue }
    }
    if (masked.startsWith('\\begin{', i)) {
      const end = masked.indexOf('\\end{', i + 2)
      if (end !== -1) {
        const close = masked.indexOf('}', end)
        if (close !== -1) { push(i, close + 1, 'block', 'begin/end block', 0.95); i = close + 1; continue }
      }
    }
    i += 1
  }
  // Fallback: un-delimited backslash command or math unicode with a balance
  // of braces that suggests a formula fragment.
  const unicodeMatch = full.search(LATEX_COMMAND)
  if (unicodeMatch !== -1 && candidates.length === 0) {
    push(unicodeMatch, Math.min(full.length, unicodeMatch + 40), 'inline', 'un-delimited latex command', 0.5)
  } else if (candidates.length === 0 && MATH_UNICODE.test(full)) {
    push(0, full.length, 'inline', 'math unicode present', 0.4)
  }
  return candidates
}

/** True when the given text contains a zero-width artifact from a web copy. */
export function hasZeroWidth(text: string): boolean {
  ZERO_WIDTH.lastIndex = 0
  return ZERO_WIDTH.test(text)
}

/** Strip zero-width chars and Markdown math fences from a linear formula. */
export function normalizeLinearMath(raw: string): string {
  return raw.replace(ZERO_WIDTH, '').replace(/`/g, '')
}

/** A balanced LaTeX delimiter report for a candidate's source text. */
export function delimiterBalance(source: string): { balanced: boolean; detail: string } {
  const opens = (source.match(/\(/g) ?? []).length
  const closes = (source.match(/\)/g) ?? []).length
  const braces = (source.match(/\{/g) ?? []).length - (source.match(/\}/g) ?? []).length
  const balanced = opens === closes && braces === 0
  return { balanced, detail: `parens ${opens}vs${closes}; brace delta ${braces}` }
}
