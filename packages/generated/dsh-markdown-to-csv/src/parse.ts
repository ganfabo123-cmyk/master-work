/**
 * Local markdown table parsing. The calling agent normalizes the user's raw
 * pasted text (fixing pipes, alignment, delimiter rows, and column counts)
 * before calling the tool; this module extracts the first contiguous table and
 * parses its cells, padding short rows to the header width and failing loudly
 * on rows longer than the header.
 */

export interface ParsedTable {
  readonly columns: string[]
  readonly rows: string[][]
}

const ESCAPED_PIPE = '\u0000'

function isPipeLine(line: string): boolean {
  return line.includes('|')
}

/** Split one table row into trimmed cells, honoring `\|` escapes. */
function splitCells(line: string): string[] {
  const protectedLine = line.replaceAll('\\|', ESCAPED_PIPE)
  const trimmed = protectedLine.trim()
  let body = trimmed
  if (body.startsWith('|')) body = body.slice(1)
  if (body.endsWith('|')) body = body.slice(0, -1)
  return body
    .split('|')
    .map(cell => cell.replaceAll(ESCAPED_PIPE, '|').trim())
}

/** A markdown delimiter row (`| --- | :---: | --- |`) separates header from data. */
function isDelimiterRow(cells: readonly string[]): boolean {
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell))
}

/**
 * Parse the first contiguous run of pipe-bearing lines as a markdown table.
 * @param markdown - Text that must contain a markdown table (prose around it
 *   is ignored, but prose between pipe lines ends the run).
 * @returns The parsed header and data rows.
 * @throws When the text contains no table or a data row exceeds the header width.
 */
export function parseMarkdownTable(markdown: string): ParsedTable {
  const lines = markdown.split(/\r?\n/)
  const tableStart = lines.findIndex(isPipeLine)
  if (tableStart === -1) {
    throw new Error('markdown_to_csv: no markdown table found in the input')
  }
  const pipeLines: string[] = []
  for (let index = tableStart; index < lines.length; index += 1) {
    const line = lines[index]
    if (line === undefined) break
    if (!isPipeLine(line)) break
    pipeLines.push(line)
  }
  if (pipeLines.length === 0) {
    throw new Error('markdown_to_csv: no markdown table found in the input')
  }

  const rows = pipeLines.map(splitCells)
  const header = rows[0] ?? []
  if (header.length === 0) {
    throw new Error('markdown_to_csv: the markdown table has no columns')
  }

  // A delimiter row (`| --- | --- |`) separates the header from the data;
  // the header is always the first row.
  const dataStart = rows.length > 1 && isDelimiterRow(rows[1] ?? []) ? 2 : 1

  const dataRows = rows.slice(dataStart).map((cells, index) => {
    if (cells.length > header.length) {
      const rowNumber = index + 1
      throw new Error(
        `markdown_to_csv: row ${rowNumber} has ${cells.length} cells but the header has ${header.length}; `
        + 'align every row to the header width before calling the tool again',
      )
    }
    while (cells.length < header.length) cells.push('')
    return cells
  })
  return { columns: header, rows: dataRows }
}
