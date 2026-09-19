import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { CallId, createUserMessage, LlmAdapter, type GenerateOptions, type LlmResolvedModelInfo, type StreamChunk } from '@deepseek-ai/dsh-llm'
import LlmRuntime from '@deepseek-ai/dsh-llm'
import SessionStore, { SessionId } from '@deepseek-ai/dsh-session'
import AgentRegistry from '@deepseek-ai/dsh-agent'
import AgentLoop from '@deepseek-ai/dsh-agent-loop'
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
  await ctx.plugin(Memory, { memoryDir: join(root, 'memory'), factsDir })
  return { ctx, factsDir, cwdA, cwdB }
}

describe('fact JSON format', () => {
  it('round-trips canonical records', () => {
    const facts: Memory.FactMemory[] = [
      { title: 'user name', body: 'gan' },
      { title: 'editor', body: 'vscode' },
    ]
    expect(Memory.parseFactsJson(Memory.serializeFactsJson(facts))).toEqual(facts)
  })

  it('normalizes titles to lowercase', () => {
    const json = Memory.serializeFactsJson([
      { title: 'User Name', body: 'gan' },
    ])
    const parsed = Memory.parseFactsJson(json)
    expect(parsed[0]?.title).toBe('user name')
  })

  it('rejects malformed JSON and empty bodies', () => {
    expect(() => Memory.parseFactsJson('invalid json')).toThrow()
    expect(() => Memory.parseFactsJson('[{ "title": "test", "body": "" }]')).toThrow(/empty body/)
    expect(() => Memory.parseFactsJson('[{ "title": "", "body": "content" }]')).toThrow(/empty title/)
  })
})

describe('per-cwd fact files', () => {
  it('derives a stable, distinct file name per absolute cwd', () => {
    const a = Memory.factFileNameFor('D:/project-a')
    expect(a).toBe(Memory.factFileNameFor('D:/project-a'))
    expect(a).not.toBe(Memory.factFileNameFor('D:/project-b'))
    expect(a).toMatch(/^[0-9a-f]{16}\.json$/u)
    expect(Memory.factFileFor('D:/facts', 'D:/project-a')).toBe(join('D:/facts', a))
  })
})

describe('fact memory service', () => {
  it('remembers, lists, and forgets cwd-scoped facts with normalized keys', async () => {
    const { ctx, cwdA, cwdB } = await fixture()
    const remembered = await ctx.memory.rememberFact(cwdA, { title: ' User Name ', body: ' gan ' })
    expect(remembered).toEqual({ title: 'user name', body: 'gan' })

    expect(await ctx.memory.facts(cwdA)).toEqual([remembered])
    expect(await ctx.memory.facts(cwdB)).toEqual([])

    // Upsert replaces the body for the same normalized title.
    await ctx.memory.rememberFact(cwdA, { title: 'USER NAME', body: 'Gan2' })
    const facts = await ctx.memory.facts(cwdA)
    expect(facts).toHaveLength(1)
    expect(facts[0]).toMatchObject({ title: 'user name', body: 'Gan2' })

    expect(await ctx.memory.forgetFact(cwdA, ' user name ')).toBe(true)
    expect(await ctx.memory.facts(cwdA)).toEqual([])
    expect(await ctx.memory.forgetFact(cwdA, 'user name')).toBe(false)
  })

  it('rejects blank keys and values', async () => {
    const { ctx, cwdA } = await fixture()
    await expect(ctx.memory.rememberFact(cwdA, { title: '  ', body: 'x' })).rejects.toMatchObject({ code: 'FACT_EMPTY_TITLE' })
    await expect(ctx.memory.rememberFact(cwdA, { title: 'name', body: '  ' })).rejects.toMatchObject({ code: 'FACT_EMPTY_BODY' })
  })

  it('serializes concurrent remember calls without lost facts', async () => {
    const { ctx, cwdA } = await fixture()
    await Promise.all([
      ctx.memory.rememberFact(cwdA, { title: 'one', body: '1' }),
      ctx.memory.rememberFact(cwdA, { title: 'two', body: '2' }),
    ])
    const facts = await ctx.memory.facts(cwdA)
    expect(facts.map(fact => fact.title).sort()).toEqual(['one', 'two'])
  })

  it('persists facts to the per-cwd markdown file', async () => {
    const { ctx, factsDir, cwdA } = await fixture()
    await ctx.memory.rememberFact(cwdA, { title: 'user name', body: 'gan' })
    const file = Memory.factFileFor(factsDir, cwdA)
    await expect(readFile(file, 'utf8')).resolves.toContain('## user name')
    await expect(readFile(file, 'utf8')).resolves.toContain('gan')
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
    const remembered = await execute(ctx, agent, 'fact_remember', { title: 'user name', body: 'gan' })
    expect(textOf(remembered)).toContain('Remembered: user name')
    expect(await ctx.memory.facts(cwdA)).toHaveLength(1)

    const forgotten = await execute(ctx, agent, 'fact_forget', { title: 'user name' })
    expect(textOf(forgotten)).toContain('Forgot: user name')
    expect(await ctx.memory.facts(cwdA)).toEqual([])

    const again = await execute(ctx, agent, 'fact_forget', { title: 'user name' })
    expect(textOf(again)).toContain('No saved fact')
  })

  it('fails loudly without a session cwd', async () => {
    const { ctx } = await fixture()
    const remembered = await execute(ctx, undefined, 'fact_remember', { title: 'x', body: 'y' })
    expect(remembered.isError).toBe(true)
    expect(textOf(remembered)).toContain('fact_remember requires a session working directory')
    const forgotten = await execute(ctx, undefined, 'fact_forget', { title: 'x' })
    expect(forgotten.isError).toBe(true)
    expect(textOf(forgotten)).toContain('fact_forget requires a session working directory')
  })
})

describe('fact injection', () => {
  it('injects the current cwd facts as a system-prompt section', async () => {
    const { ctx, cwdA } = await fixture()
    ctx.systemPrompt.variable('cwd', () => cwdA)
    await ctx.memory.rememberFact(cwdA, { title: 'user name', body: 'gan' })

    const assembly = await ctx.systemPrompt.assemble()
    const injected = assembly.sections.find(section => section.name === 'memory:facts:injected')
    expect(injected?.text).toContain('## user name')
    expect(injected?.text).toContain('gan')
    expect(injected?.text).toContain('Remembered facts for this working directory')
  })

  it('injects nothing when the cwd has no facts or no cwd variable', async () => {
    const { ctx, cwdA, cwdB } = await fixture()
    ctx.systemPrompt.variable('cwd', () => cwdB)
    await ctx.memory.rememberFact(cwdA, { title: 'user name', body: 'gan' })

    const otherCwd = await ctx.systemPrompt.assemble()
    expect(otherCwd.sections.some(section => section.name === 'memory:facts:injected')).toBe(false)

    const noCwdVariable = new Context()
    contexts.push(noCwdVariable)
    await noCwdVariable.plugin(SystemPrompt)
    await noCwdVariable.plugin(ToolRuntime)
    await noCwdVariable.plugin(Memory, { memoryDir: join(await mkdtemp(join(tmpdir(), 'dsh-memory-nocwd-')), 'memory') })
    const noCwd = await noCwdVariable.systemPrompt.assemble()
    expect(noCwd.sections.some(section => section.name === 'memory:facts:injected')).toBe(false)
  })
})

describe('actual agent prompt assembly', () => {
  it('injects cwd facts into the real system prompt sent to the model', async () => {
    const root = await mkdtemp(join(tmpdir(), 'dsh-memory-agent-'))
    temporaryDirectories.push(root)
    const factsDir = join(root, 'facts')
    const cwd = 'D:\\PycharmProjects\\CodeHarness\\harness\\deepseek-harness'
    const adapter = new RecordingAdapter()
    const ctx = new Context()
    contexts.push(ctx)
    await ctx.plugin(LlmRuntime)
    await ctx.plugin(SessionStore)
    await ctx.plugin(SystemPrompt)
    await ctx.plugin(ToolRuntime)
    await ctx.plugin(AgentRegistry)
    await ctx.plugin(AgentLoop, { agents: [] })
    await ctx.plugin(Memory, { memoryDir: join(root, 'memory'), factsDir })
    ctx.llm.registerAdapter(['mock'], adapter)
    await ctx.memory.rememberFact(cwd, { title: '协作规范', body: '严格遵守当前指令范围' })

    const agent = ctx.agentLoop.create(SessionId('prompt-assembly'), {
      provider: 'mock',
      model: 'mock',
    }, { cwd })

    agent.followup(createUserMessage({ content: [{ type: 'text', text: 'hi' }], source: { kind: 'user' } }))
    await agent.whenIdle()

    const request = adapter.requests[0]
    expect(request?.system).toContain('Remembered facts for this working directory')
    expect(request?.system).toContain('## 协作规范')
    expect(request?.system).toContain('严格遵守当前指令范围')
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

class RecordingAdapter extends LlmAdapter {
  requests: GenerateOptions[] = []

  override resolveModel(provider: string, model: string): Promise<LlmResolvedModelInfo> {
    return Promise.resolve({ provider, id: model, name: model })
  }

  async * stream(options: GenerateOptions): AsyncIterable<StreamChunk> {
    this.requests.push(options)
    yield { type: 'block-start', index: 0, blockType: 'text' }
    yield { type: 'text-delta', index: 0, text: 'ok' }
    yield { type: 'block-end', index: 0, block: { type: 'text', text: 'ok' } }
    yield { type: 'usage', usage: { inputTokens: 10, outputTokens: 2 } }
    yield { type: 'finish', reason: { kind: 'stop' } }
  }
}
