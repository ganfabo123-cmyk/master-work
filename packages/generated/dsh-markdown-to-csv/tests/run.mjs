/**
 * Sandbox-safe unit tests for @deepseek-ai/dsh-markdown-to-csv.
 *
 * Runs as plain Node against the BUILT lib artifacts (no bundler, no child
 * processes): the deterministic engineering gate executes `pnpm test` inside
 * the sandbox, where vitest cannot load its config because Vite's Windows
 * realpath optimization spawns a helper process (EPERM).
 */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { sanitizeFilename, toCsv, toCsvBody } from '../lib/csv.js'
import { parseMarkdownTable } from '../lib/parse.js'
import { contentDisposition, downloadRouteHandler, DownloadStore, tokenFromPath } from '../lib/download.js'

const PREFIX = '/api/md-table-csv'

/** @type {{ name: string, fn: () => void | Promise<void> }[]} */
const tests = []

export function test(name, fn) {
  tests.push({ name, fn })
}

async function run() {
  let failed = 0
  for (const { name, fn } of tests) {
    try {
      await fn()
      console.log(`ok - ${name}`)
    } catch (error) {
      failed += 1
      console.error(`not ok - ${name}`)
      console.error(`  ${String(error && error.stack ? error.stack : error).split('\n').join('\n  ')}`)
    }
  }
  console.log(`${tests.length - failed}/${tests.length} tests passed`)
  if (failed > 0) process.exitCode = 1
}

// ---------------------------------------------------------------------------
// toCsv / toCsvBody / sanitizeFilename (src/csv.js)
// ---------------------------------------------------------------------------

test('toCsv serializes the header and rows with CRLF records', () => {
  assert.equal(toCsv(['name', 'age'], [['Ada', '36'], ['Bob', '41']]), 'name,age\r\nAda,36\r\nBob,41\r\n')
})

test('toCsv quotes fields containing commas, double quotes, or line breaks', () => {
  assert.equal(
    toCsv(['a', 'b', 'c'], [['x,y', 'he said "hi"', 'line1\nline2']]),
    'a,b,c\r\n"x,y","he said ""hi""","line1\nline2"\r\n',
  )
})

test('toCsv leaves fields with spaces and pipes unquoted', () => {
  assert.equal(toCsv(['a'], [[' plain | text ']]), 'a\r\n plain | text \r\n')
})

test('toCsvBody prepends the UTF-8 BOM for Excel compatibility', () => {
  assert.equal(toCsvBody('a\r\n'), '\uFEFFa\r\n')
})

test('sanitizeFilename strips path separators and header-hazardous punctuation', () => {
  assert.equal(sanitizeFilename('a/b\\c:d*e?f"g<h>i|j'), 'abcdefghij.csv')
})

test('sanitizeFilename falls back when nothing safe remains', () => {
  assert.equal(sanitizeFilename('///***'), 'table.csv')
  assert.equal(sanitizeFilename('   '), 'table.csv')
})

test('sanitizeFilename appends a .csv extension unless already present', () => {
  assert.equal(sanitizeFilename('sales'), 'sales.csv')
  assert.equal(sanitizeFilename('sales.csv'), 'sales.csv')
  assert.equal(sanitizeFilename('SALES.CSV'), 'SALES.CSV')
})

// ---------------------------------------------------------------------------
// parseMarkdownTable (src/parse.js)
// ---------------------------------------------------------------------------

test('parseMarkdownTable parses a table with a delimiter row', () => {
  const table = parseMarkdownTable('| 名称 | 数量 |\n| --- | --- |\n| 苹果 | 3 |\n| 香蕉 | 12 |')
  assert.deepEqual(table, { columns: ['名称', '数量'], rows: [['苹果', '3'], ['香蕉', '12']] })
})

test('parseMarkdownTable treats the first row as the header without a delimiter row', () => {
  const table = parseMarkdownTable('| a | b |\n| 1 | 2 |')
  assert.deepEqual(table, { columns: ['a', 'b'], rows: [['1', '2']] })
})

test('parseMarkdownTable tolerates missing leading/trailing pipes and ragged spacing', () => {
  const table = parseMarkdownTable('a | b\n 1  |  2 ')
  assert.deepEqual(table, { columns: ['a', 'b'], rows: [['1', '2']] })
})

test('parseMarkdownTable keeps escaped pipes inside cells', () => {
  const table = parseMarkdownTable('| col |\n| a \\| b |')
  assert.deepEqual(table.rows, [['a | b']])
})

test('parseMarkdownTable ignores prose around the first contiguous table', () => {
  const text = '前言文字\n无非表格内容\n| x | y |\n| 1 | 2 |\n\n结尾文字'
  const table = parseMarkdownTable(text)
  assert.deepEqual(table, { columns: ['x', 'y'], rows: [['1', '2']] })
})

test('parseMarkdownTable throws when the text contains no table', () => {
  assert.throws(() => parseMarkdownTable('只是一段普通文字，没有表格。'), /no markdown table found/)
  assert.throws(() => parseMarkdownTable(''), /no markdown table found/)
})

test('parseMarkdownTable pads short rows with empty cells', () => {
  const table = parseMarkdownTable('| a | b | c |\n| --- | --- | --- |\n| 1 |\n| 2 | 3 |')
  assert.deepEqual(table.rows, [['1', '', ''], ['2', '3', '']])
})

test('parseMarkdownTable fails loudly when a row is longer than the header', () => {
  assert.throws(
    () => parseMarkdownTable('| a |\n| 1 | 2 |'),
    /row 1 has 2 cells but the header has 1/,
  )
})

test('parseMarkdownTable recognizes aligned delimiter rows', () => {
  const table = parseMarkdownTable('| a | b |\n| :--- | ---: |\n| 1 | 2 |')
  assert.deepEqual(table, { columns: ['a', 'b'], rows: [['1', '2']] })
})

// ---------------------------------------------------------------------------
// DownloadStore / tokenFromPath / contentDisposition (src/download.js)
// ---------------------------------------------------------------------------

test('DownloadStore stores and resolves a download until its TTL expires', () => {
  const store = new DownloadStore({ ttlMs: 60_000, maxEntries: 4 })
  const token = store.put('\uFEFFa,b\r\n', 't.csv', 1_000)
  assert.deepEqual(store.resolve(token, 1_500), { csv: '\uFEFFa,b\r\n', filename: 't.csv', expiresAt: 61_000 })
  assert.equal(store.resolve(token, 61_000), undefined)
  assert.equal(store.size, 0)
})

test('DownloadStore returns undefined for unknown tokens', () => {
  const store = new DownloadStore({ ttlMs: 60_000, maxEntries: 4 })
  assert.equal(store.resolve('missing'), undefined)
})

test('DownloadStore evicts the oldest entries beyond the cap', () => {
  const store = new DownloadStore({ ttlMs: 60_000, maxEntries: 2 })
  const first = store.put('1', 'a.csv', 1_000)
  const second = store.put('2', 'b.csv', 2_000)
  const third = store.put('3', 'c.csv', 3_000)
  assert.equal(store.resolve(first, 4_000), undefined)
  assert.ok(store.resolve(second, 4_000))
  assert.ok(store.resolve(third, 4_000))
  assert.equal(store.size, 2)
})

test('DownloadStore clears every entry', () => {
  const store = new DownloadStore({ ttlMs: 60_000, maxEntries: 4 })
  store.put('1', 'a.csv')
  store.put('2', 'b.csv')
  store.clear()
  assert.equal(store.size, 0)
})

test('tokenFromPath extracts the single token segment under the prefix', () => {
  assert.equal(tokenFromPath(`${PREFIX}/abc-123`, PREFIX), 'abc-123')
  assert.equal(tokenFromPath(`${PREFIX}/token/sub`, PREFIX), undefined)
  assert.equal(tokenFromPath(`${PREFIX}`, PREFIX), undefined)
  assert.equal(tokenFromPath('/other/x', PREFIX), undefined)
})

test('contentDisposition carries an ASCII fallback and an RFC 5987 UTF-8 name', () => {
  assert.equal(
    contentDisposition('销售报告.csv'),
    `attachment; filename="____.csv"; filename*=UTF-8''${encodeURIComponent('销售报告.csv')}`,
  )
  assert.equal(contentDisposition('table.csv'), 'attachment; filename="table.csv"; filename*=UTF-8\'\'table.csv')
})

test('downloadRouteHandler serves the stored CSV with attachment headers', async () => {
  const store = new DownloadStore({ ttlMs: 60_000, maxEntries: 4 })
  const token = store.put('\uFEFF姓名,年龄\r\n甲,30\r\n', '数据.csv')
  const server = createServer(downloadRouteHandler(store, PREFIX))
  try {
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
    const address = server.address()
    if (address === null || typeof address === 'string') throw new Error('no listening address')
    const response = await fetch(`http://127.0.0.1:${address.port}${PREFIX}/${token}`)
    assert.equal(response.status, 200)
    assert.equal(response.headers.get('content-type'), 'text/csv; charset=utf-8')
    assert.equal(response.headers.get('cache-control'), 'no-store')
    assert.ok(response.headers.get('content-disposition').includes(`filename*=UTF-8''${encodeURIComponent('数据.csv')}`))
    const bytes = new Uint8Array(await response.arrayBuffer())
    assert.deepEqual([...bytes.slice(0, 3)], [0xef, 0xbb, 0xbf])
    assert.equal(Buffer.from(bytes).toString('utf8'), '\uFEFF姓名,年龄\r\n甲,30\r\n')
  } finally {
    server.close()
  }
})

test('downloadRouteHandler answers 404 for an unknown or expired token', async () => {
  const store = new DownloadStore({ ttlMs: 5, maxEntries: 4 })
  const token = store.put('x', 'a.csv', 1_000)
  const server = createServer(downloadRouteHandler(store, PREFIX))
  try {
    await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
    const address = server.address()
    if (address === null || typeof address === 'string') throw new Error('no listening address')
    const base = `http://127.0.0.1:${address.port}${PREFIX}`
    assert.equal((await fetch(`${base}/nope`)).status, 404)
    assert.equal((await fetch(`${base}/${token}`)).status, 404)
  } finally {
    server.close()
  }
})

await run()