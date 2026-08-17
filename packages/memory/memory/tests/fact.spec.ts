import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { CallId } from '@deepseek-ai/dsh-llm'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import * as Memory from '@deepseek-ai/dsh-memory'

const temporaryDirectories: string[] = []
const contexts: Context[] = []

afterEach(async () => {
  for (const ctx of contexts.splice(0)) await ctx.fiber.dispose()
  for (const directory of temporaryDirectories.splice(0)) await rm(directory, { recursive: true, force: true })
})

async function fixture(): Promise<{ ctx: Context; factsDir: string; cwdA: string; cwdB: string }> {
  const root = await mkdtemp(join(tmpdir(), 'dsh-memory-facts-'))
  temporaryDirectories.push(root)
  const factsDir = join(root, 'facts')
  const cwdA = join(root, 'project-a')
  const cwdB = join(root, 'project-b')
  const ctx = new Context()
  contexts.push(ctx)
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  await ctx.plugin(Memory, { memoryFile: join(root, 'memory.md'), factsDir })
  return { ctx, factsDir, cwdA, cwdB }
}

describe('fact Markdown format', () => {
  it('round-trips canonical records and collapses duplicate keys', () => {
    const facts: Memory.FactMemory[] = [
      { key: 'user name', value: 'gan', recordedAt: '2026-08-16T02:34:23.123Z' },
      { key: 'editor', value: 'vscode', recordedAt: '2026-08-16T02:35:00.000Z' },
    ]
    expect(Memory.parseFacts(Memory.serializeFacts(facts))).toEqual(facts)
    expect(Memory.parseFacts(Memory.serializeFacts(facts) + Memory.serializeFacts([facts[0]!]))).toEqual(facts)
  })

  it('rejects non-canonical records and empty values', () => {
    expect(() => Memory.parseFacts('## Root Cause\n')).toThrow(/canonical fact records/)
    expect(() => Memory.parseFacts('# user name\nValue: \nRecorded At: 2026-01-01T00:00:00.000Z\n')).toThrow(/empty value/)
    expect(() => Memory.parseFacts('# user name\nRecorded At: 2026-01-01T00:00:00.000Z\n')).toThrow(/missing Value metadata/)
    expect(() => Memory.parseFacts('# user name\nValue: gan\nRecorded At: 2026-01-01T00:00:00.000Z\ntrailing junk\n')).toThrow(/unexpected content/)
  })
})

describe('per-cwd fact files', () => {
  it('derives a stable, distinct file name per absolute cwd', () => {
    const a = Memory.factFileNameFor('D:/project-a')
    expect(a).toBe(Memory.factFileNameFor('D:/project-a'))
    expect(a).not.toBe(Memory.factFileNameFor('D:/project-b'))
    expect(a).toMatch(/^[0-9a-f]{16}\.md$/u)
    expect(Memory.factFileFor('D:/facts', 'D:/project-a')).toBe(join('D:/facts', a))
  })
})

describe('fact memory service', () => {
  it('remembers, lists, and forgets cwd-scoped facts with normalized keys', async () => {
    const { ctx, cwdA, cwdB } = await fixture()
    const remembered = await ctx.memory.rememberFact(cwdA, { key: ' User Name ', value: ' gan ' })
    expect(remembered).toEqual({ key: 'user name', value: 'gan', recordedAt: remembered.recordedAt })
    expect(Number.isNaN(Date.parse(remembered.recordedAt))).toBe(false)

    expect(await ctx.memory.facts(cwdA)).toEqual([remembered])
    expect(await ctx.memory.facts(cwdB)).toEqual([])

    // Upsert replaces the value for the same normalized key.
    await ctx.memory.rememberFact(cwdA, { key: 'USER NAME', value: 'Gan2' })
    const facts = await ctx.memory.facts(cwdA)
    expect(facts).toHaveLength(1)
    expect(facts[0]).toMatchObject({ key: 'user name', value: 'Gan2' })

    expect(await ctx.memory.forgetFact(cwdA, ' user name ')).toBe(true)
    expect(await ctx.memory.facts(cwdA)).toEqual([])
    expect(await ctx.memory.forgetFact(cwdA, 'user name')).toBe(false)
  })

  it('rejects blank keys and values', async () => {
    const { ctx, cwdA } = await fixture()
    await expect(ctx.memory.rememberFact(cwdA, { key: '  ', value: 'x' })).rejects.toMatchObject({ code: 'FACT_EMPTY_KEY' })
    await expect(ctx.memory.rememberFact(cwdA, { key: 'name', value: '  ' })).rejects.toMatchObject({ code: 'FACT_EMPTY_VALUE' })
  })

  it('serializes concurrent remember calls without lost facts', async () => {
    const { ctx, cwdA } = await fixture()
    await Promise.all([
      ctx.memory.rememberFact(cwdA, { key: 'one', value: '1' }),
      ctx.memory.rememberFact(cwdA, { key: 'two', value: '2' }),
    ])
    const facts = await ctx.memory.facts(cwdA)
    expect(facts.map(fact => fact.key).sort()).toEqual(['one', 'two'])
  })

  it('persists facts to the per-cwd markdown file', async () => {
    const { ctx, factsDir, cwdA } = await fixture()
    await ctx.memory.rememberFact(cwdA, { key: 'user name', value: 'gan' })
    const file = Memory.factFileFor(factsDir, cwdA)
    await expect(readFile(file, 'utf8')).resolves.toContain('Value: gan')
  })
})

describe('model-facing fact tools', () => {
  it('registers fact_remember and fact_forget', async () => {
    const { ctx } = await fixture()
    expect(ctx.tools.get('fact_remember')).toBeDefined()
    expect(ctx.tools.get('fact_forget')).toBeDefined()
  })

  it('remembers and forgets through the tool surface using the session cwd', async () => {
    const { ctx, cwdA } = await fixture()
    const agent = { session: { header: { id: 'session-fact', cwd: cwdA } } }
    const remembered = await execute(ctx, agent, 'fact_remember', { key: 'user name', value: 'gan' })
    expect(textOf(remembered)).toContain('user name: gan')
    expect(await ctx.memory.facts(cwdA)).toHaveLength(1)

    const forgotten = await execute(ctx, agent, 'fact_forget', { key: 'user name' })
    expect(textOf(forgotten)).toContain('Forgot: user name')
    expect(await ctx.memory.facts(cwdA)).toEqual([])

    const again = await execute(ctx, agent, 'fact_forget', { key: 'user name' })
    expect(textOf(again)).toContain('No saved fact')
  })

  it('fails loudly without a session cwd', async () => {
    const { ctx } = await fixture()
    const remembered = await execute(ctx, undefined, 'fact_remember', { key: 'x', value: 'y' })
    expect(remembered.isError).toBe(true)
    expect(textOf(remembered)).toContain('fact_remember requires a session working directory')
    const forgotten = await execute(ctx, undefined, 'fact_forget', { key: 'x' })
    expect(forgotten.isError).toBe(true)
    expect(textOf(forgotten)).toContain('fact_forget requires a session working directory')
  })
})

describe('fact injection', () => {
  it('injects the current cwd facts as a system-prompt section', async () => {
    const { ctx, cwdA } = await fixture()
    ctx.systemPrompt.variable('cwd', () => cwdA)
    await ctx.memory.rememberFact(cwdA, { key: 'user name', value: 'gan' })

    const assembly = await ctx.systemPrompt.assemble()
    const injected = assembly.sections.find(section => section.name === 'memory:facts:injected')
    expect(injected?.text).toContain('user name: gan')
    expect(injected?.text).toContain('Remembered facts for this working directory')
  })

  it('injects nothing when the cwd has no facts or no cwd variable', async () => {
    const { ctx, cwdA, cwdB } = await fixture()
    ctx.systemPrompt.variable('cwd', () => cwdB)
    await ctx.memory.rememberFact(cwdA, { key: 'user name', value: 'gan' })

    const otherCwd = await ctx.systemPrompt.assemble()
    expect(otherCwd.sections.some(section => section.name === 'memory:facts:injected')).toBe(false)

    const noCwdVariable = new Context()
    contexts.push(noCwdVariable)
    await noCwdVariable.plugin(SystemPrompt)
    await noCwdVariable.plugin(ToolRuntime)
    await noCwdVariable.plugin(Memory, { memoryFile: join(await mkdtemp(join(tmpdir(), 'dsh-memory-nocwd-')), 'memory.md') })
    const noCwd = await noCwdVariable.systemPrompt.assemble()
    expect(noCwd.sections.some(section => section.name === 'memory:facts:injected')).toBe(false)
  })
})

function execute(ctx: Context, agent: unknown, name: string, args: object) {
  return ctx.tools.execute({
    name,
    arguments: args,
    callId: CallId(`fact-test-${Math.random()}`),
    ...agent === undefined ? {} : { agent: agent as never },
    signal: new AbortController().signal,
  })
}

function textOf(result: Awaited<ReturnType<typeof execute>>): string {
  return result.content.map(block => block.type === 'text' ? block.text : '').join('\n')
}
