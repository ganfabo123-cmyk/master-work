/**
 * Markdown parser of @deepseek-ai/dsh-word-editor: turns a well-formed Markdown
 * manuscript into typed blocks (headings, paragraphs, lists, tables, images,
 * references) with inline runs (bold / italic / code / link / math). The parser
 * targets the "known-good" manuscript format the generator consumes, so it is
 * deliberately permissive: unknown lines fall through to body paragraphs and
 * structural constructs it recognizes (headings, ordered/unordered lists,
 * pipe tables, reference entries, images) are extracted by shape, not by a
 * full CommonMark grammar.
 * @module @deepseek-ai/dsh-word-editor/services/markdown
 */

/** One inline run of a paragraph, with an optional link target or math flag. */
export type InlineRun =
  | { type: 'text'; text: string }
  | { type: 'bold'; text: string }
  | { type: 'italic'; text: string }
  | { type: 'code'; text: string }
  | { type: 'link'; text: string; href: string }
  | { type: 'math'; text: string; display: 'inline' }

/** A top-level block of the parsed manuscript. */
export type MdBlock =
  | { type: 'heading'; level: 1 | 2 | 3; text: string }
  | { type: 'paragraph'; runs: InlineRun[] }
  | { type: 'list'; ordered: boolean; items: InlineRun[][] }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'image'; alt: string; src: string }
  | { type: 'math'; text: string }
  | { type: 'reference'; text: string }

/**
 * Parse an entire Markdown manuscript into typed blocks.
 * @param markdown - the raw Markdown text.
 * @returns the ordered block list.
 */
export function parseMarkdown(markdown: string): MdBlock[] {
  const normalized = markdown.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = normalized.split('\n')
  const blocks: MdBlock[] = []
  let inReferences = false
  let i = 0
  while (i < lines.length) {
    const line = lines[i]!
    const trimmed = line.trim()

    // References: the `参考文献` heading switches the following `[n]` lines to
    // the reference style. The heading itself is emitted as a normal heading.
    if (/references|参考文献|参考资料/i.test(trimmed)) {
      const heading = parseHeading(line)
      if (heading !== undefined) {
        inReferences = true
        blocks.push(heading)
        i += 1
        continue
      }
    }

    if (trimmed === '') {
      i += 1
      continue
    }

    // A display-math block delimited by lone `$$` fences (content may span
    // several lines). The delimiters themselves are consumed, never included
    // in the saved math text. A single-line `$$...$$` is handled here too.
    if (trimmed.startsWith('$$')) {
      const inline1 = /^\$\$([\s\S]+?)\$\$$/.exec(trimmed)
      if (inline1 !== null) {
        blocks.push({ type: 'math', text: inline1[1]!.trim() })
        i += 1
        continue
      }
      if (trimmed === '$$') {
        const collected: string[] = []
        let j = i + 1
        while (j < lines.length && lines[j] !== undefined && lines[j]!.trim() !== '$$') {
          const l = lines[j]!
          if (l.trim() !== '') collected.push(l)
          j += 1
        }
        if (j < lines.length) {
          blocks.push({ type: 'math', text: collected.join('\n') })
          i = j + 1
          continue
        }
        // an unterminated $$ fence: fall through to normal paragraph handling
      }
    }

    const heading = parseHeading(line)
    if (heading !== undefined) {
      inReferences = heading.level === 1 && /参考文献|参考资料/i.test(heading.text)
      blocks.push(heading)
      i += 1
      continue
    }

    const image = parseImage(line)
    if (image !== undefined) {
      blocks.push(image)
      i += 1
      continue
    }

    if (line.startsWith('|')) {
      const parsedTable = parseTable(lines, i)
      if (parsedTable !== undefined) {
        blocks.push(parsedTable.table)
        i += parsedTable.consumed
        continue
      }
    }

    const reference = inReferences ? parseReference(line) : undefined
    if (reference !== undefined && trimmed.length > 0) {
      blocks.push({ type: 'reference', text: reference })
      i += 1
      continue
    }

    const list = parseList(lines, i)
    if (list !== undefined) {
      blocks.push(list.block)
      i += list.consumed
      continue
    }

    // A paragraph: consecutive non-blank, non-structural lines joined by a
    // single space until a blank line (the manuscript writes one sentence per
    // line).
    const paragraphLines: string[] = []
    while (i < lines.length && lines[i] !== undefined && lines[i]!.trim() !== '') {
      const l = lines[i]!
      if (
        parseHeading(l) !== undefined ||
        l.startsWith('|') ||
        (/^(?:\d+[\.、]|[-\*])\s+/.test(l.trim()) && paragraphLines.length === 0)
      ) {
        break
      }
      paragraphLines.push(l.trim())
      i += 1
    }
    if (paragraphLines.length > 0) {
      blocks.push({ type: 'paragraph', runs: parseInline(paragraphLines.join(' ')) })
      continue
    }
    i += 1
  }
  return blocks
}

/** Parse an ATX heading line, or undefined for a non-heading line. */
function parseHeading(line: string): Extract<MdBlock, { type: 'heading' }> | undefined {
  const m = /^(#{1,6})\s+(.*)$/.exec(line)
  if (m === null) return undefined
  const level = Math.min(m[1]!.length, 3) as 1 | 2 | 3
  return { type: 'heading', level, text: inlineText(m[2]!) }
}

/** Parse an image reference line like `![alt](src)` (whole line). */
function parseImage(line: string): Extract<MdBlock, { type: 'image' }> | undefined {
  const m = /^!\[([^\]]*)\]\(([^)\s]+)\)\s*$/.exec(line.trim())
  if (m === null) return undefined
  return { type: 'image', alt: m[1] ?? '', src: m[2]! }
}

/** A reference entry `[N] ...` or `[N]` Arabic-numeral-labeled line. */
function parseReference(line: string): string | undefined {
  const trimmed = line.trim()
  if (/^\[\d+\]/.test(trimmed) || /^\[\d+[-,、]\d+\]/.test(trimmed)) {
    return trimmed
  }
  return undefined
}

/** Parse a pipe table starting at the given line; returns undefined when the following line is not a separator. */
function parseTable(lines: string[], start: number): { table: Extract<MdBlock, { type: 'table' }>; consumed: number } | undefined {
  const headerLine = lines[start]!
  const headers = splitTableRow(headerLine)
  const separator = lines[start + 1]
  if (separator === undefined || !/^\s*\|?[\s:|-]+\|?\s*$/.test(separator) || !separator.includes('-')) {
    return undefined
  }
  const rows: string[][] = []
  let i = start + 2
  while (i < lines.length && lines[i] !== undefined && lines[i]!.trim().startsWith('|')) {
    const cells = splitTableRow(lines[i]!)
    // pad/trim to header width
    rows.push(cells.slice(0, headers.length))
    i += 1
  }
  return { table: { type: 'table', headers, rows }, consumed: i - start }
}

/** Split a pipe-table row into cell strings (trimming outer pipes). */
function splitTableRow(line: string): string[] {
  const trimmed = line.trim()
  const body = trimmed.startsWith('|') ? trimmed.slice(1) : trimmed
  const end = body.trimEnd().endsWith('|') ? body.trimEnd().slice(0, -1) : body.trimEnd()
  return end.split('|').map(c => c.trim())
}

/** Parse a consecutive list (ordered or unordered) starting at `start`. */
function parseList(lines: string[], start: number): { block: Extract<MdBlock, { type: 'list' }>; consumed: number } | undefined {
  const first = lines[start]!
  const firstMatch = /^(\d+[\.、]|[-*\u25a0])\s+/.exec(first.trim())
  if (firstMatch === null) return undefined
  const ordered = /^\d/.test(firstMatch[1]!)
  const items: InlineRun[][] = []
  const texts: string[] = []
  let i = start
  while (i < lines.length && lines[i] !== undefined) {
    const l = lines[i]!
    const m = /^(?:(\d+[\.、])|[-*\u25a0])\s+(.*)$/.exec(l.trim())
    if (m === null) break
    texts.push(m[2]!)
    const rawContent = texts[texts.length - 1]!
    items.push(parseInline(rawContent))
    i += 1
  }
  return { block: { type: 'list', ordered, items }, consumed: i - start }
}

/** The plain text of a heading after stripping inline markers. */
function inlineText(text: string): string {
  const runs = parseInline(text)
  return runs.map(r => r.text).join('')
}

/**
 * Tokenize a line into inline runs: bold / italic / code / link / math and
 * plain text. Kept simple: delimiters open and close on the same line.
 * @param text - the raw inline text.
 * @returns the ordered runs.
 */
export function parseInline(text: string): InlineRun[] {
  const runs: InlineRun[] = []
  let pos = 0
  while (pos < text.length) {
    const rest = text.slice(pos)
    const m =
      /^(?:\\\(([\s\S]*?)\\\)|\$\$([\s\S]{0,160}?)\$\$|\$([^\s$]{1,120}?)\$|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*]+)\*|_([^_]+)_)/.exec(rest)
    if (m === null) {
      // consume one char as text
      const prev = runs[runs.length - 1]
      if (prev !== undefined && prev.type === 'text') {
        prev.text += text[pos]!
      } else {
        runs.push({ type: 'text', text: text[pos]! })
      }
      pos += 1
      continue
    }
    const run = mi(m)
    if (run !== null) runs.push(run)
    // advance by the whole matched delimiter run length
    pos += m[0].length
  }
  return runs
}

/** Map a single regex match to an inline run. */
function mi(m: RegExpExecArray): InlineRun | null {
  if (m[1] !== undefined) return { type: 'math', text: m[1], display: 'inline' }
  if (m[2] !== undefined) return { type: 'math', text: m[2], display: 'inline' }
  if (m[3] !== undefined) return { type: 'math', text: m[3], display: 'inline' }
  if (m[4] !== undefined) return { type: 'code', text: m[4] }
  if (m[5] !== undefined && m[6] !== undefined) return { type: 'link', text: m[5], href: m[6] }
  if (m[7] !== undefined) return { type: 'bold', text: m[7] }
  if (m[8] !== undefined) return { type: 'bold', text: m[8] }
  if (m[9] !== undefined) return { type: 'italic', text: m[9] }
  if (m[10] !== undefined) return { type: 'italic', text: m[10] }
  return null
}

/** The plain text of a run (used for the structure preview). */
export function runText(run: InlineRun): string {
  return run.text
}
