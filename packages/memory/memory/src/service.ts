/**
 * Memory service: validate and record experiences, retrieve candidates, and load full records.
 *
 * @module @deepseek-ai/dsh-memory/service
 */

import { Service, type Context } from '@deepseek-ai/cordis'
import type { FactMemory } from './fact.ts'
import { normalizeFactTitle } from './fact.ts'
import {
  normalizeKeywords,
  type ExperienceMemory,
  type MemoryOutcome,
  type NewExperienceMemory,
} from './memory.ts'
import { KeywordRetriever } from './retrieval/keyword_retriever.ts'
import type { MemoryRetriever } from './retrieval/retriever.ts'
import { FactStore } from './store/fact_store.ts'
import { MemoryStore } from './store/memory_store.ts'

/** Stable error taxonomy for memory failures. */
export class MemoryError extends Error {
  constructor(message: string, readonly code: string, options?: ErrorOptions) {
    super(message, options)
    this.name = 'MemoryError'
  }
}

/** Runtime-owned dependencies for the memory service. */
export interface MemoryRuntime {
  readonly memoryFile: string
  readonly factsDir: string
  readonly maxFacts: number
  readonly now?: () => Date
  readonly retriever?: MemoryRetriever
}

/** One model-facing search candidate without an internal ranking score. */
export interface MemorySearchCandidate {
  readonly id: string
  readonly title: string
  readonly keywords: readonly string[]
  readonly matchedKeywords: readonly string[]
  readonly outcome: MemoryOutcome
}

/** Query accepted by {@link MemoryService.search}. */
export interface MemorySearchRequest {
  readonly keywords: readonly string[]
  readonly limit?: number
}

/** Process-global memory service backed by the configured experience file and per-cwd fact files. */
export class MemoryService extends Service {
  private readonly store: MemoryStore
  private readonly factStore: FactStore
  private readonly retriever: MemoryRetriever
  private readonly now: () => Date
  private readonly maxFacts: number

  constructor(ctx: Context, runtime: MemoryRuntime) {
    super(ctx, 'memory')
    this.store = new MemoryStore(runtime.memoryFile)
    this.factStore = new FactStore(runtime.factsDir)
    this.retriever = runtime.retriever ?? new KeywordRetriever()
    this.now = runtime.now ?? (() => new Date())
    this.maxFacts = runtime.maxFacts
  }

  /**
   * Validate and append one or more experiences to the formal memory store.
   * Keywords are persisted in canonical form, omitted outcomes become
   * `unknown`, and one Harness-generated ISO timestamp applies to the batch.
   * @param entries - model-authored experience fields supplied for persistence.
   * @param signal - operation cancellation.
   * @returns durable experiences with assigned ids and timestamps.
   */
  async record(entries: readonly NewExperienceMemory[], signal?: AbortSignal): Promise<ExperienceMemory[]> {
    if (entries.length === 0) throw new MemoryError('memory record requires at least one entry', 'MEMORY_EMPTY_BATCH')
    const recordedAt = this.now().toISOString()
    const durable = entries.map((entry) => {
      const title = entry.title.trim()
      const body = entry.body.trim()
      const keywords = normalizeKeywords(entry.keywords)
      if (title.length === 0) throw new MemoryError('memory title must not be blank', 'MEMORY_EMPTY_TITLE')
      if (/^#(?:\s|$)/mu.test(body)) throw new MemoryError('memory body must not contain a level-one heading', 'MEMORY_BODY_H1')
      if (body.length === 0) throw new MemoryError('memory body must not be blank', 'MEMORY_EMPTY_BODY')
      if (keywords.length === 0) throw new MemoryError('memory keywords must contain at least one non-blank value', 'MEMORY_EMPTY_KEYWORDS')
      return { title, body, keywords, outcome: entry.outcome ?? 'unknown', recordedAt }
    })
    return this.store.append(durable, signal)
  }

  /**
   * Select lightweight candidates. Internal ranking chooses Top-K only; the
   * returned order is stable id order and does not express relevance.
   * @param request - query keywords and optional candidate limit.
   * @param signal - operation cancellation.
   * @returns candidate metadata without bodies or ranking scores.
   */
  async search(request: MemorySearchRequest, signal?: AbortSignal): Promise<MemorySearchCandidate[]> {
    const keywords = normalizeKeywords(request.keywords)
    const limit = request.limit ?? 10
    if (!Number.isSafeInteger(limit) || limit < 1) throw new MemoryError('memory search limit must be a positive safe integer', 'MEMORY_INVALID_LIMIT')
    const selected = await this.retriever.search({ keywords, limit, ...signal === undefined ? {} : { signal } }, this.store)
    const documents = new Map((await this.store.listDocuments(signal)).map(document => [document.id, document]))
    return selected.flatMap((result) => {
      const document = documents.get(result.id)
      return document === undefined ? [] : [{
        id: document.id,
        title: document.title,
        keywords: document.keywords,
        matchedKeywords: result.matchedKeywords,
        outcome: document.outcome,
      }]
    })
  }

  /**
   * Read one complete experience by stable id.
   * @param id - stable `memory-N` identity.
   * @param signal - operation cancellation.
   * @returns the complete experience, or `undefined` when absent.
   */
  get(id: string, signal?: AbortSignal): Promise<ExperienceMemory | undefined> {
    return this.store.get(id, signal)
  }

  /**
   * Read every fact for one cwd in file order.
   * @param cwd - absolute session working directory.
   * @param signal - operation cancellation.
   * @returns durable cwd-scoped facts.
   */
  facts(cwd: string, signal?: AbortSignal): Promise<FactMemory[]> {
    return this.factStore.list(cwd, signal)
  }

  /**
   * Upsert one fact for a cwd, normalizing the title.
   * @param cwd - absolute session working directory.
   * @param input - the title/body to persist; the title is trimmed and lowercased.
   * @param signal - operation cancellation.
   * @returns the durable fact.
   */
  async rememberFact(cwd: string, input: { title: string; body: string }, signal?: AbortSignal): Promise<FactMemory> {
    const title = normalizeFactTitle(input.title)
    const body = input.body.trim()
    if (title.length === 0) throw new MemoryError('fact title must not be blank', 'FACT_EMPTY_TITLE')
    if (body.length === 0) throw new MemoryError('fact body must not be blank', 'FACT_EMPTY_BODY')
    const fact: FactMemory = { title, body }
    await this.factStore.set(cwd, fact, signal)
    return fact
  }

  /**
   * Remove one fact by normalized title for a cwd.
   * @param cwd - absolute session working directory.
   * @param title - the fact title to remove; trimmed and lowercased before lookup.
   * @param signal - operation cancellation.
   * @returns whether a fact with that title was removed.
   */
  forgetFact(cwd: string, title: string, signal?: AbortSignal): Promise<boolean> {
    return this.factStore.remove(cwd, normalizeFactTitle(title), signal)
  }

  /**
   * The configured cap on facts injected per cwd.
   * @returns the effective fact count budget for the injected section.
   */
  factBudget(): number {
    return this.maxFacts
  }
}
