/**
 * Deterministic exact-keyword retrieval for the V1 memory implementation.
 *
 * @module @deepseek-ai/dsh-memory/retrieval/keyword-retriever
 */

import { memoryIdNumber, normalizeKeywords } from '../memory.ts'
import type { MemoryRetriever, MemorySearchQuery, InternalRetrievalResult } from './retriever.ts'
import type { MemorySearchSource } from '../store/memory_store.ts'

/** Exact-match retriever whose ranking signal selects Top-K but does not order presentation. */
export class KeywordRetriever implements MemoryRetriever {
  async search(query: MemorySearchQuery, source: MemorySearchSource): Promise<InternalRetrievalResult[]> {
    const queryKeywords = new Set(normalizeKeywords(query.keywords))
    if (queryKeywords.size === 0 || query.limit <= 0) return []
    const candidates = (await source.listDocuments(query.signal)).flatMap((document) => {
      const matchedKeywords = normalizeKeywords(document.keywords).filter(keyword => queryKeywords.has(keyword))
      return matchedKeywords.length === 0 ? [] : [{
        id: document.id,
        rankingScore: matchedKeywords.length,
        matchedKeywords,
        position: document.position,
      }]
    })
    const selected = candidates
      .sort((left, right) => right.rankingScore - left.rankingScore || left.position - right.position)
      .slice(0, query.limit)
    return selected
      .sort((left, right) => memoryIdNumber(left.id) - memoryIdNumber(right.id))
      .map(({ id, rankingScore, matchedKeywords }) => ({ id, rankingScore, matchedKeywords }))
  }
}
