import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { Agent } from '@deepseek-ai/dsh-agent'
import { createUserMessage, CallId } from '@deepseek-ai/dsh-llm'
import SessionStore, {
  SESSION_FORMAT_VERSION,
  SessionId,
  type Session,
} from '@deepseek-ai/dsh-session'
import JsonlSessionPersistence from '@deepseek-ai/dsh-session-persistence-jsonl'
import SqliteSessionQueryEngine from '@deepseek-ai/dsh-session-query-sqlite'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import ApprovalService, { type ApprovalOutcome } from '@deepseek-ai/dsh-user-approval'
import * as ToolCrossSessionSearch from '@deepseek-ai/dsh-tool-cross-session-search'

const temporaryDirectories: string[] = []
const contexts: Context[] = []

afterEach(async () => {
  for (const ctx of contexts.splice(0)) await ctx.fiber.dispose()
  for (const directory of temporaryDirectories.splice(0)) {
    await rm(directory, { recursive: true, force: true })
  }
})

function fakeAgent(session: Session): Agent {
  return { id: session.id, session } as unknown as Agent
}

interface MountOptions {
  maxSearchResults?: number
  answer?: ApprovalOutcome
  withApproval?: boolean
}

async function mount({
  maxSearchResults = 20,
  answer = 'allowed-once',
  withApproval = true,
}: MountOptions = {}) {
  const root = await mkdtemp(join(tmpdir(), 'dsh-cross-session-'))
  temporaryDirectories.push(root)
  const ctx = new Context()
  contexts.push(ctx)
  await ctx.plugin(SessionStore)
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  if (withApproval) await ctx.plugin(ApprovalService)
  await ctx.plugin(JsonlSessionPersistence, { root, compression: 'none' })
  await ctx.plugin(SqliteSessionQueryEngine, { path: join(root, 'session-query.db'), openAt: 'first-search' })
  await ctx.plugin(ToolCrossSessionSearch, { maxSearchResults })

  if (withApproval) {
    ctx.on('approval/request', () => Promise.resolve<ApprovalOutcome>(answer))
  }

  const caller = ctx.sessions.create(SessionId('caller'), { meta: { createdAt: 10, cwd: '/caller' } })
  caller.append('turn/start', { turn: 1 })
  caller.append(
    'user/message',
    createUserMessage({ content: [{ type: 'text', text: 'caller context' }], source: { kind: 'user' } }),
    { surfaceOp: 'append' },
  )
  caller.append('step/start', { turn: 1, step: 1 })

  let calls = 0
  const execute = (args: unknown) => ctx.tools.execute({
    name: 'cross_session_search',
    arguments: args,
    callId: CallId(`cx-${++calls}`),
    signal: new AbortController().signal,
    agent: fakeAgent(caller),
  })
  return { ctx, caller, execute }
}

async function seedSession(ctx: Context, id: string, cwd: string, text: string): Promise<void> {
  await ctx.sessionPersistence.create({
    version: SESSION_FORMAT_VERSION,
    id: SessionId(id),
    createdAt: 1,
    cwd,
  })
  await ctx.sessionPersistence.append(SessionId(id), [{
    type: 'user/message',
    seq: 0,
    time: 2,
    data: createUserMessage({ content: [{ type: 'text', text }], source: { kind: 'user' } }),
    surfaceOp: 'append',
  }])
}

function textOf(result: { content: readonly { type: string; text?: string }[] }): string {
  return result.content.map(block => block.type === 'text' ? block.text ?? '' : '').join('\n')
}

describe('tool-cross-session-search with the real SQLite provider', () => {
  it('searches and returns persisted sessions in other workspaces after user approval', { timeout: 20_000 }, async () => {
    const { ctx, execute } = await mount()
    await seedSession(ctx, 'other-a', '/other/project-a', 'unrelated in project a')
    await seedSession(ctx, 'other-b', '/other/project-b', 'cross-workspace integration needle')

    const result = await execute({ query: 'cross-workspace integration needle' })

    expect(result.isError).toBe(false)
    const rendered = textOf(result)
    expect(rendered).toContain('other-b')
    expect(rendered).toContain('/other/project-b')
    expect(rendered).not.toContain('other-a')
  })

  it('returns nothing from other workspaces when the user rejects approval', { timeout: 20_000 }, async () => {
    const { ctx, execute } = await mount({ answer: 'rejected' })
    await seedSession(ctx, 'secret-other', '/other/hidden', 'hidden cross-workspace needle')

    const result = await execute({ query: 'hidden cross-workspace needle' })

    expect(result.isError).toBe(true)
    const rendered = textOf(result)
    expect(rendered).not.toContain('secret-other')
    expect(rendered).not.toContain('/other/hidden')
    expect(rendered).toContain('The user declined cross-workspace session search')
  })

  it('fails loudly when the approval service is not mounted', { timeout: 20_000 }, async () => {
    const { ctx, execute } = await mount({ withApproval: false })
    await seedSession(ctx, 'some-other', '/other/x', 'needle')

    const result = await execute({ query: 'needle' })

    expect(result.isError).toBe(true)
    const rendered = textOf(result)
    // Injection of the 'approval' service failed; the tool cannot run.
    expect(rendered.length).toBeGreaterThan(0)
  })

  it('enforces the configured result cap across workspaces', { timeout: 20_000 }, async () => {
    const { ctx, execute } = await mount({ maxSearchResults: 2 })
    await seedSession(ctx, 'cap-a', '/one', 'cap needle')
    await seedSession(ctx, 'cap-b', '/two', 'cap needle')
    await seedSession(ctx, 'cap-c', '/three', 'cap needle')

    const result = await execute({ query: 'cap needle' })

    expect(result.isError).toBe(false)
    const rendered = textOf(result)
    expect(rendered).toContain('(2)')
    expect(rendered).toContain('Result cap reached.')
    const count = (rendered.match(/\. Session /gu) ?? []).length
    expect(count).toBe(2)
  })

  it('records the approval audit pair on the caller session log', { timeout: 20_000 }, async () => {
    const { ctx, caller, execute } = await mount()
    await seedSession(ctx, 'audit-other', '/other/a', 'audit needle')
    await execute({ query: 'audit needle' })

    const asked = caller.events.filter(event => event.type === 'approval/asked')
    const decided = caller.events.filter(event => event.type === 'approval/decided')
    expect(asked).toHaveLength(1)
    expect(decided).toHaveLength(1)
    expect((decided[0] as { data: { outcome: ApprovalOutcome } }).data.outcome).toBe('allowed-once')
  })
})
