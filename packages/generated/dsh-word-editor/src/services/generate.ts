/**
 * Document generator of @deepseek-ai/dsh-word-editor: builds a fresh `w:body`
 * from parsed Markdown blocks and the template's concrete styles, mutating a
 * loaded template {@link DocxDocument} in place (keeping its styles, headers,
 * footers, and section properties so the output layout matches the template).
 * Cover and TOC are intentionally out of scope — the caller owns those.
 * @module @deepseek-ai/dsh-word-editor/services/generate
 */

import { extname } from 'node:path'
import { XMLSerializer, DOMParser } from '@xmldom/xmldom'
import { strToU8 } from 'fflate'
import type { DocxDocument } from './oooxml.js'
import { createEl, NS } from './oooxml.js'
import type { InlineRun, MdBlock } from './markdown.js'

/** Namespace URIs for the drawing XML an inserted picture uses. */
export const DRAW = {
  a: 'http://schemas.openxmlformats.org/drawingml/2006/main',
  pic: 'http://schemas.openxmlformats.org/drawingml/2006/picture',
  wp: 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
  r: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
  rels: 'http://schemas.openxmlformats.org/package/2006/relationships',
} as const

const XMLNS_NS = 'http://www.w3.org/2000/xmlns/'
const IMAGE_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
const IMAGE_MIME: Record<string, string> = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  bmp: 'image/bmp',
  svg: 'image/svg+xml',
  tiff: 'image/tiff',
}

/** One table row: the cell texts. */
export interface MdTableRow {
  cells: string[]
}

/**
 * A structured overview of a generated document: what the model sees instead
 * of the raw manuscript, so it can confirm the structure without reading every
 * paragraph.
 */
export interface GenerateOutline {
  headings: Array<{ level: number; text: string }>
  paragraph_count: number
  table_count: number
  /** Row count of each generated table, in order. */
  table_rows: number[]
  reference_count: number
  image_count: number
}

/** Settings for one generate pass. */
export interface GenerateOptions {
  /** Resolve an image path to its bytes; return undefined when unreadable. */
  loadImage: (src: string) => Uint8Array | undefined
}

/** Resolve a logical style to the template's concrete styleId. */
function styleId(doc: DocxDocument, logical: 'body' | 'heading_1' | 'heading_2' | 'heading_3' | 'reference'): string {
  const id = doc.styleMap.get(logical)
  if (id === undefined) throw new Error(`the template maps no style for logical style ${logical}`)
  return id
}

/** The template's concrete table styleId for the dedicated proposal table. */
function tableStyleId(doc: DocxDocument): string {
  for (const style of Array.from(doc.styles.getElementsByTagNameNS(NS.word, 'style'))) {
    const nameEl = Array.from(style.getElementsByTagNameNS(NS.word, 'name'))[0]
    const name = nameEl?.getAttributeNS(NS.word, 'val')
    if (name === '开题报告表格') {
      const id = style.getAttributeNS(NS.word, 'styleId')
      if (id !== null && id !== '') return id
    }
  }
  throw new Error('the template defines no 开题报告表格 table style')
}

/**
 * Replace the loaded template document's body with blocks built from the
 * parsed manuscript, using the template's concrete style ids. Mutates `doc`.
 * @param doc - the template's parsed {@link DocxDocument} to reshape.
 * @param blocks - the parsed Markdown blocks.
 * @param options - image loading configuration.
 * @returns the generated structure outline.
 */
export function generateDocument(doc: DocxDocument, blocks: MdBlock[], options: GenerateOptions): GenerateOutline {
  const body = Array.from(doc.document.getElementsByTagNameNS(NS.word, 'body'))[0]
  if (body === undefined) throw new Error('malformed template: no w:body')
  const sectPr = Array.from(body.getElementsByTagNameNS(NS.word, 'sectPr'))[0]
  // Drop the existing body content, keeping the final section properties so
  // the template's page layout (margins, headers, footers, orientation) survives.
  while (body.firstChild) body.removeChild(body.firstChild)
  const outline: GenerateOutline = {
    headings: [],
    paragraph_count: 0,
    table_count: 0,
    table_rows: [],
    reference_count: 0,
    image_count: 0,
  }
  let nextImage = 1
  for (const block of blocks) {
    switch (block.type) {
      case 'heading': {
        const level = `heading_${block.level}` as 'heading_1' | 'heading_2' | 'heading_3'
        body.appendChild(makeStyledParagraph(doc, styleId(doc, level), [textRun(block.text)]))
        outline.headings.push({ level: block.level, text: block.text })
        outline.paragraph_count += 1
        break
      }
      case 'paragraph': {
        body.appendChild(makeStyledParagraph(doc, styleId(doc, 'body'), block.runs))
        outline.paragraph_count += 1
        break
      }
      case 'math': {
        body.appendChild(makeStyledParagraph(doc, styleId(doc, 'body'), [textRun(block.text)]))
        outline.paragraph_count += 1
        break
      }
      case 'list': {
        for (let idx = 0; idx < block.items.length; idx++) {
          const marker: InlineRun = { type: 'text', text: block.ordered ? `${idx + 1}. ` : '· ' }
          body.appendChild(makeStyledParagraph(doc, styleId(doc, 'body'), [marker, ...block.items[idx]!]))
          outline.paragraph_count += 1
        }
        break
      }
      case 'table': {
        body.appendChild(makeTable(doc, block.headers, block.rows))
        outline.table_count += 1
        outline.table_rows.push(block.rows.length)
        break
      }
      case 'reference': {
        body.appendChild(makeStyledParagraph(doc, styleId(doc, 'reference'), [textRun(block.text)]))
        outline.reference_count += 1
        break
      }
      case 'image': {
        const rId = insertImagePart(doc, block.src, options, nextImage)
        if (rId !== undefined) {
          body.appendChild(makeImageParagraph(doc, rId, nextImage, block.alt))
          outline.image_count += 1
        }
        nextImage += 1
        break
      }
    }
  }
  if (sectPr !== undefined) body.appendChild(sectPr)
  ensureDrawingNamespaces(doc)
  return outline
}

/** A plain text inline run helper. */
function textRun(text: string): InlineRun {
  return { type: 'text', text }
}

/**
 * Build a `w:p` from styled inline runs.
 * @param doc - the document container for element creation.
 * @param style - the concrete paragraph style id.
 * @param runs - the inline runs to render.
 * @returns the paragraph element.
 */
export function makeStyledParagraph(doc: DocxDocument, style: string, runs: InlineRun[]): Element {
  const p = createEl(doc.document, NS.word, 'w:p')
  const pPr = createEl(doc.document, NS.word, 'w:pPr')
  const pStyle = createEl(doc.document, NS.word, 'w:pStyle')
  pStyle.setAttributeNS(NS.word, 'w:val', style)
  pPr.appendChild(pStyle)
  p.appendChild(pPr)
  for (const r of runs) p.appendChild(makeRun(doc, r))
  p.appendChild(makeBlankRun(doc))
  return p
}

/** Build a single `w:r` with formatting for one inline run (links render as plain text). */
function makeRun(doc: DocxDocument, run: InlineRun): Element {
  const wRun = createEl(doc.document, NS.word, 'w:r')
  if (run.type === 'bold' || run.type === 'italic' || run.type === 'code' || run.type === 'math') {
    const rPr = createEl(doc.document, NS.word, 'w:rPr')
    if (run.type === 'bold') rPr.appendChild(createEl(doc.document, NS.word, 'w:b'))
    if (run.type === 'italic') rPr.appendChild(createEl(doc.document, NS.word, 'w:i'))
    if (run.type === 'code' || run.type === 'math') {
      const szCs = createEl(doc.document, NS.word, 'w:szCs')
      szCs.setAttributeNS(NS.word, 'w:val', '20')
      rPr.appendChild(szCs)
    }
    wRun.appendChild(rPr)
  }
  const t = createEl(doc.document, NS.word, 'w:t')
  t.setAttributeNS(NS.xml, 'xml:space', 'preserve')
  t.textContent = run.text
  wRun.appendChild(t)
  return wRun
}

/** A blank trailing run, matching the template's paragraph style. */
function makeBlankRun(doc: DocxDocument): Element {
  const run = createEl(doc.document, NS.word, 'w:r')
  run.appendChild(createEl(doc.document, NS.word, 'w:t'))
  return run
}

/**
 * Build a `w:tbl` carrying the template's dedicated table style, with a header
 * row and data rows; every cell holds a `表格内容`-styled paragraph.
 * @param doc - the document container.
 * @param headers - the header row cell texts.
 * @param rows - the data row cell texts.
 * @returns the table element.
 */
export function makeTable(doc: DocxDocument, headers: string[], rows: string[][]): Element {
  const tbl = createEl(doc.document, NS.word, 'w:tbl')
  const tblPr = createEl(doc.document, NS.word, 'w:tblPr')
  const tblStyle = createEl(doc.document, NS.word, 'w:tblStyle')
  tblStyle.setAttributeNS(NS.word, 'w:val', tableStyleId(doc))
  tblPr.appendChild(tblStyle)
  tbl.appendChild(tblPr)
  const colCount = Math.max(1, headers.length, ...rows.map(r => r.length))
  const grid = createEl(doc.document, NS.word, 'w:tblGrid')
  for (let i = 0; i < colCount; i++) {
    const gc = createEl(doc.document, NS.word, 'w:gridCol')
    gc.setAttributeNS(NS.word, 'w:w', String(Math.floor(5000 / colCount)))
    grid.appendChild(gc)
  }
  tbl.appendChild(grid)
  tbl.appendChild(makeTableRow(doc, headers, colCount))
  for (const row of rows) tbl.appendChild(makeTableRow(doc, row, colCount))
  return tbl
}

/** Build one `w:tr` with `colCount` cells, padding empty cells. */
function makeTableRow(doc: DocxDocument, cells: string[], colCount: number): Element {
  const tr = createEl(doc.document, NS.word, 'w:tr')
  const cellStyle = doc.styleMap.get('table_content')
  for (let i = 0; i < colCount; i++) {
    const value = cells[i] ?? ''
    const tc = createEl(doc.document, NS.word, 'w:tc')
    const tcPr = createEl(doc.document, NS.word, 'w:tcPr')
    const tcW = createEl(doc.document, NS.word, 'w:tcW')
    tcW.setAttributeNS(NS.word, 'w:w', String(Math.floor(5000 / colCount)))
    tcW.setAttributeNS(NS.word, 'w:type', 'dxa')
    tcPr.appendChild(tcW)
    tc.appendChild(tcPr)
    tc.appendChild(makeStyledParagraph(doc, cellStyle ?? '', value === '' ? [] : [textRun(value)]))
    tr.appendChild(tc)
  }
  return tr
}

/**
 * Copy an image from the filesystem into the document package: media part,
 * content-type default, and a document relationship. Returns the freed
 * relationship id, or undefined when the image cannot be read.
 * @param doc - the document container.
 * @param src - the image path.
 * @param options - the image loader.
 * @param imageNo - a stable per-content image ordinal.
 */
function insertImagePart(doc: DocxDocument, src: string, options: GenerateOptions, imageNo: number): string | undefined {
  const bytes = options.loadImage(src)
  if (bytes === undefined) return undefined
  const ext = (extname(src) || '.png').replace('.', '').toLowerCase()
  const mediaPath = `word/media/image${imageNo}.${ext}`
  doc.entries.set(mediaPath, bytes)
  addImageContentType(doc, ext)
  // The document rels live in `word/_rels/`, so their targets are relative to
  // `word/` (e.g. `media/image1.png`), never the full `word/media/...` path.
  return addImageRelationship(doc, mediaPath.replace(/^word\//, ''))
}

/** Add an image relationship to `word/_rels/document.xml.rels` and return its id. */
function addImageRelationship(doc: DocxDocument, target: string): string {
  const relsPath = 'word/_rels/document.xml.rels'
  const relsBytes = doc.entries.get(relsPath)
  if (relsBytes !== undefined) {
    const relsDoc = new DOMParser().parseFromString(new TextDecoder().decode(relsBytes), 'application/xml')
    const rels = Array.from(relsDoc.getElementsByTagNameNS(DRAW.rels, 'Relationships'))[0]
    let maxId = 0
    for (const rel of Array.from(relsDoc.getElementsByTagNameNS(DRAW.rels, 'Relationship'))) {
      const n = /^rId(\d+)$/.exec(rel.getAttribute('Id') ?? '')
      if (n !== null) maxId = Math.max(maxId, Number(n[1]))
    }
    const rId = `rId${maxId + 1}`
    const rel = relsDoc.createElementNS(DRAW.rels, 'Relationship')
    rel.setAttribute('Id', rId)
    rel.setAttribute('Type', IMAGE_REL)
    rel.setAttribute('Target', target)
    if (rels !== undefined) rels.appendChild(rel)
    doc.entries.set(relsPath, strToU8(new XMLSerializer().serializeToString(relsDoc)))
    return rId
  }
  const rId = 'rId1'
  const relsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${DRAW.rels}"><Relationship Id="${rId}" Type="${IMAGE_REL}" Target="${target}"/></Relationships>`
  doc.entries.set(relsPath, strToU8(relsXml))
  return rId
}

/** Ensure `[Content_Types].xml` declares the image extension. */
function addImageContentType(doc: DocxDocument, ext: string): void {
  const path = '[Content_Types].xml'
  const CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
  const bytes = doc.entries.get(path)
  if (bytes === undefined) return
  const typesDoc = new DOMParser().parseFromString(new TextDecoder().decode(bytes), 'application/xml')
  const root = Array.from(typesDoc.getElementsByTagNameNS(CT, 'Types'))[0]
  if (root === undefined) return
  if (Array.from(typesDoc.getElementsByTagNameNS(CT, 'Default')).some(d => d.getAttribute('Extension') === ext)) return
  const def = typesDoc.createElementNS(CT, 'Default')
  def.setAttribute('Extension', ext)
  def.setAttribute('ContentType', IMAGE_MIME[ext] ?? 'image/png')
  root.insertBefore(def, root.firstChild)
  doc.entries.set(path, strToU8(new XMLSerializer().serializeToString(typesDoc)))
}

/** Make a centered picture paragraph for the referenced image. */
function makeImageParagraph(doc: DocxDocument, rId: string, id: number, alt: string): Element {
  const p = createEl(doc.document, NS.word, 'w:p')
  const pPr = createEl(doc.document, NS.word, 'w:pPr')
  const jc = createEl(doc.document, NS.word, 'w:jc')
  jc.setAttributeNS(NS.word, 'w:val', 'center')
  pPr.appendChild(jc)
  p.appendChild(pPr)
  const wRun = createEl(doc.document, NS.word, 'w:r')
  const drawing = createEl(doc.document, NS.word, 'w:drawing')
  const inline = createEl(doc.document, DRAW.wp, 'wp:inline')
  inline.setAttribute('distT', '0')
  inline.setAttribute('distB', '0')
  inline.setAttribute('distL', '0')
  inline.setAttribute('distR', '0')
  const extent = createEl(doc.document, DRAW.wp, 'wp:extent')
  extent.setAttribute('cx', '1800000')
  extent.setAttribute('cy', '1200000')
  inline.appendChild(extent)
  const effExt = createEl(doc.document, DRAW.wp, 'wp:effectExtent')
  effExt.setAttribute('l', '0')
  effExt.setAttribute('t', '0')
  effExt.setAttribute('r', '0')
  effExt.setAttribute('b', '0')
  inline.appendChild(effExt)
  const docPr = createEl(doc.document, DRAW.wp, 'wp:docPr')
  docPr.setAttribute('id', String(id))
  docPr.setAttribute('name', alt || `image-${id}`)
  inline.appendChild(docPr)
  const cNv = createEl(doc.document, DRAW.wp, 'wp:cNvGraphicFramePr')
  cNv.appendChild(createEl(doc.document, DRAW.a, 'a:graphicFrameLocks'))
  inline.appendChild(cNv)
  const graphic = createEl(doc.document, DRAW.a, 'a:graphic')
  const graphicData = createEl(doc.document, DRAW.a, 'a:graphicData')
  graphicData.setAttribute('uri', DRAW.pic)
  const pic = createEl(doc.document, DRAW.pic, 'pic:pic')
  const nvPr = createEl(doc.document, DRAW.pic, 'pic:nvPicPr')
  const cNvPr = createEl(doc.document, DRAW.pic, 'pic:cNvPr')
  cNvPr.setAttribute('id', String(id))
  cNvPr.setAttribute('name', alt || `image-${id}`)
  nvPr.appendChild(cNvPr)
  nvPr.appendChild(createEl(doc.document, DRAW.pic, 'pic:cNvPicPr'))
  pic.appendChild(nvPr)
  const blipFill = createEl(doc.document, DRAW.pic, 'pic:blipFill')
  const blip = createEl(doc.document, DRAW.a, 'a:blip')
  blip.setAttributeNS(DRAW.r, 'r:embed', rId)
  blipFill.appendChild(blip)
  const stretch = createEl(doc.document, DRAW.a, 'a:stretch')
  stretch.appendChild(createEl(doc.document, DRAW.a, 'a:fillRect'))
  blipFill.appendChild(stretch)
  pic.appendChild(blipFill)
  const spPr = createEl(doc.document, DRAW.pic, 'pic:spPr')
  const xfrm = createEl(doc.document, DRAW.a, 'a:xfrm')
  xfrm.appendChild(createEl(doc.document, DRAW.a, 'a:off'))
  const xext = createEl(doc.document, DRAW.a, 'a:ext')
  xext.setAttribute('cx', '1800000')
  xext.setAttribute('cy', '1200000')
  xfrm.appendChild(xext)
  spPr.appendChild(xfrm)
  const geom = createEl(doc.document, DRAW.a, 'a:prstGeom')
  geom.setAttribute('prst', 'rect')
  spPr.appendChild(geom)
  pic.appendChild(spPr)
  graphicData.appendChild(pic)
  graphic.appendChild(graphicData)
  inline.appendChild(graphic)
  drawing.appendChild(inline)
  wRun.appendChild(drawing)
  p.appendChild(wRun)
  return p
}

/** Declare the drawing namespaces (`a`, `pic`) on the root `w:document` when absent. */
function ensureDrawingNamespaces(doc: DocxDocument): void {
  const root = doc.document.documentElement
  if (root === null) return
  for (const [prefix, uri] of [['a', DRAW.a], ['pic', DRAW.pic]] as const) {
    if (!root.hasAttributeNS(XMLNS_NS, prefix)) {
      root.setAttributeNS(XMLNS_NS, `xmlns:${prefix}`, uri)
    }
  }
}
