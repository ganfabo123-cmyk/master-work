import { describe, expect, it } from 'vitest'
import { KeywordRetriever, normalizeKeywords, type MemorySearchSource } from '@deepseek-ai/dsh-memory'

const source: MemorySearchSource = {
  async listDocuments() {
    return [
      { id: 'memory-1', title: 'One', keywords: ['encoding'], outcome: 'unknown', position: 0 },
      { id: 'memory-2', title: 'Two', keywords: ['typescript', 'encoding', 'windows'], outcome: 'success', position: 1 },
      { id: 'memory-3', title: 'Three', keywords: ['typescript', 'encoding'], outcome: 'mixed', position: 2 },
      { id: 'memory-4', title: 'Four', keywords: ['python'], outcome: 'failure', position: 3 },
    ]
  },
}

describe('KeywordRetriever public contract', () => {
  it('normalizes case, whitespace, blanks, and duplicates canonically', () => {
    expect(normalizeKeywords([' TypeScript ', 'TYPESCRIPT', 'typescript', ' '])).toEqual(['typescript'])
  })

  it('returns no candidates for a zero-match query', async () => {
    await expect(new KeywordRetriever().search({ keywords: ['rust'], limit: 10 }, source)).resolves.toEqual([])
  })

  it('uses ranking only for Top-K selection and presents selected ids stably', async () => {
    const results = await new KeywordRetriever().search({ keywords: [' TypeScript ', 'ENCODING', 'WINDOWS'], limit: 3 }, source)
    expect(results.map(result => result.id)).toEqual(['memory-1', 'memory-2', 'memory-3'])
    expect(results.find(result => result.id === 'memory-2')?.matchedKeywords).toEqual(['typescript', 'encoding', 'windows'])
    expect(JSON.stringify(results)).not.toMatch(/similarity/iu)
  })

  it('applies limit after exact matching', async () => {
    const results = await new KeywordRetriever().search({ keywords: ['typescript', 'encoding'], limit: 2 }, source)
    expect(results.map(result => result.id)).toEqual(['memory-2', 'memory-3'])
  })
})

