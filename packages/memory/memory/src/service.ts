/**
 * Memory service: validate and record experiences, retrieve candidates, and load full records.
 *
 * @module @deepseek-ai/dsh-memory/service
 */

import { Service, type Context } from '@deepseek-ai/cordis'
import {
  normalizeKeywords,
  type ExperienceMemory,
  type MemoryOutcome,
  type NewExperienceMemory,
} from './memory.ts'
import { KeywordRetriever } from './retrieval/keyword_retriever.ts'
import type { MemoryRetriever } from './retrieval/retriever.ts'
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

/** Process-global experience memory backed by the configured Markdown file. */
export class MemoryService extends Service {
  private readonly store: MemoryStore
  private readonly retriever: MemoryRetriever
  private readonly now: () => Date

  constructor(ctx: Context, runtime: MemoryRuntime) {
    super(ctx, 'memory')
    this.store = new MemoryStore(runtime.memoryFile)
    this.retriever = runtime.retriever ?? new KeywordRetriever()
    this.now = runtime.now ?? (() => new Date())
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
}
