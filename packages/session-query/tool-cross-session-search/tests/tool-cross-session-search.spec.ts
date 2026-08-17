import { afterEach, describe, expect, it, vi } from 'vitest'
import { Context, type Fiber } from '@deepseek-ai/cordis'
import type { Agent } from '@deepseek-ai/dsh-agent'
import { createUserMessage, CallId } from '@deepseek-ai/dsh-llm'
import SessionStore, {
  SESSION_FORMAT_VERSION,
  SessionId,
  type Session,
  type SessionHeader,
  type SessionId as SessionIdValue,
} from '@deepseek-ai/dsh-session'
import SessionQueryEngine, {
  type SessionEventSearchHit,
  type SessionEventSearchPage,
  type SessionEventSearchRequest,
  type SessionSearchExecContext,
  type SessionSearchHit,
  type SessionSearchPage,
  type SessionSearchRequest,
  type SessionTitleObservationResult,
} from '@deepseek-ai/dsh-session-query'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime, { type ToolExecutionResult } from '@deepseek-ai/dsh-tools'
import ApprovalService, { type ApprovalOutcome } from '@deepseek-ai/dsh-user-approval'
import * as ToolCrossSessionSearch from '@deepseek-ai/dsh-tool-cross-session-search'

const activeContexts: Context[] = []

afterEach(async () => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  for (const ctx of activeContexts.splice(0)) await ctx.fiber.dispose()
  FakeQuery.reset()
})

function header(id: string, cwd: string | undefined, createdAt = 1): SessionHeader {
  return {
    version: SESSION_FORMAT_VERSION,
    id: SessionId(id),
    createdAt,
    ...cwd === undefined ? {} : { cwd },
  }
}

function createSession(ctx: Context, id: string, cwd: string | undefined, createdAt = 10): Session {
  return ctx.sessions.create(SessionId(id), {
    meta: { createdAt, ...cwd === undefined ? {} : { cwd } },
  })
}

function openStep(session: Session): void {
  session.append('turn/start', { turn: 1 })
  session.append(
    'user/message',
    createUserMessage({ content: [{ type: 'text', text: 'live needle' }], source: { kind: 'user' } }),
    { surfaceOp: 'append' },
  )
  session.append('step/start', { turn: 1, step: 1 })
}

function fakeAgent(session: Session): Agent {
  return { id: session.id, session } as unknown as Agent
}

function sessionHit(id: string, cwd: string | undefined, text = 'needle excerpt'): SessionSearchHit {
  return {
    header: header(id, cwd, 100),
    live: false,
    persisted: true,
    bestMatch: {
      sessionId: SessionId(id),
      seq: 4,
      type: 'assistant/message',
      time: 200,
      surface: 'current',
      snippet: text,
    },
  }
}

class FakeQuery extends SessionQueryEngine {
  static sessionSearch: (
    request: SessionSearchRequest,
    exec?: SessionSearchExecContext,
  ) => Promise<SessionSearchPage<SessionSearchHit>> = () => Promise.resolve({ items: [] })

  static sessionRequests: SessionSearchRequest[] = []
  static searchSignals: Array<AbortSignal | undefined> = []
  static titles = new Map<SessionIdValue, string | Error>()

  static reset(): void {
    this.sessionSearch = () => Promise.resolve({ items: [] })
    this.sessionRequests = []
    this.searchSignals = []
    this.titles = new Map()
  }

  override searchSessions(
    request: SessionSearchRequest,
    exec?: SessionSearchExecContext,
  ): Promise<SessionSearchPage<SessionSearchHit>> {
    FakeQuery.sessionRequests.push(request)
    FakeQuery.searchSignals.push(exec?.signal)
    return FakeQuery.sessionSearch(request, exec)
  }

  override searchEvents(
    request: SessionEventSearchRequest,
  ): Promise<SessionEventSearchPage> {
    const items: SessionEventSearchHit[] = []
    return Promise.resolve({
      session: header(request.sessionId, '/other'),
      items,
    })
  }

  override readTitleSnapshots(
    sessionIds: readonly SessionIdValue[],
    _signal?: AbortSignal,
  ): Promise<SessionTitleObservationResult[]> {
    return Promise.resolve(sessionIds.map((id): SessionTitleObservationResult => {
      const value = FakeQuery.titles.get(id)
      if (value === undefined) {
        return { sessionId: id, status: 'fulfilled', value: { session: header(id, '/other') } }
      }
      if (value instanceof Error) {
        return { sessionId: id, status: 'rejected', reason: value }
      }
      return {
        sessionId: id,
        status: 'fulfilled',
        value: {
          session: header(id, '/other'),
          title: {
            title: value,
            messageSeqs: [],
            source: { kind: 'fallback' },
            eventSeq: 0,
            updatedAt: 1,
          },
        },
      }
    }))
  }
}

interface Mounted {
  readonly ctx: Context
  readonly fiber: Fiber
  readonly caller: Session
  /** Decide how the single mounted answerer answers every approval/request. */
  answer: (outcome: ApprovalOutcome) => void
  call(name: string, args: unknown, options?: { agent?: Agent; signal?: AbortSignal }): Promise<ToolExecutionResult>
}

/** Mount with a single configurable approval answerer, or none when `withAnswerer` is false. */
async function mount(
  config: ToolCrossSessionSearch.Config = {},
  callerCwd: string | null = '/work',
  withAnswerer = true,
): Promise<Mounted> {
  const ctx = new Context()
  activeContexts.push(ctx)
  await ctx.plugin(SessionStore)
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  await ctx.plugin(ApprovalService)
  await ctx.plugin(FakeQuery)
  const fiber = await ctx.plugin(ToolCrossSessionSearch, config)

  let answer: ApprovalOutcome = 'allowed-once'
  if (withAnswerer) {
    ctx.on('approval/request', (): Promise<ApprovalOutcome> => Promise.resolve(answer))
  }

  const caller = createSession(ctx, 'caller', callerCwd ?? undefined, 10)
  openStep(caller)
  let calls = 0
  return {
    ctx,
    fiber,
    caller,
    answer: (outcome) => { answer = outcome },
    call: (name, args, options = {}) => ctx.tools.execute({
      name,
      arguments: args,
      callId: CallId(`call-${++calls}`),
      signal: options.signal ?? new AbortController().signal,
      ...options.agent === undefined ? { agent: fakeAgent(caller) } : { agent: options.agent },
    }),
  }
}

function text(result: ToolExecutionResult): string {
  return result.content.map(block => block.type === 'text' ? block.text : '').join('\n')
}

function errorCode(result: ToolExecutionResult): string | undefined {
  return result.isError ? result.error.info?.code : undefined
}

describe('registration, schemas, and disposal', () => {
  it('registers the cross-workspace tool, prompt, and pure generic presenter, then disposes them', async () => {
    const mounted = await mount({ maxSearchResults: 7 })
    const names = mounted.ctx.tools.schemas().map(schema => schema.name)
    expect(names).toEqual(['cross_session_search'])
    const schema = mounted.ctx.tools.schemas()[0]
    expect(schema?.parameters).not.toHaveProperty('properties.cwd')
    expect(schema?.parameters).not.toHaveProperty('properties.cursor')
    expect(schema?.parameters).not.toHaveProperty('properties.limit')
    const tool = mounted.ctx.tools.get('cross_session_search')
    expect('isConcurrencySafe' in (tool ?? {})).toBe(false)
    expect(mounted.ctx.tools.get('cross_session_search')?.presentCall?.({ query: 'needle' }))
      .toEqual({
        card: 'generic',
        kind: 'search',
        title: 'Search prior sessions across all workspaces',
        rawInput: 'needle',
      })
    expect(mounted.ctx.tools.get('cross_session_search')?.output.render({}, 'rendered'))
      .toEqual([{ type: 'text', text: 'rendered' }])

    await mounted.fiber.dispose()
    expect(mounted.ctx.tools.schemas().map(s => s.name)).not.toContain('cross_session_search')
  })
})

describe('approval gate and search', () => {
  it('grants the search and finds cross-workspace hits after user approval', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({
      items: [sessionHit('target-a', '/other/work')],
    })
    FakeQuery.titles.set(SessionId('target-a'), 'Other Workspace Goal')

    const result = await mounted.call('cross_session_search', { query: 'needle' })

    expect(result.isError).toBe(false)
    expect(text(result)).toContain('Other Workspace Goal')
    expect(text(result)).toContain('/other/work')
    expect(text(result)).toContain('needle excerpt')
  })

  it('emits the approval audit pair onto the caller session and forwards the query', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [sessionHit('target-a', '/other')] })

    await mounted.call('cross_session_search', { query: 'needle' })

    const events = mounted.caller.events
    const asked = events.filter(event => event.type === 'approval/asked')
    const decided = events.filter(event => event.type === 'approval/decided')
    expect(asked).toHaveLength(1)
    expect((asked[0] as { data: { reason?: string } }).data.reason).toContain('needle')
    expect(decided).toHaveLength(1)
    expect((decided[0] as { data: { outcome: ApprovalOutcome } }).data.outcome).toBe('allowed-once')
  })

  it('fails closed with no leak when the user rejects approval', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [sessionHit('secret-a', '/other')] })
    mounted.answer('rejected')

    const result = await mounted.call('cross_session_search', { query: 'needle' })

    expect(result.isError).toBe(true)
    expect(errorCode(result)).toBe('SESSION_CROSS_SEARCH_DENIED')
    expect(text(result)).not.toContain('secret-a')
    expect(FakeQuery.sessionRequests).toHaveLength(0)
  })

  it('fails closed with no leak when approval is cancelled', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [sessionHit('secret-b', '/other')] })
    mounted.answer('cancelled')

    const result = await mounted.call('cross_session_search', { query: 'needle' })

    expect(result.isError).toBe(true)
    expect(errorCode(result)).toBe('SESSION_CROSS_SEARCH_DENIED')
    expect(text(result)).not.toContain('secret-b')
    expect(FakeQuery.sessionRequests).toHaveLength(0)
  })

  it('fails closed when no approval answerer is composed (unavailable)', async () => {
    const mounted = await mount({}, '/work', false)
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [sessionHit('secret-c', '/other')] })

    const result = await mounted.call('cross_session_search', { query: 'needle' })

    expect(result.isError).toBe(true)
    expect(errorCode(result)).toBe('SESSION_CROSS_SEARCH_DENIED')
    expect(text(result)).toContain('no approval answerer')
    expect(FakeQuery.sessionRequests).toHaveLength(0)
  })

  it('fails loudly when the approval request itself throws', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [sessionHit('secret-d', '/other')] })
    vi.spyOn(mounted.ctx.approval, 'request').mockRejectedValueOnce(new Error('boom'))

    const result = await mounted.call('cross_session_search', { query: 'needle' })

    expect(result.isError).toBe(true)
    expect(errorCode(result)).toBe('SESSION_CROSS_SEARCH_APPROVAL_FAILED')
    expect(FakeQuery.sessionRequests).toHaveLength(0)
  })

  it('fails loudly when no agent-bound caller is present', async () => {
    const mounted = await mount()
    const result = await mounted.ctx.tools.execute({
      name: 'cross_session_search',
      arguments: { query: 'n' },
      callId: CallId('no-agent'),
      signal: new AbortController().signal,
      agent: undefined,
    } as never)
    expect(result.isError).toBe(true)
    expect(errorCode(result)).toBe('SESSION_CROSS_SEARCH_MISSING_AGENT')
  })

  it('searches every workspace by omitting a cwd filter', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [] })
    await mounted.call('cross_session_search', { query: 'needle' })
    expect(FakeQuery.sessionRequests).toHaveLength(1)
    const filters = FakeQuery.sessionRequests[0]?.sessionFilters ?? []
    expect(filters.some(filter => filter.kind === 'cwd')).toBe(false)
  })

  it('honors parent and root filter arguments without a cwd clause', async () => {
    const mounted = await mount()
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [] })
    await mounted.call('cross_session_search', {
      query: 'needle',
      parent_session_ids: ['pa', 'pb'],
      include_root_sessions: true,
    })
    const filters = FakeQuery.sessionRequests[0]?.sessionFilters
    expect(filters?.some(filter => filter.kind === 'cwd')).toBe(false)
    expect(filters?.some(filter =>
      filter.kind === 'parent'
      && 'values' in filter
      && filter.values.includes(null))).toBe(true)
  })

  it('enforces the configured result cap in the service layer', async () => {
    const mounted = await mount({ maxSearchResults: 2 })
    FakeQuery.sessionSearch = () => Promise.resolve({ items: [
      sessionHit('a', '/x'), sessionHit('b', '/y'), sessionHit('c', '/z'),
    ] })
    const result = await mounted.call('cross_session_search', { query: 'needle' })
    expect(text(result)).toContain('(2)')
    expect(text(result)).not.toContain('Session c')
    expect(text(result)).toContain('Result cap reached.')
  })
})
