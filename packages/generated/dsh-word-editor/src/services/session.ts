/**
 * DOCX editing session of @deepseek-ai/dsh-word-editor. A session owns one
 * open working copy, assigns stable in-session target ids to every addressable
 * block element (paragraphs, tables, rows, cells, table-cell paragraphs,
 * sdt, section properties), and implements the model's editing verbs
 * (`read`, `find`, `str_replace`, `add_to`, `delete`) as pure OOXML
 * transformations with audit records. Never writes to the source; a later
 * save step persists an atomic new file.
 * @module @deepseek-ai/dsh-word-editor/services/session
 */

import { createEl, elementText, firstSentence, NS, paragraphStyleId, classifyParagraph, type DocxDocument } from './oooxml.js'
import type { EditAudit, ElementKind, FindParagraph, LogicalStyle, ReadElement, ReadResult } from '../types.js'

/** The id of the whole-document anchor used by `add_to`. */
export const DOCUMENT_ID = 'document'

/** Hard cap on the number of block elements a single {@link DocxSession.read} returns. */
export const READ_ELEMENT_CAP = 300

/** The position an `add_to` uses for a new content unit. */
export type AddPosition = 'before' | 'after' | 'start' | 'end'

/**
 * A parsed-and-indexed working DOCX copy. All mutations happen in memory and
 * register an audit record; saving persists an atomic new file.
 */
export class DocxSession {
  private readonly elementToId = new Map<Element, string>()
  private readonly idToElement = new Map<string, Element>()
  /** Permanent element→id assignment; deleted elements stay here but leave the live maps. */
  private readonly stableId = new WeakMap<Element, string>()
  private readonly audits: EditAudit[] = []
  private paraIndex = 0
  private tableIndex = 0
  private sectIndex = 0
  private genericIndex = 0
  private source: string | undefined

  /**
   * @param doc - the loaded working-copy document.
   * @param allowlist - logical style names the model may request explicitly.
   */
  constructor(
    readonly doc: DocxDocument,
    private readonly allowlist: string[],
  ) {
    this.refresh()
  }

  /** The logical style names allowed as an explicit tool style. */
  get allowedStyles(): readonly string[] {
    return this.allowlist
  }

  /** The full audit trail of every write on this session. */
  get changeAudits(): readonly EditAudit[] {
    return this.audits
  }

  /** Log an audit record and return it to the caller. */
  private audited(record: EditAudit): EditAudit {
    this.audits.push(record)
    return record
  }

  /** The source path this working copy was opened from, if set. */
  get sourcePath(): string | undefined {
    return this.source
  }

  /** Record the source path this working copy was opened from. */
  setSource(path: string): this {
    this.source = path
    return this
  }

  private recorded(elem: Element, id: string): void {
    this.elementToId.set(elem, id)
    this.idToElement.set(id, elem)
    this.stableId.set(elem, id)
  }

  /** Whether an element is still connected to the live document tree. */
  private connected(elem: Element): boolean {
    let node: Node | null = elem
    while (node !== null) {
      if (node === this.doc.document) return true
      node = node.parentNode
    }
    return false
  }

  private bodyChildren(): Element[] {
    return this.documentBody()
  }

  /** The top-level block elements of the document body, in order. */
  blocks(): Element[] {
    return this.documentBody()
  }

  private documentBody(): Element[] {
    const body = this.doc.document.getElementsByTagNameNS(NS.word, 'body')[0]
    if (body === undefined) throw new Error('malformed document: no w:body')
    return Array.from(body.childNodes).filter((n): n is Element => n.nodeType === 1)
  }

  /** The session target id of an element, if indexed.
   * @param elem - the element.
   * @returns its id or undefined.
   */
  idOf(elem: Element): string | undefined {
    return this.elementToId.get(elem)
  }

  /**
   * Re-index the document. Known elements keep their ids (moved content is not
   * renumbered); never-seen elements get fresh ids; deleted elements leave the
   * index. Call after every mutation.
   */
  refresh(): void {
    this.elementToId.clear()
    this.idToElement.clear()
    for (const block of this.bodyChildren()) this.indexBlock(block)
  }

  private indexBlock(block: Element): void {
    const tag = block.localName
    if (tag === 'p') {
      this.recorded(block, this.stableId.get(block) ?? `p${++this.paraIndex}`)
    } else if (tag === 'tbl') {
      const tableNo = this.stableId.get(block)?.match(/^t(\d+)$/)?.[1] !== undefined
        ? Number(this.stableId.get(block)?.match(/^t(\d+)$/)?.[1])
        : ++this.tableIndex
      this.recorded(block, `t${tableNo}`)
      for (let ri = 0; ri < block.getElementsByTagNameNS(NS.word, 'tr').length; ri++) {
        const row = block.getElementsByTagNameNS(NS.word, 'tr').item(ri)
        if (row === null) continue
        this.recorded(row, `t${tableNo}-r${ri + 1}`)
        const cells = Array.from(row.getElementsByTagNameNS(NS.word, 'tc'))
        cells.forEach((cell, ci) => {
          const cid = `t${tableNo}-r${ri + 1}-c${ci + 1}`
          this.recorded(cell, cid)
          const cellParas = Array.from(cell.childNodes).filter((n): n is Element => n.nodeType === 1 && (n as Element).localName === 'p')
          cellParas.forEach((cp, pi) => {
            this.recorded(cp as Element, `${cid}-p${pi + 1}`)
          })
        })
      }
    } else if (tag === 'sdt') {
      this.recorded(block, this.stableId.get(block) ?? `sdt${++this.genericIndex}`)
      const paras = Array.from(block.getElementsByTagNameNS(NS.word, 'p'))
      paras.forEach((p) => {
        this.recorded(p as Element, this.stableId.get(p as Element) ?? `p${++this.paraIndex}`)
      })
    } else if (tag === 'sectPr') {
      this.recorded(block, this.stableId.get(block) ?? `sect${++this.sectIndex}`)
    } else {
      this.recorded(block, this.stableId.get(block) ?? `${tag}${++this.genericIndex}`)
    }
  }

  /** Resolve a target id to its DOM element.
   * @param targetId - the session target id.
   * @returns the element.
   * @throws a loud error for an unknown id.
   */
  resolve(targetId: string): Element {
    const elem = this.idToElement.get(targetId)
    if (elem === undefined || !this.connected(elem)) {
      throw new Error(`unknown target_id ${JSON.stringify(targetId)}; run read() to refresh the document view`)
    }
    return elem
  }

  /** The logical style of a paragraph element.
   * @param p - the paragraph element.
   * @returns its logical style.
   */
  logicalOf(p: Element): LogicalStyle {
    return classifyParagraph(p, this.doc.styleMap)
  }

  /** The full text of a paragraph/cell element (including MathML text).
   * @param elem - the element.
   * @returns the concatenated text.
   */
  textOf(elem: Element): string {
    return elementText(elem)
  }

  private flagsOf(elem: Element): string[] {
    const present: string[] = []
    if (elem.getElementsByTagNameNS(NS.math, 'oMath').length > 0) present.push('m:oMath')
    if (elem.getElementsByTagNameNS(NS.word, 'drawing').length > 0 || elem.getElementsByTagNameNS(NS.word, 'pict').length > 0) present.push('drawing')
    if (elem.getElementsByTagNameNS(NS.word, 'hyperlink').length > 0) present.push('hyperlink')
    if (elem.getElementsByTagNameNS(NS.word, 'fldSimple').length > 0 || elem.getElementsByTagNameNS(NS.word, 'fldChar').length > 0) present.push('field')
    return present
  }

  private kindOfP(p: Element): ReadElement['kind'] {
    const style = this.logicalOf(p)
    if (style === 'heading_1' || style === 'heading_2' || style === 'heading_3') return 'heading'
    if (style === 'toc_1' || style === 'toc_2' || style === 'toc_3') return 'toc'
    if (style === 'reference') return 'reference'
    if (style === 'table_content') return 'table_content'
    if (style === 'body') return 'body'
    return 'other'
  }

  /**
   * Build the full {@link read} overview of the working copy.
   * @param documentPath - the source path to report.
   * @returns the read result (path, elements, truncation marker).
   */
  read(documentPath: string | undefined): ReadResult {
    this.refresh()
    const elements: ReadElement[] = []
    let truncated = false
    for (const block of this.bodyChildren()) {
      if (elements.length >= READ_ELEMENT_CAP) truncated = true
      const el = this.readElement(block)
      if (el !== undefined) elements.push(el)
    }
    return { document_path: documentPath ?? '', truncated, elements }
  }

  private readElement(elem: Element): ReadElement | undefined {
    const id = this.elementToId.get(elem)
    if (id === undefined) return undefined
    const tag = elem.localName
    const kind: ReadElement['kind'] =
      tag === 'p' ? this.kindOfP(elem)
        : tag === 'tbl' ? 'table'
          : tag === 'sectPr' ? 'section_properties'
            : tag === 'sdt' ? 'sdt'
              : 'other'
    const base: ReadElement = {
      target_id: id,
      ooxml_type: `w:${tag}`,
      kind,
      style: tag === 'p' ? this.logicalOf(elem) : this.styleName(elem),
      contains: this.flagsOf(elem),
    }
    const parentEl = elem.parentNode
    if (parentEl !== null && parentEl.nodeType === 1) {
      const pid = this.elementToId.get(parentEl as Element)
      if (pid !== undefined) base.parent_id = pid
    }
    if (tag === 'p') {
      const text = this.textOf(elem)
      if (this.kindOfP(elem) === 'body') {
        const preview = firstSentence(text)
        base.content_preview = preview
        if (preview.length < text.length) base.content_truncated = true
      } else {
        base.content = text
      }
    } else if (tag === 'tbl') {
      const rows = Array.from(elem.getElementsByTagNameNS(NS.word, 'tr'))
      base.content = `table (${rows.length} rows)`
      const children: ReadElement[] = []
      for (const row of rows) {
        for (const cell of Array.from(row.getElementsByTagNameNS(NS.word, 'tc'))) {
          for (const cp of Array.from(cell.childNodes).filter((n): n is Element => n.nodeType === 1 && (n as Element).localName === 'p')) {
            const cid = this.elementToId.get(cp)
            if (cid !== undefined) {
              children.push({
                target_id: cid,
                ooxml_type: 'w:p',
                kind: 'table_content',
                style: this.logicalOf(cp as Element),
                content: this.textOf(cp as Element),
                contains: this.flagsOf(cp as Element),
              })
            }
          }
        }
      }
      if (children.length > 0) base.children = children
    } else if (tag === 'sectPr') {
      base.content = '页面与分节属性'
    } else {
      base.content = this.textOf(elem)
    }
    return base
  }

  private styleName(elem: Element): string {
    if (elem.localName === 'tbl') {
      const tblPr = Array.from(elem.getElementsByTagNameNS(NS.word, 'tblPr'))[0]
      const ts = tblPr === undefined ? undefined : Array.from(tblPr.getElementsByTagNameNS(NS.word, 'tblStyle'))[0]
      const val = ts?.getAttributeNS(NS.word, 'val')
      if (val !== null && val !== undefined) {
        for (const [logical, id] of this.doc.styleMap) if (id === val) return logical
        return this.styleNameById(val) ?? val
      }
    }
    return 'keep'
  }

  /** The display name of a styleId from the styles part, if declared. */
  private styleNameById(styleId: string): string | undefined {
    const styles = Array.from(this.doc.styles.getElementsByTagNameNS(NS.word, 'style'))
    for (const style of styles) {
      const id = style.getAttributeNS(NS.word, 'styleId')
      if (id !== styleId) continue
      const nameEl = Array.from(style.getElementsByTagNameNS(NS.word, 'name'))[0]
      const name = nameEl?.getAttributeNS(NS.word, 'val')
      if (name !== null && name !== undefined) return name
    }
    return undefined
  }

  /** Collect every indexed paragraph element in document order. */
  private allParagraphs(): Element[] {
    return this.bodyChildren().flatMap((b) => {
      if (b.localName === 'p') return [b]
      if (b.localName === 'tbl' || b.localName === 'sdt') {
        return Array.from(b.getElementsByTagNameNS(NS.word, 'p')) as Element[]
      }
      return []
    })
  }

  /**
   * Find paragraphs by id and/or substring content. See the tool contract for
   * the exact argument semantics.
   * @param id - optional paragraph target id to read exactly.
   * @param content - optional substring to search across paragraphs.
   * @returns matching paragraph records.
   */
  find(id: string | undefined, content: string | undefined): FindParagraph[] {
    this.refresh()
    if ((id === undefined || id === '') && (content === undefined || content === '')) {
      throw new Error('find requires at least one of id or content')
    }
    if (id !== undefined && id !== '') {
      const elem = this.resolve(id)
      if (elem.localName !== 'p') {
        throw new Error(`target_id ${JSON.stringify(id)} is a w:${elem.localName}, not a paragraph; use read() for non-paragraph content`)
      }
      const text = this.textOf(elem)
      if (content !== undefined && content !== '' && !text.includes(content)) {
        return []
      }
      return [this.paragraphView(elem)]
    }
    const needle = content ?? ''
    return this.allParagraphs()
      .filter(p => this.elementToId.has(p) && this.textOf(p).includes(needle))
      .map(p => this.paragraphView(p))
  }

  private paragraphView(p: Element): FindParagraph {
    const id = this.elementToId.get(p) ?? ''
    const content = this.textOf(p)
    const flags = this.flagsOf(p).filter(f => f !== 'm:oMath')
    const found: FindParagraph = {
      target_id: id,
      content,
      style: this.logicalOf(p),
    }
    const parent = p.parentNode
    if (parent !== null && parent.nodeType === 1) {
      const parentElem = parent as Element
      const pid = this.elementToId.get(parentElem)
      if (pid !== undefined) found.parent_id = pid
      found.parent_kind = this.kindOf(parentElem)
    }
    if (flags.length > 0) found.children = [{ target_id: id, type: flags.join(','), position: 0 }]
    const prev = this.prevParagraph(p)
    const next = this.nextParagraph(p)
    if (prev !== undefined) found.prev = { target_id: prev.id, content_preview: firstSentence(prev.text) }
    if (next !== undefined) found.next = { target_id: next.id, content_preview: firstSentence(next.text) }
    return found
  }

  private kindOf(elem: Element): ElementKind {
    const tag = elem.localName
    if (tag === 'tbl' || tag === 'tr' || tag === 'tc') return 'table'
    if (tag === 'sdt') return 'sdt'
    if (tag === 'p') return this.kindOfP(elem)
    return 'other'
  }

  private prevParagraph(p: Element): { id: string; text: string } | undefined {
    const paras = this.allParagraphs()
    const idx = paras.indexOf(p)
    if (idx <= 0) return undefined
    const prev = paras[idx - 1]
    if (prev === undefined) return undefined
    const id = this.elementToId.get(prev)
    if (id === undefined) return undefined
    return { id, text: this.textOf(prev) }
  }

  private nextParagraph(p: Element): { id: string; text: string } | undefined {
    const paras = this.allParagraphs()
    const idx = paras.indexOf(p)
    const next = paras[idx + 1]
    if (next === undefined) return undefined
    const id = this.elementToId.get(next)
    if (id === undefined) return undefined
    return { id, text: this.textOf(next) }
  }

  /** True when the element or a descendant carries a structural token that a
   * plain text edit must not cross.
   * @param elem - the element to inspect.
   */
  private hasStructuralConflict(elem: Element): boolean {
    return (
      elem.getElementsByTagNameNS(NS.math, 'oMath').length > 0 ||
      elem.getElementsByTagNameNS(NS.math, 'oMathPara').length > 0 ||
      elem.getElementsByTagNameNS(NS.word, 'drawing').length > 0 ||
      elem.getElementsByTagNameNS(NS.word, 'pict').length > 0 ||
      elem.getElementsByTagNameNS(NS.word, 'fldChar').length > 0 ||
      elem.getElementsByTagNameNS(NS.word, 'instrText').length > 0
    )
  }

  /** Resolve a logical style to a concrete styleId.
   * @param logical - the requested style (`keep` preserves the given element's style).
   * @param current - the element whose style `keep` preserves.
   * @returns the concrete styleId.
   */
  private resolveStyleId(logical: LogicalStyle, current: Element): string {
    if (logical === 'keep') {
      return paragraphStyleId(current) ?? this.doc.styleMap.get('body') ?? ''
    }
    if (!this.allowlist.includes(logical)) {
      throw new Error(`style ${JSON.stringify(logical)} is not allowed here; allowed: ${this.allowlist.join(', ')}`)
    }
    const id = this.doc.styleMap.get(logical)
    if (id === undefined) {
      throw new Error(`the template maps no style for logical style ${JSON.stringify(logical)}`)
    }
    return id
  }

  private setParagraphStyle(p: Element, styleId: string): void {
    let pPr = Array.from(p.getElementsByTagNameNS(NS.word, 'pPr'))[0]
    if (pPr === undefined) {
      pPr = createEl(this.doc.document, NS.word, 'w:pPr')
      p.insertBefore(pPr, p.firstChild)
    }
    let pStyle = Array.from(pPr.getElementsByTagNameNS(NS.word, 'pStyle'))[0]
    if (pStyle === undefined) {
      pStyle = createEl(this.doc.document, NS.word, 'w:pStyle')
      pPr.insertBefore(pStyle, pPr.firstChild)
    }
    pStyle.setAttributeNS(NS.word, 'w:val', styleId)
  }

  private makeRun(text: string): Element {
    const run = createEl(this.doc.document, NS.word, 'w:r')
    const t = createEl(this.doc.document, NS.word, 'w:t')
    if (text.length === 0 || /^[\s\u3000]/.test(text) || /[\s\u3000]$/.test(text)) {
      t.setAttributeNS(NS.xml, 'xml:space', 'preserve')
    }
    t.textContent = text
    run.appendChild(t)
    return run
  }

  private makeParagraph(styleId: string, text = ''): Element {
    const p = createEl(this.doc.document, NS.word, 'w:p')
    const pPr = createEl(this.doc.document, NS.word, 'w:pPr')
    const pStyle = createEl(this.doc.document, NS.word, 'w:pStyle')
    pStyle.setAttributeNS(NS.word, 'w:val', styleId)
    pPr.appendChild(pStyle)
    p.appendChild(pPr)
    p.appendChild(this.makeRun(text))
    return p
  }

  private containsTextStructural(p: Element): boolean {
    return this.hasStructuralConflict(p)
  }

  /**
   * Replace part or all of a paragraph's text. `old_content` must appear
   * exactly in the target; plain replacement is refused when the target spans
   * a formula/drawing/field. Multi-line `content` splits into sibling
   * paragraphs (never embeds a newline inside one paragraph).
   * @param targetId - the paragraph target id.
   * @param oldContent - exact existing text to replace.
   * @param content - the replacement text.
   * @param style - requested style (`keep` preserves the original).
   * @returns the audit record.
   */
  strReplace(targetId: string, oldContent: string, content: string, style: LogicalStyle = 'keep'): EditAudit {
    this.refresh()
    const elem = this.resolve(targetId)
    if (elem.localName !== 'p') {
      throw new Error(`str_replace targets a paragraph; ${JSON.stringify(targetId)} is a w:${elem.localName}`)
    }
    if (oldContent.length === 0) throw new Error('str_replace requires a non-empty old_content')
    if (this.containsTextStructural(elem)) {
      throw new Error(`target ${JSON.stringify(targetId)} contains a formula/drawing/field; plain text replacement refused — use the formula tools`)
    }
    const before = this.textOf(elem)
    if (!before.includes(oldContent)) {
      throw new Error(`old_content not found exactly in target ${JSON.stringify(targetId)}`)
    }
    const at = before.indexOf(oldContent)
    const newText = before.slice(0, at) + content + before.slice(at + oldContent.length)
    const lines = content.split('\n')
    if (lines.length > 1) {
      // replace the whole paragraph with N paragraphs; the template node becomes the first
      this.expandParagraph(elem, newText.split('\n'), style)
      this.refresh()
      return this.audited({
        location: targetId,
        before,
        after: newText,
        before_style: this.logicalOf(elem),
        after_style: style === 'keep' ? this.logicalOf(elem) : style,
        affects_table: false,
        affects_formula: false,
      })
    }
    this.writeParagraphText(elem, newText, style)
    return this.audited({
      location: targetId,
      before,
      after: newText,
      before_style: this.logicalOf(elem),
      after_style: style === 'keep' ? 'keep' : style,
      affects_table: false,
      affects_formula: false,
    })
  }

  /** Rewrite a paragraph's text in place, keeping its `w:pPr` and a blank hot
   * run, applying the requested style.
   * @param p - the paragraph.
   * @param text - the new single-line text.
   * @param style - requested style.
   */
  private writeParagraphText(p: Element, text: string, style: LogicalStyle): void {
    while (p.firstChild) p.removeChild(p.firstChild)
    const styleId = this.resolveStyleId(style, p)
    this.setParagraphStyle(p, styleId)
    p.appendChild(this.makeRun(text))
    p.appendChild(this.makeRun(''))
  }

  /** Replace one paragraph with N sibling paragraphs split on newlines.
   * @param p - the original paragraph (becomes the first of the new set).
   * @param lines - the split replacement lines.
   * @param style - requested style.
   */
  private expandParagraph(p: Element, lines: string[], style: LogicalStyle): void {
    const styleId = this.resolveStyleId(style, p)
    while (p.firstChild) p.removeChild(p.firstChild)
    this.setParagraphStyle(p, styleId)
    p.appendChild(this.makeRun(lines[0] ?? ''))
    p.appendChild(this.makeRun(''))
    let anchor: ChildNode | null = p
    for (let i = 1; i < lines.length; i++) {
      const np = this.makeParagraph(styleId, lines[i] ?? '')
      const parent = p.parentNode
      if (parent !== null) {
        parent.insertBefore(np, anchor.nextSibling)
        anchor = np
      }
    }
  }

  /**
   * Add content at a paragraph, cell, table row, or the whole document.
   * See the tool contract for the full position/new-paragraph semantics.
   * @param targetId - document/paragraph/cell/table-row target.
   * @param content - text or (for a table row) per-cell texts.
   * @param style - requested style.
   * @param position - where to add.
   * @param isNewPara - create a new paragraph instead of appending text inline.
   * @returns the audit record.
   */
  addTo(
    targetId: string,
    content: string | string[],
    style: LogicalStyle,
    position: AddPosition,
    isNewPara: boolean,
  ): EditAudit {
    this.refresh()
    if (targetId === DOCUMENT_ID) {
      return this.addToDocument(content, style, position)
    }
    const elem = this.resolve(targetId)
    const tag = elem.localName
    if (tag === 'tr') {
      return this.addTableRow(elem, content, position)
    }
    if (tag !== 'p' && tag !== 'tc') {
      throw new Error(`add_to supports document/paragraph/cell/table-row targets; ${JSON.stringify(targetId)} is a w:${tag}`)
    }
    const before = this.textOf(elem)
    const text = typeof content === 'string' ? content : content.join('\n')
    const styleId = this.resolveStyleId(style, elem)
    if (isNewPara) {
      const newPara = this.makeParagraph(styleId, text)
      const parent = elem.parentNode
      if (parent === null) throw new Error(`add_to: target ${JSON.stringify(targetId)} has no parent`)
      const insertBeforeNode = position === 'before' ? elem : elem.nextSibling
      parent.insertBefore(newPara, insertBeforeNode)
    } else {
      const addToParagraph = tag === 'p' ? elem : Array.from(elem.getElementsByTagNameNS(NS.word, 'p'))[0]
      if (addToParagraph === undefined) throw new Error(`add_to: cell ${JSON.stringify(targetId)} has no paragraph to append to`)
      this.writeParagraphText(addToParagraph, this.textOf(addToParagraph) + text, style === 'keep' ? 'keep' : style)
    }
    this.refresh()
    return this.audited({
      location: targetId,
      before,
      after: this.textOf(elem),
      before_style: this.logicalOf(elem),
      after_style: style === 'keep' ? this.logicalOf(elem) : style,
      affects_table: tag === 'tc' || this.kindOf(elem) === 'table',
      affects_formula: this.containsTextStructural(elem),
    })
  }

  /** Add a block at the very start or end of the document body.
   * @param content - the text (splits on newlines).
   * @param style - requested style.
   * @param position - `start` or `end`.
   */
  private addToDocument(content: string | string[], style: LogicalStyle, position: AddPosition): EditAudit {
    if (position !== 'start' && position !== 'end') {
      throw new Error('add_to(document, ...) requires position "start" or "end"')
    }
    const body = this.doc.document.getElementsByTagNameNS(NS.word, 'body')[0]
    if (body === undefined) throw new Error('malformed document: no w:body')
    const lines = (typeof content === 'string' ? content : content.join('\n')).split('\n')
    if (position === 'start') {
      let ref: ChildNode | null = body.firstChild
      for (const line of lines) {
        const p = this.makeParagraph(this.resolveStyleId(style, body), line)
        body.insertBefore(p, ref)
        ref = p
      }
    } else {
      const lastChild = body.lastChild
      for (const line of lines) {
        const p = this.makeParagraph(this.resolveStyleId(style, body), line)
        if (lastChild !== null) body.insertBefore(p, lastChild.nextSibling)
        else body.appendChild(p)
      }
    }
    this.refresh()
    return this.audited({
      location: DOCUMENT_ID,
      before: '',
      after: `${lines.length} paragraph(s) added at ${position}`,
      before_style: 'keep',
      after_style: style,
      affects_table: false,
      affects_formula: false,
    })
  }

  /** Clone a table row and insert the per-cell texts before or after it.
   * @param row - the `w:tr` to clone from.
   * @param content - per-cell texts (count must equal the column count).
   * @param position - `before` or `after`.
   */
  private addTableRow(row: Element, content: string | string[], position: AddPosition): EditAudit {
    if (position !== 'before' && position !== 'after') {
      throw new Error('add_to(table row, ...) requires position "before" or "after"')
    }
    const cells = Array.from(row.getElementsByTagNameNS(NS.word, 'tc'))
    const texts = typeof content === 'string' ? [content] : content
    if (texts.length !== cells.length) {
      throw new Error(`table row has ${cells.length} columns but ${texts.length} cell values were given`)
    }
    const clone = row.cloneNode(true) as Element
    const cloneCells = Array.from(clone.getElementsByTagNameNS(NS.word, 'tc'))
    cloneCells.forEach((cell, i) => {
      const paras = Array.from(cell.childNodes).filter((n): n is Element => n.nodeType === 1 && (n as Element).localName === 'p')
      const firstPara = paras[0]
      const value = texts[i] ?? ''
      if (firstPara !== undefined) {
        while (firstPara.firstChild) firstPara.removeChild(firstPara.firstChild)
        firstPara.appendChild(this.makeRun(value))
        firstPara.appendChild(this.makeRun(''))
        for (let k = 1; k < paras.length; k++) cell.removeChild(paras[k]!)
      } else {
        const p = this.makeParagraph(this.doc.styleMap.get('table_content') ?? '', value)
        cell.appendChild(p)
      }
    })
    const parent = row.parentNode
    if (parent === null) throw new Error('add_to: table row has no parent')
    parent.insertBefore(clone, position === 'before' ? row : row.nextSibling)
    this.refresh()
    const tableId = this.elementToId.get(parent as Element) ?? 'tbl'
    return this.audited({
      location: tableId,
      before: '',
      after: `cloned row with ${cells.length} cells (${texts.join(' | ')})`,
      before_style: 'table_content',
      after_style: 'table_content',
      affects_table: true,
      affects_formula: false,
    })
  }

  /**
   * Delete exact text from a target, or a whole paragraph/table-row/table.
   * @param targetId - the target id.
   * @param content - optional exact text to delete; when absent the whole target is removed.
   * @param style - optional assertion on the target's style; a mismatch refuses deletion.
   * @returns the audit record.
   */
  delete(targetId: string, content?: string, style?: LogicalStyle): EditAudit {
    this.refresh()
    const elem = this.resolve(targetId)
    if (style !== undefined && style !== 'keep' && this.logicalOf(elem) !== style) {
      throw new Error(`delete refused: target ${JSON.stringify(targetId)} has style ${this.logicalOf(elem)}, not ${style}`)
    }
    const before = this.textOf(elem)
    if (content !== undefined && content !== '') {
      if (!before.includes(content)) {
        throw new Error(`delete: text not found exactly in target ${JSON.stringify(targetId)}`)
      }
      if (this.hasStructuralConflict(elem)) {
        throw new Error('delete: target contains a formula/drawing/field; refuse plain text deletion')
      }
      const at = before.indexOf(content)
      const newText = before.slice(0, at) + before.slice(at + content.length)
      this.writeParagraphText(elem, newText, 'keep')
      return this.audited({
        location: targetId,
        before,
        after: newText,
        before_style: this.logicalOf(elem),
        after_style: this.logicalOf(elem),
        affects_table: false,
        affects_formula: false,
      })
    }
    const parent = elem.parentNode
    if (parent === null) throw new Error(`delete: target ${JSON.stringify(targetId)} has no parent`)
    parent.removeChild(elem)
    this.refresh()
    return this.audited({
      location: targetId,
      before,
      after: '(deleted)',
      before_style: this.logicalOf(elem),
      after_style: 'keep',
      affects_table: elem.localName === 'tr' || elem.localName === 'tbl' || elem.localName === 'tc',
      affects_formula: this.containsTextStructural(elem),
    })
  }
}
