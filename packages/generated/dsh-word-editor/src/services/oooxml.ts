/**
 * OOXML container service of @deepseek-ai/dsh-word-editor: load a `.docx` ZIP
 * into an in-memory entry map plus a parsed DOM of `word/document.xml`, resolve
 * the logical-style whitelist to the template's concrete styles by name, and
 * serialize the result back to a new `.docx` of the same entry set. This is
 * the only module that touches raw OOXML; callers work through session
 * target ids and logical styles.
 * @module @deepseek-ai/dsh-word-editor/services/oooxml
 */

import { DOMParser } from '@xmldom/xmldom'
import { strFromU8, unzipSync } from 'fflate'
import type { LogicalStyle } from '../types.js'

const WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
const MATH_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
const XML_SPACE = 'http://www.w3.org/XML/1998/namespace'

/** A parsed WordprocessingML document: the DOCX entry set plus the document DOM. */
export interface DocxDocument {
  /** Every DOCX ZIP entry under its full path, decompressed. */
  entries: Map<string, Uint8Array>
  /** Parsed `word/document.xml`. */
  document: Document
  /** Parsed `word/styles.xml`; always present because OOXML obliges one. */
  styles: Document
  /** Resolved logical-style → concrete styleId map (see {@link resolveStyles}). */
  styleMap: Map<LogicalStyle, string>
}

/**
 * Render every `w:t`/`m:t` text node of an element in document order. Used to
 * read a paragraph's or cell's full text including MathML text content.
 * @param node - the element whose descendant text to collect.
 * @returns the concatenated text.
 */
export function elementText(node: Element): string {
  const parts: string[] = []
  for (const child of node.getElementsByTagNameNS ? Array.from(node.getElementsByTagNameNS('*', 't')) : []) {
    parts.push(child.textContent ?? '')
  }
  return parts.join('')
}

/**
 * Text of a run-less paragraph may live directly in `w:t`; this alias keeps
 * callers that only want `w:t` (excluding MathML `m:t`) explicit.
 * @param node - the element whose `w:t` descendants to collect.
 * @returns the concatenated `w:t` text.
 */
export function wText(node: Element): string {
  return Array.from(node.getElementsByTagNameNS(WORD_NS, 't'))
    .map(child => child.textContent ?? '')
    .join('')
}

/** Namespace constants the DOM helpers share. */
export const NS = { word: WORD_NS, math: MATH_NS, xml: XML_SPACE } as const

/**
 * Create an element in a given namespace with the given tag name (the caller
 * passes the `w:`/`m:` prefixed name).
 * @param doc - the owner document.
 * @param ns - namespace URI.
 * @param name - prefixed tag name such as `w:p`.
 * @returns the created element.
 */
export function createEl(doc: Document, ns: string, name: string): Element {
  return doc.createElementNS(ns, name)
}

/**
 * Read a `.docx` file from an in-memory byte buffer into a {@link DocxDocument}.
 * @param bytes - the raw `.docx` bytes.
 * @returns the parsed document container.
 * @throws when the container is missing the required OOXML parts or malformed.
 */
export function loadDocx(bytes: Uint8Array): DocxDocument {
  const entries = new Map<string, Uint8Array>()
  for (const [name, data] of Object.entries(unzipSync(bytes))) {
    entries.set(name, new Uint8Array(data))
  }
  const documentXml = entries.get('word/document.xml')
  const stylesXml = entries.get('word/styles.xml')
  if (documentXml === undefined || stylesXml === undefined) {
    throw new Error('not a valid .docx: missing word/document.xml or word/styles.xml')
  }
  const parser = new DOMParser()
  const document = parser.parseFromString(strFromU8(documentXml), 'application/xml')
  const styles = parser.parseFromString(strFromU8(stylesXml), 'application/xml')
  return {
    entries,
    document,
    styles,
    styleMap: resolveStyles(styles),
  }
}

/**
 * Resolve logical styles to concrete styleIds by scanning `word/styles.xml`
 * and matching each declared style's `w:name` against the whitelist. Style
 * names are looked up dynamically so a template's numeric styleIds never leak
 * into code.
 * @param styles - parsed `word/styles.xml`.
 * @returns the logical → styleId map (only whitelisted styles present).
 */
export function resolveStyles(styles: Document): Map<LogicalStyle, string> {
  const byName = new Map<string, string>()
  const styleEls = Array.from(styles.getElementsByTagNameNS(WORD_NS, 'style'))
  for (const style of styleEls) {
    const id = style.getAttributeNS(WORD_NS, 'styleId')
    const nameEl = Array.from(style.getElementsByTagNameNS(WORD_NS, 'name'))[0]
    const name = nameEl?.getAttributeNS(WORD_NS, 'val')
    if (id !== null && id !== '' && name !== null && name !== undefined) byName.set(name, id)
  }
  const map = new Map<LogicalStyle, string>()
  const logicalNames: Record<Exclude<LogicalStyle, 'keep'>, string> = {
    body: 'Normal (Web)',
    heading_1: 'heading 2',
    heading_2: 'heading 3',
    heading_3: 'heading 4',
    toc_1: 'toc 1',
    toc_2: 'toc 2',
    toc_3: 'toc 3',
    table_content: '表格内容',
    reference: '参考文献',
  }
  for (const [logical, actualName] of Object.entries(logicalNames)) {
    const id = byName.get(actualName)
    if (id !== undefined) map.set(logical as Exclude<LogicalStyle, 'keep'>, id)
  }
  return map
}

/**
 * Get the block-level children of the document body in document order.
 * @param doc - the parsed document.
 * @returns the `w:body` child elements.
 */
export function bodyBlocks(doc: DocxDocument): Element[] {
  const body = Array.from(doc.document.getElementsByTagNameNS(WORD_NS, 'body'))[0]
  if (body === undefined) throw new Error('malformed document: no w:body')
  return Array.from(body.childNodes).filter((n): n is Element => n.nodeType === 1)
}

/**
 * The declared paragraph styleId of a `w:p`, or undefined for a directly
 * formatted paragraph.
 * @param p - the paragraph element.
 * @returns the styleId or undefined.
 */
export function paragraphStyleId(p: Element): string | undefined {
  const pPr = Array.from(p.getElementsByTagNameNS(WORD_NS, 'pPr'))[0]
  if (pPr === undefined) return undefined
  const pStyle = Array.from(pPr.getElementsByTagNameNS(WORD_NS, 'pStyle'))[0]
  const val = pStyle?.getAttributeNS(WORD_NS, 'val')
  return val === null ? undefined : val
}

/**
 * Classify a paragraph element by its logical style: whether it is a heading,
 * TOC, reference, table content, or plain body paragraph (the default for any
 * resolved body style and direct formatting).
 * @param p - the paragraph element.
 * @param styleMap - the resolved logical-style map.
 * @returns the classified logical style (or `'keep'` when unstyled-rich).
 */
export function classifyParagraph(p: Element, styleMap: Map<LogicalStyle, string>): LogicalStyle {
  const id = paragraphStyleId(p)
  for (const [logical, styleId] of styleMap) {
    if (id === styleId) return logical
  }
  return 'keep'
}

/**
 * The first sentence of a paragraph: text up to the first Chinese or English
 * end-of-sentence mark (。！？!?…). Returns the whole text when no such mark
 * exists.
 * @param text - the full paragraph text.
 * @returns the first sentence.
 */
export function firstSentence(text: string): string {
  const idx = text.search(/[。！？!?…]|(?<![A-Za-z])\.(?![A-Za-z])/)
  if (idx === -1) return text
  return text.slice(0, idx + 1)
}
