/**
 * Test fixture generator for @deepseek-ai/dsh-word-editor: builds a minimal but
 * valid .docx (WordprocessingML) whose styles mirror the adapted proposal
 * template — body (Normal (Web)), heading levels, toc, 表格内容, 参考文献,
 * and the dedicated 开题报告表格 table style — plus a body paragraph, a
 * heading, and a table with two rows, and writes it to a temp file.
 * @module dsh-word-editor/tests/fixture
 */

import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { strToU8, zipSync } from 'fflate'

const W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

function el(qname, attrs = {}, inner = '') {
  const attr = Object.entries(attrs).map(([k, v]) => ` ${k}="${v}"`).join('')
  return `<${qname}${attr}>${inner}</${qname}>`
}

/** One paragraph: a style + runs of text. */
function para(style, text) {
  const pPr = style ? el('w:pPr', {}, el('w:pStyle', { 'w:val': style })) : ''
  const runs = Array.from(text).map((ch) => el('w:r', {}, el('w:t', { 'xml:space': 'preserve' }, ch))).join('')
  return el('w:p', {}, `${pPr}${runs}`)
}

/** A paragraph with a native OMath (a simple x+y fraction). */
function paraWithMath(style, before) {
  const pPr = style ? el('w:pPr', {}, el('w:pStyle', { 'w:val': style })) : ''
  const mathText = el('m:t', { 'xml:space': 'preserve' }, 'a+b')
  const mr = el('m:r', {}, mathText)
  const oMath = `<m:oMath>${mr}</m:oMath>`
  return `<w:p><w:pPr><w:pStyle w:val="${style}"/></w:pPr>${el('w:r', {}, el('w:t', {}, before))}${oMath}</w:p>`
}

function tableCell(text, numCols = 2) {
  const tcPr = el('w:tcPr', {}, el('w:tcW', { 'w:w': String(5000 / numCols), 'w:type': 'dxa' }))
  return el('w:tc', {}, `${tcPr}${para('26', text)}`)
}

function tableRow(cells) {
  const trPr = el('w:trPr', {}, el('w:trHeight', { 'w:val': '500', 'w:hRule': 'atLeast' }))
  return el('w:tr', {}, `${trPr}${cells}`)
}

const STYLES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="${W}">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/><w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="15"><w:name w:val="Normal (Web)"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="3"><w:name w:val="heading 2"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="4"><w:name w:val="heading 3"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="5"><w:name w:val="heading 4"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="13"><w:name w:val="toc 1"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="14"><w:name w:val="toc 2"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="7"><w:name w:val="toc 3"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="26"><w:name w:val="表格内容"/><w:qFormat/></w:style>
  <w:style w:type="paragraph" w:styleId="27"><w:name w:val="参考文献"/><w:qFormat/></w:style>
  <w:style w:type="table" w:styleId="ProposalTable"><w:name w:val="开题报告表格"/><w:qFormat/></w:style>
</w:styles>`

const BODY =
  para('3', '1 课题来源及研究目的和意义') +
  para('15', '本研究面向复杂软件调试任务，重点关注多智能体协同方法的设计与验证。首先需要明确调试空间和候选根因表示。') +
  paraWithMath('15', '给定候选根因集合') +
  para('4', '1.1 课题的来源') +
  para('15', '本课题来源于大语言模型驱动的软件工程智能化研究需求。') +
  `<w:tbl><w:tblPr>${el('w:tblStyle', { 'w:val': 'ProposalTable' })}</w:tblPr><w:tblGrid>${el('w:gridCol', { 'w:w': '5000' })}${el('w:gridCol', { 'w:w': '5000' })}</w:tblGrid>${tableRow(tableCell('时间阶段') + tableCell('主要工作'))}${tableRow(tableCell('第一阶段') + tableCell('方案设计与文献调研'))}</w:tbl>` +
  para('13', '目  录')

const DOCUMENT = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="${W}" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>${BODY}<w:sectPr/></w:body>
</w:document>`

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>`

const RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`

const DOC_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`

const SETTINGS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="${W}"/>`

/** Build a fixture .docx at the given path; returns the path. */
export function buildFixture(path) {
  const zip = zipSync({
    '[Content_Types].xml': strToU8(CONTENT_TYPES),
    '_rels/.rels': strToU8(RELS),
    'word/document.xml': strToU8(DOCUMENT),
    'word/styles.xml': strToU8(STYLES),
    'word/settings.xml': strToU8(SETTINGS),
    'word/_rels/document.xml.rels': strToU8(DOC_RELS),
  }, { level: 6 })
  writeFileSync(path, Buffer.from(zip))
  return path
}

/** The absolute fixture path in the caller-provided directory. */
export function fixturePath(dir, name = '开题报告-初稿-专属表格样式.docx') {
  return join(dir, name)
}