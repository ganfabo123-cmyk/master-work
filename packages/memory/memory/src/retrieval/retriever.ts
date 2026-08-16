/**
 * Retrieval interfaces separate candidate selection from durable memory storage.
 *
 * @module @deepseek-ai/dsh-memory/retrieval/retriever
 */

import type { MemorySearchSource } from '../store/memory_store.ts'

/** A normalized keyword query and its maximum candidate count. */
export interface MemorySearchQuery {
  readonly keywords: readonly string[]
  readonly limit: number
  readonly signal?: AbortSignal
}

/** Internal candidate data; ranking score never crosses the model-facing API. */
export interface InternalRetrievalResult {
  readonly id: string
  readonly rankingScore: number
  readonly matchedKeywords: readonly string[]
}

/** Pluggable candidate-selection strategy. */
export interface MemoryRetriever {
  /** Select candidate ids from a memory search source. */
  search(query: MemorySearchQuery, source: MemorySearchSource): Promise<InternalRetrievalResult[]>
}
