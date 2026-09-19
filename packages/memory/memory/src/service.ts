/**
 * Memory service: validate and record experiences, retrieve candidates, and load full records.
 *
 * @module @deepseek-ai/dsh-memory/service
 */

import { Service, type Context } from '@deepseek-ai/cordis'
import { lstat, mkdir, readdir, rename } from 'node:fs/promises'
import { join } from 'node:path'
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
  readonly memoryDir: string
  /** Old single global file moved without rewriting on first global-block access. */
  readonly legacyMemoryFile?: string
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

/** Process-global memory service backed by block files and per-cwd fact files. */
export class MemoryService extends Service {
  private readonly stores = new Map<string, MemoryStore>()
  private readonly factStore: FactStore
  private readonly retriever: MemoryRetriever
  private readonly now: () => Date
  private readonly maxFacts: number
  private readonly memoryDir: string
  private readonly legacyMemoryFile: string | undefined
  private globalMigration: Promise<void> | undefined

  constructor(ctx: Context, runtime: MemoryRuntime) {
    super(ctx, 'memory')
    this.factStore = new FactStore(runtime.factsDir)
    this.retriever = runtime.retriever ?? new KeywordRetriever()
    this.now = runtime.now ?? (() => new Date())
    this.maxFacts = runtime.maxFacts
    this.memoryDir = runtime.memoryDir
    this.legacyMemoryFile = runtime.legacyMemoryFile
  }

  /**
   * Validate and append one or more experiences to the formal memory store.
   * Keywords are persisted in canonical form, omitted outcomes become
   * `unknown`, and one Harness-generated ISO timestamp applies to the batch.
   * @param blockName - block whose file receives the complete batch.
   * @param entries - model-authored experience fields supplied for persistence.
   * @param signal - operation cancellation.
   * @returns durable experiences with assigned ids and timestamps.
   */
  async record(blockName: string, entries: readonly NewExperienceMemory[], signal?: AbortSignal): Promise<ExperienceMemory[]> {
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
    return (await this.storeFor(blockName, signal)).append(durable, signal)
  }

  /**
   * Select lightweight candidates. Internal ranking chooses Top-K only; the
   * returned order is stable id order and does not express relevance.
   * @param blockName - block whose file supplies retrieval candidates.
   * @param request - query keywords and optional candidate limit.
   * @param signal - operation cancellation.
   * @returns candidate metadata without bodies or ranking scores.
   */
  async search(blockName: string, request: MemorySearchRequest, signal?: AbortSignal): Promise<MemorySearchCandidate[]> {
    const keywords = normalizeKeywords(request.keywords)
    const limit = request.limit ?? 10
    if (!Number.isSafeInteger(limit) || limit < 1) throw new MemoryError('memory search limit must be a positive safe integer', 'MEMORY_INVALID_LIMIT')
    const store = await this.storeFor(blockName, signal)
    const selected = await this.retriever.search({ keywords, limit, ...signal === undefined ? {} : { signal } }, store)
    const documents = new Map((await store.listDocuments(signal)).map(document => [document.id, document]))
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
   * @param blockName - block containing the requested id.
   * @param id - stable `memory-N` identity.
   * @param signal - operation cancellation.
   * @returns the complete experience, or `undefined` when absent.
   */
  async get(blockName: string, id: string, signal?: AbortSignal): Promise<ExperienceMemory | undefined> {
    return (await this.storeFor(blockName, signal)).get(id, signal)
  }

  /**
   * Read every complete experience from one block in durable file order.
   * @param blockName - block whose complete contents should be returned.
   * @param signal - operation cancellation.
   * @returns every experience stored in the block.
   */
  async list(blockName: string, signal?: AbortSignal): Promise<ExperienceMemory[]> {
    return (await this.storeFor(blockName, signal)).list(signal)
  }

  /**
   * Enumerate every block that currently owns a durable block file, without
   * loading the blocks whose stores have not been touched in this process.
   * A block exists whenever its `<block_name>_memory.md` file is present on
   * disk; the disk listing is authoritative because files may be written by
   * another process or session that never shared this service's store cache.
   * @param signal - operation cancellation.
   * @returns normalized block names owning files, in lexicographic order.
   */
  async listBlocks(signal?: AbortSignal): Promise<string[]> {
    signal?.throwIfAborted()
    let entries: string[]
    try {
      entries = await readdir(this.memoryDir)
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
    const blocks: string[] = []
    for (const entry of entries) {
      const blockName = BLOCK_FILE_PATTERN.exec(entry)?.[1]
      if (blockName === undefined) continue
      if (await pathKind(join(this.memoryDir, entry)) !== 'file') continue
      blocks.push(blockName)
    }
    return blocks.sort()
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

  private async storeFor(blockName: string, signal?: AbortSignal): Promise<MemoryStore> {
    signal?.throwIfAborted()
    const normalized = normalizeBlockName(blockName)
    if (normalized === 'global') await this.ensureGlobalMigration()
    signal?.throwIfAborted()
    let store = this.stores.get(normalized)
    if (store === undefined) {
      store = new MemoryStore(join(this.memoryDir, `${normalized}_memory.md`))
      this.stores.set(normalized, store)
    }
    return store
  }

  private ensureGlobalMigration(): Promise<void> {
    if (this.globalMigration === undefined) this.globalMigration = this.migrateLegacyGlobalFile()
    return this.globalMigration
  }

  private async migrateLegacyGlobalFile(): Promise<void> {
    if (this.legacyMemoryFile === undefined) return
    const target = join(this.memoryDir, 'global_memory.md')
    if (this.legacyMemoryFile === target) return
    const legacy = await pathKind(this.legacyMemoryFile)
    if (legacy === 'missing') return
    if (legacy !== 'file') throw new MemoryError(`legacy memory path is not a file: ${this.legacyMemoryFile}`, 'MEMORY_LEGACY_NOT_FILE')
    if (await pathKind(target) !== 'missing') {
      throw new MemoryError(`cannot migrate legacy memory because target already exists: ${target}`, 'MEMORY_MIGRATION_CONFLICT')
    }
    await mkdir(this.memoryDir, { recursive: true, mode: 0o700 })
    await rename(this.legacyMemoryFile, target)
  }
}

function normalizeBlockName(blockName: string): string {
  const normalized = blockName.trim().toLowerCase()
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/u.test(normalized)) {
    throw new MemoryError('memory block name must contain 1-64 ASCII letters, digits, underscores, or hyphens', 'MEMORY_INVALID_BLOCK_NAME')
  }
  return normalized
}

/** Block store file naming used both when creating a store and when listing blocks. */
const BLOCK_FILE_PATTERN = /^([a-z0-9][a-z0-9_-]{0,63})_memory\.md$/u

async function pathKind(path: string): Promise<'file' | 'other' | 'missing'> {
  try {
    return (await lstat(path)).isFile() ? 'file' : 'other'
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return 'missing'
    throw error
  }
}
