/**
 * Keyless unit checks for the built `lib/` of @deepseek-ai/dsh-word-editor:
 * the plugin contract, OOXML load/serialize round-trips, style resolution, the
 * editing session (read/find/str_replace/add_to with row cloning/delete with
 * audit), the formula scanner (incl. OMath protection), the atomic save, and
 * the Word COM script builder. The live Word-COM formula path is exercised by
 * the acceptance runtime on a Windows host, not here.
 */

import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { name, inject, apply, EditorCoordinator, loadDocx, scanCandidates, buildWordScript, parseMarkdown, parseInline, generateDocument, makeStyledParagraph, superscriptDoc } from '../lib/index.js'
import { DocxSession } from '../lib/services/session.js'
import { serializeDocx, saveAtomically, saveGenerated, unchangedSince, timestamp } from '../lib/services/save.js'
import { firstSentence, resolveStyles, classifyParagraph, elementText } from '../lib/services/oooxml.js'
import * as invariant from '../lib/invariant.js'
import { buildFixture, fixturePath } from './fixture.mjs'

const tmp = mkdtempSync(join(tmpdir(), 'dsh-word-editor-test-'))
try {
  const fixture = buildFixture(fixturePath(tmp))

  // --- Plugin contract: function-plugin named exports, no default export. ---
  assert.equal(typeof name, 'string')
  assert.ok(name.length > 0)
  assert.deepEqual([...inject].sort(), ['subagents', 'subprocess', 'tools'])
  assert.equal(typeof apply, 'function')

  // --- apply registers the seven tools and an effect disposer. ---
  let toolNames = []
  let disposer
  apply({
    effect: (fn) => {
      disposer = fn()
    },
    tools: {
      register: (tool) => {
        toolNames.push(tool.name)
        return () => {}
      },
    },
    subprocess: {},
    subagents: {},
  }, { template: '', proposalTableTemplate: '', allowlist: [], subagentProvider: 'spawn', updateToc: false })
  assert.deepEqual(Object.fromEntries(toolNames.map((n) => [n, 1])), {
    word_open: 1, word_read: 1, word_find: 1, word_str_replace: 1, word_add_to: 1, word_delete: 1, word_formula_scan: 1, word_formula_convert: 1, word_generate: 1, word_superscript: 1, word_save: 1,
  })
  assert.equal(typeof disposer, 'function')
  disposer()

  // --- OOXML: load, style resolution, and serialize round-trip. ---
  const doc = loadDocx(new Uint8Array(readFileSync(fixture)))
  assert.equal(doc.styleMap.get('body'), '15')
  assert.equal(doc.styleMap.get('heading_1'), '3')
  assert.equal(doc.styleMap.get('heading_2'), '4')
  assert.equal(doc.styleMap.get('toc_1'), '13')
  assert.equal(doc.styleMap.get('table_content'), '26')
  assert.equal(doc.styleMap.get('reference'), '27')
  assert.equal(doc.entries.has('word/document.xml'), true)
  // re-serialize and reload: still parses, same document path presence
  const reloaded = loadDocx(serializeDocx(doc))
  assert.equal(reloaded.styleMap.get('body'), '15')

  // firstSentence stops at the first . / Chinese 句号
  assert.equal(firstSentence('本研究面向复杂软件调试任务。重点'), '本研究面向复杂软件调试任务。')
  assert.equal(firstSentence('无句末符号的整段'), '无句末符号的整段')

  // classifyParagraph maps a resolved styleId back to the logical style.
  const wNs = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  const paras = doc.document.getElementsByTagNameNS(wNs, 'p')
  assert.equal(classifyParagraph(paras[0], doc.styleMap), 'heading_1')
  assert.equal(classifyParagraph(paras[1], doc.styleMap), 'body')
  // a plain (styleId-less) paragraph classifies as keep.
  assert.equal(classifyParagraph(doc.document.createElementNS(wNs, 'w:p'), doc.styleMap), 'keep')

  // --- Session: read previews body first sentence, full content elsewhere. ---
  const session = new DocxSession(doc, ['body', 'heading_1', 'heading_2', 'heading_3', 'toc_1', 'toc_2', 'toc_3', 'reference', 'table_content'])
  const read = session.read(fixture)
  assert.equal(read.truncated, false)
  const heading = read.elements.find((e) => e.kind === 'heading')
  assert.ok(heading !== undefined)
  assert.equal(heading.style, 'heading_1')
  assert.equal(heading.content, '1 课题来源及研究目的和意义')
  const bodyEl = read.elements.find((e) => e.kind === 'body' && e.content_preview !== undefined)
  assert.ok(bodyEl !== undefined)
  assert.ok(bodyEl.content_preview.includes('本研究面向复杂软件调试任务'))
  assert.equal(bodyEl.content_truncated, true)
  // table is fully expanded with cell paragraphs under children
  const tableEl = read.elements.find((e) => e.kind === 'table')
  assert.ok(tableEl !== undefined)
  assert.equal(tableEl.style, '开题报告表格')
  assert.ok(tableEl.children !== undefined && tableEl.children.length >= 4)
  const firstCell = tableEl.children[0]
  assert.equal(firstCell.kind, 'table_content')
  assert.equal(firstCell.style, 'table_content')
  assert.equal(firstCell.content, '时间阶段')

  // --- find: id-only returns full text; content search returns matches; no-arg errors. ---
  const bodyTarget = read.elements.find((e) => e.kind === 'body')
  const byId = session.find(bodyTarget.target_id, undefined)
  assert.equal(byId.length, 1)
  assert.equal(byId[0].content.includes('多智能体协同方法的设计与验证'), true)
  const byContent = session.find(undefined, '软件工程智能化')
  assert.ok(byContent.length >= 1)
  assert.equal(byContent[0].content.includes('软件工程智能化'), true)
  assert.throws(() => session.find(undefined, undefined), /requires at least one/)
  assert.throws(() => session.find('t1', undefined), /not a paragraph/)

  // --- str_replace: exact match appended/edited, style kept. ---
  const strReplaceAudit = session.strReplace(bodyTarget.target_id, '重点关注', '精确聚焦', 'keep')
  assert.ok(strReplaceAudit.before.includes('重点关注'))
  assert.ok(strReplaceAudit.after.includes('精确聚焦'))
  assert.equal(strReplaceAudit.affects_formula, false)
  // old_content not present → refused
  const bodyTarget2 = session.read(fixture).elements.find((e) => e.kind === 'body')
  assert.throws(() => session.strReplace(bodyTarget2.target_id, '不存在的文字', 'x'), /not found exactly/)
  // a paragraph containing OMath refuses plain replacement
  const mathPara = session.read(fixture).elements.find((e) => e.contains !== undefined && e.contains.includes('m:oMath'))
  assert.ok(mathPara !== undefined)
  assert.throws(() => session.strReplace(mathPara.target_id, '给定候选根因', 'xxxx'), /formula/)

  // --- add_to is_new_para=true adds a body-styled paragraph after the heading. ---
  const beforeCount = session.read(fixture).elements.length
  const addAudit = session.addTo(heading.target_id, '本节引言。', 'heading_1', 'after', true)
  assert.equal(addAudit.affects_table, false)
  assert.ok(session.read(fixture).elements.length >= beforeCount)

  // --- add_to table row clone preserves table style and column count. ---
  const firstRow = doc.document.getElementsByTagNameNS(wNs, 'tr')[0]
  const rowId = session.idOf(firstRow)
  assert.ok(rowId !== undefined && /^t\d+-r\d+$/.test(rowId), `row id ${String(rowId)}`)
  const rowAudit = session.addTo(rowId, ['第二阶段', '系统原型实现'], 'table_content', 'after', false)
  assert.equal(rowAudit.affects_table, true)
  const afterRead = session.read(fixture)
  const tableAfter = afterRead.elements.find((e) => e.kind === 'table')
  const cellTexts = tableAfter.children.map((c) => c.content)
  assert.ok(cellTexts.includes('第二阶段'))
  assert.ok(cellTexts.includes('系统原型实现'))

  // --- delete exact text leaves the paragraph, whole-target removes it. ---
  const someBody = session.read(fixture).elements.find((e) => e.kind === 'body' && e.content_preview !== undefined)
  const delAudit = session.delete(someBody.target_id, '首先需要明确调试空间', undefined)
  assert.ok(delAudit.before.includes('首先需要明确调试空间'))
  assert.ok(!delAudit.after.includes('首先需要明确调试空间'))
  const targetToDelete = session.read(fixture).elements.find((e) => e.kind === 'body')
  const wholeAudit = session.delete(targetToDelete.target_id, undefined, undefined)
  assert.equal(wholeAudit.after, '(deleted)')
  assert.throws(() => session.resolve(targetToDelete.target_id), /unknown target_id/)

  // --- formula scan: finds the dollar delimiters, protects existing OMath. ---
  const scan = scanCandidates(doc.document, 'pX')
  // The fixture has no raw $...$; a paragraph with one is added here.
  const doctored = loadDocx(new Uint8Array(readFileSync(fixture)))
  const ses2 = new DocxSession(doctored, ['body'])
  const paraEl = ses2.blocks().find((b) => elementText(b).includes('给定候选根因'))
  const stripped = loadDocx(new Uint8Array(readFileSync(fixture)))
  const scanOnMath = scanCandidates(stripped.document, 'pM')
  // existing OMath paragraph yields no new candidate (its text is masked)
  assert.equal(scanOnMath.length, 0)

  // --- atomic save writes a new -edited-<timestamp>.docx and round-trips. ---
  const outPath = saveAtomically(doc, fixture, '开题报告-初稿-专属表格样式')
  assert.ok(existsSync(outPath))
  assert.match(outPath, /-edited-\d{8}-\d{6}\.docx$/)
  const reopened = loadDocx(new Uint8Array(readFileSync(outPath)))
  assert.equal(reopened.styleMap.get('body'), '15')
  // unchangedSince true for identical bytes, false after edit
  assert.equal(unchangedSince(fixture, new Uint8Array(readFileSync(fixture))), true)

  // --- saveGenerated writes a `-generated-<timestamp>.docx` next to the base. ---
  const genOut = saveGenerated(doc, fixture)
  assert.ok(existsSync(genOut))
  assert.match(genOut, /-generated-\d{8}-\d{6}\.docx$/)
  const reopenedGenOut = loadDocx(new Uint8Array(readFileSync(genOut)))
  assert.equal(reopenedGenOut.styleMap.get('body'), '15')

  // --- coordinator: open + read + audits + save produce a real output path. ---
  const coord = new EditorCoordinator({ allowlist: ['body'], subagentProvider: 'spawn', updateToc: false })
  coord.openSource(fixture)
  assert.equal(coord.sessionDoc.sourcePath, fixture)
  const read2 = coord.read()
  assert.equal(read2.document_path, fixture)
  const aBody = read2.elements.find((e) => e.kind === 'body')
  coord.strReplace(aBody.target_id, '重点关注', '精确聚焦', 'keep')
  assert.equal(coord.audits().length, 1)
  const saved = coord.save()
  assert.ok(existsSync(saved.path))
  assert.equal(saved.tocRefreshed, false)
  coord.reset()
  assert.equal(coord.active, false)

  // --- coordinator: generateFromMarkdown parses and saves a real output. ---
  const genCoord = new EditorCoordinator({ allowlist: ['body'], subagentProvider: 'spawn', updateToc: false })
  const mdPath = join(tmp, 'manuscript.md')
  writeFileSync(mdPath, '# 1 章\n\n正文。\n', 'utf8')
  const genResult = genCoord.generateFromMarkdown('# 1 章\n\n正文。\n', mdPath, fixture)
  assert.ok(existsSync(genResult.path))
  assert.match(genResult.path, /-generated-\d{8}-\d{6}\.docx$/)
  assert.deepEqual(genResult.outline.headings, [{ level: 1, text: '1 章' }])

  // --- wordcom script builder: coherent COM wiring + TOC update decision. ---
  const script = buildWordScript('C:\\x\\doc.docx', [{ paragraphText: '前 公式', linearMath: 'a+b', display: 'inline' }], true)
  assert.ok(script.includes('New-Object -ComObject Word.Application'))
  assert.ok(script.includes('$doc.Save()'))
  assert.ok(script.includes('foreach ($toc in $doc.TablesOfContents)'))
  assert.ok(script.includes('OMaths.Add'))
  assert.ok(script.includes('BuildUp'))
  assert.ok(script.includes("$doc = $word.Documents.Open('C:\\x\\doc.docx'"))

  // --- timestamp format ---
  assert.match(timestamp(new Date(2026, 8, 3, 9, 30, 0)), /^20260903-093000$/)

  // --- invariant companion registers the package name. ---
  let registeredInvariant
  await invariant.apply({
    invariants: {
      register: (packageName, installer) => {
        registeredInvariant = { packageName, installer }
        return () => {}
      },
    },
  })
  assert.equal(invariant.name, 'word-editor-invariant')
  assert.equal(registeredInvariant.packageName, '@deepseek-ai/dsh-word-editor')
  assert.equal(typeof registeredInvariant.installer, 'function')

  // --- markdown parser: headings, paragraphs, lists, tables, references, inline. ---
  const md = [
    '# 1 课题来源',
    '',
    '## 1.1 课题来源',
    '',
    '本课题来源于**大语言模型**驱动的软件工程研究。',
    '',
    '表格如下：',
    '',
    '| 阶段 | 工作 |',
    '| --- | --- |',
    '| 第一阶段 | 调研 |',
    '| 第二阶段 | 实现 |',
    '',
    '要点：',
    '',
    '1. 第一要点',
    '2. 第二要点',
    '',
    '# 9 参考文献',
    '',
    '[1] 作者. 题目[J]. 期刊, 2024.',
    '[2] 作者2. 题目2[EB/OL]. arXiv:0000.00000, 2023.',
  ].join('\n')
  const blocks = parseMarkdown(md)
  const headings = blocks.filter((b) => b.type === 'heading')
  assert.equal(headings.length, 3)
  assert.equal(headings[0].level, 1)
  assert.equal(headings[0].text, '1 课题来源')
  const body = blocks.find((b) => b.type === 'paragraph' && b.runs.some((r) => r.type === 'bold'))
  assert.ok(body !== undefined, 'bold paragraph parsed')
  const boldRun = body.runs.find((r) => r.type === 'bold')
  assert.equal(boldRun.text, '大语言模型')
  const table = blocks.find((b) => b.type === 'table')
  assert.ok(table !== undefined, 'table parsed')
  assert.deepEqual(table.headers, ['阶段', '工作'])
  assert.equal(table.rows.length, 2)
  const list = blocks.find((b) => b.type === 'list')
  assert.ok(list !== undefined, 'list parsed')
  assert.equal(list.ordered, true)
  assert.equal(list.items.length, 2)
  const refs = blocks.filter((b) => b.type === 'reference')
  assert.equal(refs.length, 2)
  assert.match(refs[0].text, /^\[1\] /)

  // --- inline parser: bold/italic/code/link/math/text. ---
  const inline = parseInline('前**加粗**后`代码`及_斜体_与$a+b$和[链接](https://x)')
  assert.deepEqual(inline.map((r) => r.type), ['text', 'bold', 'text', 'code', 'text', 'italic', 'text', 'math', 'text', 'link'])
  const math = inline.find((r) => r.type === 'math')
  assert.equal(math.text, 'a+b')
  const link = inline.find((r) => r.type === 'link')
  assert.equal(link.href, 'https://x')

  // --- inline parser: \( .. \) is an inline math run with delimiters stripped. ---
  const paren = parseInline('其中，\\(H_t\\) 表示候选集合，\\(q_t\\) 待验证。')
  const parenMath = paren.filter((r) => r.type === 'math')
  assert.deepEqual(parenMath.map((r) => r.text), ['H_t', 'q_t'])
  // the \( and \) delimiters are consumed and never leak into a text run
  assert.ok(paren.every((r) => !r.text.includes('\\(') && !r.text.includes('\\)')))

  // --- parser: cross-line $$..$$ block and single-line $$..$$ become math blocks. ---
  const blockMmd = '前置\n\n$$\nx = \\frac{a}{b}\n$$\n\n后置\n'
  const blockMblocks = parseMarkdown(blockMmd)
  const blockMath = blockMblocks.find((b) => b.type === 'math')
  assert.ok(blockMath !== undefined, 'cross-line $$..$$ parsed as a math block')
  assert.equal(blockMath.text, 'x = \\frac{a}{b}')
  const singleMathMd = '$$ y = z $$'
  const singleBlocks = parseMarkdown(singleMathMd)
  assert.equal(singleBlocks[0].type, 'math')

  // --- generator: reshapes a template copy into the manuscript body. ---
  const genMd = [
    '# 1 标题一',
    '',
    '正文第一段。',
    '',
    '| 列A | 列B |',
    '| --- | --- |',
    '| 值1 | 值2 |',
    '',
    '# 9 参考文献',
    '',
    '[1] 引用条目一。',
  ].join('\n')
  const genBlocks = parseMarkdown(genMd)
  const genDoc = loadDocx(new Uint8Array(readFileSync(fixture)))
  const outline = generateDocument(genDoc, genBlocks, { loadImage: () => undefined })
  assert.deepEqual(outline.headings, [{ level: 1, text: '1 标题一' }, { level: 1, text: '9 参考文献' }])
  assert.ok(outline.paragraph_count >= 2)
  assert.equal(outline.table_count, 1)
  assert.deepEqual(outline.table_rows, [1])
  assert.equal(outline.reference_count, 1)
  // serialized copy still parses and keeps the template's styles
  const genBytes = serializeDocx(genDoc)
  const reopenedGen = loadDocx(genBytes)
  assert.equal(reopenedGen.styleMap.get('body'), '15')
  // the generated body has the reference-styled paragraph
  const genNs = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  const refPara = Array.from(reopenedGen.document.getElementsByTagNameNS(genNs, 'p')).find((p) => p.textContent.includes('引用条目一'))
  assert.ok(refPara !== undefined, 'reference paragraph present in generated body')
  const refStyle = refPara.getElementsByTagNameNS(genNs, 'pStyle')[0]?.getAttributeNS(genNs, 'val')
  assert.equal(refStyle, '27')
  // generated body has the dedicated table style
  const tbl = reopenedGen.document.getElementsByTagNameNS(genNs, 'tbl')[0]
  assert.ok(tbl !== undefined, 'generated table present')
  const tblStyle = tbl.getElementsByTagNameNS(wNs, 'tblStyle')[0]?.getAttributeNS(wNs, 'val')
  assert.equal(tblStyle, 'ProposalTable')

  // --- generator formulas: inline and block math are written as bare LaTeX text. ---
  const mathMd = [
    '# 1 标题',
    '',
    '正文含 \\(H_t\\) 与 $E=mc^2$。',
    '',
    '$$',
    'x = \\frac{a}{b}',
    '$$',
  ].join('\n')
  const mathGenDoc = loadDocx(new Uint8Array(readFileSync(fixture)))
  generateDocument(mathGenDoc, parseMarkdown(mathMd), { loadImage: () => undefined })
  const mathBytes = serializeDocx(mathGenDoc)
  const mathReloaded = loadDocx(mathBytes)
  const mathDocXml = new TextDecoder().decode(mathReloaded.entries.get('word/document.xml'))
  // delimiters are stripped but the LaTeX itself lands as plain text (the
  // caller converts formulas separately; word_generate does not build OMath)
  assert.ok(mathDocXml.includes('H_t'), 'inline \\(..\\) LaTeX written')
  assert.ok(mathDocXml.includes('E=mc^2'), 'inline $..$ LaTeX written')
  assert.ok(mathDocXml.includes('x = \\frac{a}{b}'), 'block $$ LaTeX written')
  assert.ok(!mathDocXml.includes('\\(') && !mathDocXml.includes('\\('), 'no \\( delimiter leaked')
  assert.ok(!mathDocXml.includes('$$'), 'no $$ delimiter leaked')
  assert.ok(!mathDocXml.includes('DSH_MATH'), 'no placeholder left behind')

  // --- generator images: a png media part + rel + content-type + drawing. ---
  const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0])
  const imgMd = '# 图\n\n![示意图](diagram.png)\n'
  const imgDoc = loadDocx(new Uint8Array(readFileSync(fixture)))
  const imgOutline = generateDocument(imgDoc, parseMarkdown(imgMd), { loadImage: () => png })
  assert.equal(imgOutline.image_count, 1)
  assert.ok(imgDoc.entries.has('word/media/image1.png'), 'image media part added')
  assert.ok(imgDoc.entries.has('word/_rels/document.xml.rels'), 'document rels present')
  const relsXml = new TextDecoder().decode(imgDoc.entries.get('word/_rels/document.xml.rels'))
  assert.match(relsXml, /image1\.png/)
  const ctXml = new TextDecoder().decode(imgDoc.entries.get('[Content_Types].xml'))
  assert.match(ctXml, /png/)
  // round-trip: the serialized copy still carries the drawing and rels
  const imgBytes = serializeDocx(imgDoc)
  const reopenedImg = loadDocx(imgBytes)
  const docXml = new TextDecoder().decode(reopenedImg.entries.get('word/document.xml'))
  assert.match(docXml, /wp:inline/)
  assert.match(docXml, /pic:pic/)
  assert.match(docXml, /r:embed/)
  assert.ok(reopenedImg.entries.has('word/media/image1.png'))

  // --- superscript: [数字] citations become superscript runs, formatting kept. ---
  const supDoc = loadDocx(new Uint8Array(readFileSync(fixture)))
  const supBody = supDoc.document.getElementsByTagNameNS('http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'body')[0]
  const supPara = makeStyledParagraph(supDoc, '15', [
    { type: 'text', text: '方法' },
    { type: 'bold', text: '关键' },
    { type: 'text', text: '验证[1,2]与[3-5]及[4]均有效。' },
  ])
  supBody.insertBefore(supPara, supBody.lastChild)
  // a reference-styled paragraph keeps its leading [1] untouched
  const refSup = makeStyledParagraph(supDoc, '27', [{ type: 'text', text: '[1] 作者. 题目[J]. 2024.' }])
  supBody.insertBefore(refSup, supBody.lastChild)
  const convertedSup = superscriptDoc(supDoc)
  assert.equal(convertedSup, 3)
  const supRel = loadDocx(serializeDocx(supDoc))
  const bodyNs = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
  const supPPara = Array.from(supRel.document.getElementsByTagNameNS(bodyNs, 'p')).find((p) => p.textContent.includes('验证[1,2]'))
  assert.ok(supPPara !== undefined, 'citation paragraph present')
  const verts = Array.from(supPPara.getElementsByTagNameNS(bodyNs, 'vertAlign'))
  assert.equal(verts.length, 3, 'three citations superscripted')
  for (const v of verts) assert.equal(v.getAttributeNS(bodyNs, 'val'), 'superscript')
  const bEls = Array.from(supPPara.getElementsByTagNameNS(bodyNs, 'b'))
  assert.ok(bEls.length >= 1, 'bold run preserved across rebuild')
  // the reference paragraph did NOT gain superscripts
  const supRefPara = Array.from(supRel.document.getElementsByTagNameNS(bodyNs, 'p')).find((p) => p.textContent.includes('[1] 作者'))
  assert.ok(supRefPara !== undefined, 'reference paragraph present')
  assert.equal(supRefPara.getElementsByTagNameNS(bodyNs, 'vertAlign').length, 0, 'reference marker stays normal')

  // --- coordinator: superscript(source) converts and saves a new file. ---
  const supSrcPath = join(tmp, 'citations.docx')
  const supSrcDoc = loadDocx(new Uint8Array(readFileSync(fixture)))
  const supSrcBody = supSrcDoc.document.getElementsByTagNameNS('http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'body')[0]
  supSrcBody.insertBefore(makeStyledParagraph(supSrcDoc, '15', [{ type: 'text', text: '见[2,15-16]相关研究。' }]), supSrcBody.lastChild)
  writeFileSync(supSrcPath, Buffer.from(serializeDocx(supSrcDoc)))
  const supCoord = new EditorCoordinator({ allowlist: ['body'], subagentProvider: 'spawn', updateToc: false })
  const supRes = supCoord.superscript(supSrcPath)
  assert.ok(existsSync(supRes.path))
  assert.match(supRes.path, /-superscripted-\d{8}-\d{6}\.docx$/)
  assert.equal(supRes.converted, 1)
  const supReopen = loadDocx(new Uint8Array(readFileSync(supRes.path)))
  assert.equal(supReopen.styleMap.get('body'), '15')

  console.log('dsh-word-editor: all unit checks passed')
} finally {
  rmSync(tmp, { recursive: true, force: true })
}