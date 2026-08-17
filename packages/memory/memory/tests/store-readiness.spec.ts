import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import * as Memory from '@deepseek-ai/dsh-memory'
import { UTF8_BODY, UTF8_TITLE } from './fixtures/utf8-experience.ts'

const roots: string[] = []
const contexts: Context[] = []

afterEach(async () => {
  for (const ctx of contexts.splice(0)) await ctx.fiber.dispose()
  for (const root of roots.splice(0)) await rm(root, { recursive: true, force: true })
})

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), 'dsh-memory-store-'))
  roots.push(root)
  const memoryFile = join(root, 'missing-parent', 'memory.md')
  const factsDir = join(root, 'facts')
  const ctx = new Context()
  contexts.push(ctx)
  await ctx.plugin(Memory.MemoryService, { memoryFile, factsDir, maxFacts: 5, now: () => new Date('2026-08-16T02:34:23.123Z') })
  return { ctx, memoryFile }
}

function durable(id: string, title = 'Experience'): Memory.ExperienceMemory {
  return { id, title, keywords: ['typescript', 'encoding'], recordedAt: '2026-08-16T02:34:23.123Z', outcome: 'success', body: UTF8_BODY }
}

describe('release-ready Markdown and Store contracts', () => {
  it('parses an empty file and round-trips multiple UTF-8 records with nested headings', () => {
    expect(Memory.parseMemoryMarkdown('')).toEqual([])
    const records = [durable('memory-1', UTF8_TITLE), durable('memory-2', 'English experience')]
    expect(Memory.parseMemoryMarkdown(Memory.serializeMemoryMarkdown(records))).toEqual(records)
  })

  it('rejects malformed metadata, invalid H1 boundaries, duplicate ids, and empty bodies', () => {
    expect(() => Memory.parseMemoryMarkdown('# invalid\n')).toThrow(/invalid level-one heading/)
    expect(() => Memory.parseMemoryMarkdown('# One {memory-1}\n\nRecorded At: now\nOutcome: success\n\nbody\n')).toThrow(/Keywords/)
    const record = Memory.serializeMemoryMarkdown([durable('memory-1')])
    expect(() => Memory.parseMemoryMarkdown(record + record)).toThrow(/duplicate id/)
    expect(() => Memory.parseMemoryMarkdown('# Empty {memory-1}\n\nKeywords: x\nRecorded At: 2026-08-16T00:00:00.000Z\nOutcome: unknown\n')).toThrow(/empty body/)
  })

  it('creates a missing parent and file, then preserves multilingual content across reload', async () => {
    const { ctx, memoryFile } = await fixture()
    const [stored] = await ctx.memory.record([{ title: UTF8_TITLE, keywords: [' Encoding ', 'ENCODING', 'Windows'], body: UTF8_BODY }])
    expect(stored).toMatchObject({ id: 'memory-1', keywords: ['encoding', 'windows'], outcome: 'unknown' })
    expect(await readFile(memoryFile, 'utf8')).toContain('C:\\Users\\测试\\项目')

    const reloaded = new Memory.MemoryStore(memoryFile)
    expect(await reloaded.get('memory-1')).toEqual(stored)
  })

  it.each([
    [['memory-1', 'memory-2', 'memory-9'], 'memory-10'],
    [['memory-1', 'memory-100'], 'memory-101'],
  ])('allocates after the maximum durable id in %j', async (ids, expected) => {
    const { ctx, memoryFile } = await fixture()
    await mkdir(join(memoryFile, '..'), { recursive: true })
    await writeFile(memoryFile, Memory.serializeMemoryMarkdown(ids.map(id => durable(id))))
    await expect(ctx.memory.record([{ title: 'Next', keywords: ['id'], body: UTF8_BODY }]))
      .resolves.toMatchObject([{ id: expected }])
  })

  it('reloads external file changes for get and search', async () => {
    const { ctx, memoryFile } = await fixture()
    await ctx.memory.record([{ title: 'First', keywords: ['one'], body: UTF8_BODY }])
    const records = Memory.parseMemoryMarkdown(await readFile(memoryFile, 'utf8'))
    await writeFile(memoryFile, Memory.serializeMemoryMarkdown([...records, durable('memory-8', 'External')]))
    await expect(ctx.memory.get('memory-8')).resolves.toMatchObject({ title: 'External' })
    await expect(ctx.memory.search({ keywords: ['encoding'] })).resolves.toEqual(expect.arrayContaining([expect.objectContaining({ id: 'memory-8' })]))
  })

  it('rejects blank title, body, and keywords without partially writing a batch', async () => {
    const { ctx, memoryFile } = await fixture()
    await expect(ctx.memory.record([{ title: ' ', keywords: ['x'], body: UTF8_BODY }])).rejects.toMatchObject({ code: 'MEMORY_EMPTY_TITLE' })
    await expect(ctx.memory.record([{ title: 'Body', keywords: ['x'], body: ' ' }])).rejects.toMatchObject({ code: 'MEMORY_EMPTY_BODY' })
    await expect(ctx.memory.record([{ title: 'Keywords', keywords: [], body: UTF8_BODY }])).rejects.toMatchObject({ code: 'MEMORY_EMPTY_KEYWORDS' })
    await expect(ctx.memory.record([
      { title: 'Valid', keywords: ['x'], body: UTF8_BODY },
      { title: '', keywords: ['y'], body: UTF8_BODY },
    ])).rejects.toMatchObject({ code: 'MEMORY_EMPTY_TITLE' })
    await expect(readFile(memoryFile, 'utf8')).rejects.toMatchObject({ code: 'ENOENT' })
  })

  it('keeps all records and unique ids across three concurrent appends', async () => {
    const { ctx } = await fixture()
    const results = await Promise.all(['A', 'B', 'C'].map(title => ctx.memory.record([{ title, keywords: [title], body: UTF8_BODY }])))
    expect(results.flat().map(record => record.id).sort()).toEqual(['memory-1', 'memory-2', 'memory-3'])
    await expect(Promise.all(['memory-1', 'memory-2', 'memory-3'].map(id => ctx.memory.get(id))))
      .resolves.toEqual(expect.arrayContaining([expect.objectContaining({ title: 'A' }), expect.objectContaining({ title: 'B' }), expect.objectContaining({ title: 'C' })]))
  })
})

