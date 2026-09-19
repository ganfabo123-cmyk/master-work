import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { CallId } from '@deepseek-ai/dsh-llm'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import * as Memory from '@deepseek-ai/dsh-memory'
import { parseMemoryMarkdown, serializeMemoryMarkdown } from '@deepseek-ai/dsh-memory'

const temporaryDirectories: string[] = []
const contexts: Context[] = []

afterEach(async () => {
  for (const ctx of contexts.splice(0)) await ctx.fiber.dispose()
  for (const directory of temporaryDirectories.splice(0)) await rm(directory, { recursive: true, force: true })
})

async function fixture(): Promise<{ ctx: Context; memoryFile: string }> {
  const root = await mkdtemp(join(tmpdir(), 'dsh-memory-'))
  temporaryDirectories.push(root)
  const memoryDir = join(root, 'memory')
  const memoryFile = join(memoryDir, 'global_memory.md')
  const ctx = new Context()
  contexts.push(ctx)
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  await ctx.plugin(Memory, { memoryDir })
  return { ctx, memoryFile }
}

const body = `## Context

Windows TypeScript work.

## Problem

Chinese text was corrupted.

## Attempts

Default encoding failed.

## Resolution

Used explicit UTF-8.

## Lesson

Control source-file encoding.`

describe('experience Markdown format', () => {
  it('round-trips flat records with H2 body sections', () => {
    const memories: Memory.ExperienceMemory[] = [{
      id: 'memory-7', title: 'UTF-8 source edits', keywords: ['typescript', 'encoding'],
      recordedAt: '2026-08-16T02:34:23.123Z', outcome: 'success', body,
    }]
    expect(parseMemoryMarkdown(serializeMemoryMarkdown(memories))).toEqual(memories)
  })

  it('rejects any non-record H1 and duplicate ids', () => {
    expect(() => parseMemoryMarkdown('# Root Cause\n')).toThrow(/invalid level-one heading/)
    const record = serializeMemoryMarkdown([{
      id: 'memory-1', title: 'One', keywords: ['x'], recordedAt: '2026-08-16T00:00:00.000Z', outcome: 'unknown', body,
    }])
    expect(() => parseMemoryMarkdown(record + '\n' + record)).toThrow(/duplicate id/)
  })
})

describe('memory service', () => {
  it('normalizes durable keywords, defaults outcome, and loads a complete experience', async () => {
    const { ctx, memoryFile } = await fixture()
    const [stored] = await ctx.memory.record('global', [{
      title: ' Canonical keywords ', keywords: [' TypeScript ', 'TYPESCRIPT', ' encoding '], body,
    }])
    expect(stored).toMatchObject({ id: 'memory-1', title: 'Canonical keywords', keywords: ['typescript', 'encoding'], outcome: 'unknown' })
    expect(Number.isNaN(Date.parse(stored!.recordedAt))).toBe(false)
    expect(await ctx.memory.get('global', 'memory-1')).toEqual(stored)
    await expect(readFile(memoryFile, 'utf8')).resolves.toContain('Keywords: typescript, encoding')
  })

  it('rejects empty keywords and level-one headings in bodies', async () => {
    const { ctx } = await fixture()
    await expect(ctx.memory.record('global', [{ title: 'Empty', keywords: [' '], body }])).rejects.toMatchObject({ code: 'MEMORY_EMPTY_KEYWORDS' })
    await expect(ctx.memory.record('global', [{ title: 'H1', keywords: ['x'], body: '# Root Cause' }])).rejects.toMatchObject({ code: 'MEMORY_BODY_H1' })
  })

  it('serializes concurrent appends without lost records or duplicate ids', async () => {
    const { ctx } = await fixture()
    const [first, second] = await Promise.all([
      ctx.memory.record('global', [{ title: 'First', keywords: ['one'], outcome: 'success', body }]),
      ctx.memory.record('global', [{ title: 'Second', keywords: ['two'], outcome: 'failure', body }]),
    ])
    expect([first[0]?.id, second[0]?.id].sort()).toEqual(['memory-1', 'memory-2'])
    expect(await ctx.memory.get('global', 'memory-1')).toBeDefined()
    expect(await ctx.memory.get('global', 'memory-2')).toBeDefined()
  })

  it('uses score only to select Top-K, then presents candidates by ascending id', async () => {
    const { ctx } = await fixture()
    await ctx.memory.record('global', [
      { title: 'Weak older match', keywords: ['encoding'], body },
      { title: 'Strong match', keywords: ['encoding', 'typescript', 'windows'], body },
      { title: 'Weak newer match', keywords: ['encoding'], body },
    ])
    const candidates = await ctx.memory.search('global', { keywords: [' TypeScript ', 'ENCODING'], limit: 2 })
    expect(candidates.map(candidate => candidate.id)).toEqual(['memory-1', 'memory-2'])
    expect(candidates[1]?.matchedKeywords).toEqual(['encoding', 'typescript'])
    expect(candidates[0]).not.toHaveProperty('rankingScore')
  })

  it('isolates files and id allocation by normalized block name', async () => {
    const { ctx, memoryFile } = await fixture()
    const [globalMemory] = await ctx.memory.record(' GLOBAL ', [{ title: 'Global', keywords: ['shared'], body }])
    const [pythonMemory] = await ctx.memory.record('Python', [{ title: 'Python', keywords: ['shared'], body }])
    expect(globalMemory?.id).toBe('memory-1')
    expect(pythonMemory?.id).toBe('memory-1')
    expect(await ctx.memory.search('global', { keywords: ['shared'] })).toMatchObject([{ title: 'Global' }])
    expect(await ctx.memory.search('python', { keywords: ['shared'] })).toMatchObject([{ title: 'Python' }])
    await expect(readFile(memoryFile, 'utf8')).resolves.toContain('# Global {memory-1}')
    await expect(readFile(join(memoryFile, '..', 'python_memory.md'), 'utf8')).resolves.toContain('# Python {memory-1}')
  })

  it('rejects block names that can escape the memory directory', async () => {
    const { ctx } = await fixture()
    await expect(ctx.memory.search('../global', { keywords: ['x'] })).rejects.toMatchObject({ code: 'MEMORY_INVALID_BLOCK_NAME' })
  })

  it('lists every block that owns a durable file even when not loaded this process', async () => {
    const { ctx, memoryFile } = await fixture()
    await ctx.memory.record('python', [{ title: 'Python', keywords: ['shared'], body }])
    await ctx.memory.record('global', [{ title: 'Global', keywords: ['shared'], body }])
    await writeFile(join(memoryFile, '..', 'notes.md'), 'not a block file\n')
    expect(await ctx.memory.listBlocks()).toEqual(['global', 'python'])
  })

  it('returns an empty listing when the memory directory does not exist yet', async () => {
    const { ctx } = await fixture()
    await expect(ctx.memory.listBlocks()).resolves.toEqual([])
  })
})

describe('model-facing memory tools', () => {
  it('registers search/get/list-blocks/record without the retired tree tool', async () => {
    const { ctx } = await fixture()
    expect(ctx.tools.get('memory_search')).toBeDefined()
    expect(ctx.tools.get('memory_get')).toBeDefined()
    expect(ctx.tools.get('memory_list_blocks')).toBeDefined()
    expect(ctx.tools.get('memory_record')).toBeDefined()
    expect(ctx.tools.get('memory_children')).toBeUndefined()
  })

  it('lists block names through the model-facing tool without loading any block', async () => {
    const { ctx } = await fixture()
    const listed = textOf(await execute(ctx, 'memory_list_blocks', {}))
    expect(listed).toBe('No experience memory blocks exist.')
    await ctx.memory.record('dsh', [{ title: 'One', keywords: ['x'], body }])
    await ctx.memory.record('python', [{ title: 'Two', keywords: ['y'], body }])
    const after = textOf(await execute(ctx, 'memory_list_blocks', {}))
    expect(after).toContain('Experience memory blocks:')
    expect(after).toContain('- dsh')
    expect(after).toContain('- python')
  })

  it('records Tool Call fields directly without asking the user, then supports progressive loading', async () => {
    const { ctx, memoryFile } = await fixture()
    let questionCount = 0
    ctx.provide('userQuestions', {
      ask: () => {
        questionCount += 1
        throw new Error('memory_record must not ask the user')
      },
    })
    const recorded = await execute(ctx, 'memory_record', { block_name: 'dsh', entries: [{
      title: 'Encoding fix', keywords: [' TypeScript ', 'encoding'], outcome: 'success', body,
    }] })
    expect(textOf(recorded)).toContain('memory-1')
    expect(questionCount).toBe(0)
    await expect(readFile(join(memoryFile, '..', 'dsh_memory.md'), 'utf8')).resolves.toContain(body)

    const searched = textOf(await execute(ctx, 'memory_search', { block_name: 'dsh', keywords: ['encoding'] }))
    expect(searched).toContain('matched keywords: encoding')
    expect(searched).not.toContain('rankingScore')
    expect(searched).not.toContain('Control source-file encoding.')

    const loaded = textOf(await execute(ctx, 'memory_get', { block_name: 'dsh', id: 'memory-1' }))
    expect(loaded).toContain('Recorded At:')
    expect(loaded).toContain('Control source-file encoding.')
  })

  it('rejects malformed existing storage instead of accepting the retired tree format', async () => {
    const { ctx, memoryFile } = await fixture()
    await mkdir(join(memoryFile, '..'), { recursive: true })
    await writeFile(memoryFile, '# Old topic\n\n## Old child\n')
    await expect(ctx.memory.search('global', { keywords: ['old'] })).rejects.toThrow(/invalid level-one heading/)
  })
})

function execute(ctx: Context, name: string, args: object) {
  return ctx.tools.execute({ name, arguments: args, callId: CallId(`memory-test-${Math.random()}`), signal: new AbortController().signal })
}

function textOf(result: Awaited<ReturnType<typeof execute>>): string {
  return result.content.map(block => block.type === 'text' ? block.text : '').join('\n')
}
