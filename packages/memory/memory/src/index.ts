/**
 * Keyword experience-memory plugin and its model-facing tools.
 *
 * @module @deepseek-ai/dsh-memory
 */

import { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type {} from '@deepseek-ai/dsh-system-prompt'
import { resolveConfig, type Config } from './config.ts'
import { EXPERIENCE_BODY_TEMPLATE, formatExperience, formatSearchCandidates } from './model.ts'
import { MemoryError, MemoryService, type MemoryRuntime } from './service.ts'

declare module '@deepseek-ai/cordis' {
  interface Context {
    memory: MemoryService
  }
}

export { Config, resolveConfig } from './config.ts'
export { MEMORY_ID_PREFIX, normalizeKeywords } from './memory.ts'
export type { ExperienceMemory, MemoryOutcome, MemorySearchDocument, NewExperienceMemory } from './memory.ts'
export { KeywordRetriever } from './retrieval/keyword_retriever.ts'
export type { InternalRetrievalResult, MemoryRetriever, MemorySearchQuery } from './retrieval/retriever.ts'
export { MemoryError, MemoryService } from './service.ts'
export type { MemorySearchCandidate, MemorySearchRequest } from './service.ts'
export { parseMemoryMarkdown, serializeMemoryMarkdown } from './store/markdown.ts'
export { MemoryStore } from './store/memory_store.ts'
export type { MemorySearchSource } from './store/memory_store.ts'

/** Cordis plugin name. */
export const name = 'memory'
/** Capability services required by the model-facing consumer. */
export const inject = ['tools', 'systemPrompt']

const SYSTEM_PROMPT = 'Use experience memory when a past success or failure may help the current task. Generate several specific keywords, call memory_search, judge candidates from their title, keywords, matched keywords, outcome, and current context, then call memory_get only for candidates worth reading. Search results are candidates only: presentation order does not guarantee relevance or correctness. Treat loaded memories as past evidence that may be stale, not as truth. Record only reusable lessons with memory_record; do not record routine errors or complete session history.'

const TEXT_OUTPUT = {
  schema: { type: 'string' as const },
  render: (_args: unknown, value: string) => [{ type: 'text' as const, text: value }],
}

/** Mount the memory service and the three model-facing tools. */
export function apply(ctx: Context, config: Config): void {
  const runtime: MemoryRuntime = { memoryFile: resolveConfig(config).memoryFile }
  ctx.plugin(MemoryService, runtime)
  ctx.systemPrompt.section({ name: 'tool:memory', order: 114, text: SYSTEM_PROMPT })

  ctx.tools.register(defineTool({
    name: 'memory_search',
    description: 'Find lightweight candidate experiences by several exact keywords. Result order is stable and does not express relevance.',
    parameters: {
      keywords: { type: 'array', required: true, items: { type: 'string' }, description: 'Specific technology, system, problem, environment, and component terms.' },
      limit: { type: 'number', description: 'Maximum candidate count. Defaults to 10.' },
    },
    output: TEXT_OUTPUT,
    execute: async (args, exec) => formatSearchCandidates(await resolveMemory(ctx).search({
      keywords: args.keywords,
      ...args.limit === undefined ? {} : { limit: args.limit },
    }, exec.signal)),
    presentCall: ({ keywords }) => ({ card: 'generic' as const, kind: 'read' as const, title: 'Search experience memory', rawInput: `${String(keywords.length)} keyword(s)` }),
  }))

  ctx.tools.register(defineTool({
    name: 'memory_get',
    description: 'Read one complete past experience by its stable memory-N id.',
    parameters: { id: { type: 'string', required: true, description: 'The candidate experience id.' } },
    output: TEXT_OUTPUT,
    execute: async (args, exec) => {
      const memory = await resolveMemory(ctx).get(args.id, exec.signal)
      return memory === undefined ? `No memory experience with id "${args.id}".` : formatExperience(memory)
    },
    presentCall: ({ id }) => ({ card: 'generic' as const, kind: 'read' as const, title: 'Read experience memory', rawInput: id }),
  }))

  ctx.tools.register(defineTool({
    name: 'memory_record',
    description: 'Append one or more reusable experiences directly to memory.md using the supplied tool-call fields.',
    parameters: {
      entries: {
        type: 'array', required: true, description: 'Reusable experiences from the current task.',
        items: {
          type: 'object', additionalProperties: false,
          properties: {
            title: { type: 'string', required: true, description: 'Short, specific experience title.' },
            keywords: { type: 'array', required: true, items: { type: 'string' }, description: 'Stable recall terms covering relevant semantic dimensions.' },
            outcome: { type: 'string', enum: ['success', 'failure', 'mixed', 'unknown'], description: 'Observed result; omitted becomes unknown.' },
            body: { type: 'string', required: true, description: `Markdown experience body. Level-one headings are forbidden. Recommended template:\n${EXPERIENCE_BODY_TEMPLATE}` },
          },
        },
      },
    },
    output: TEXT_OUTPUT,
    execute: async (args, exec) => {
      if (args.entries.length === 0) return 'memory_record rejected: no entries supplied.'
      try {
        const stored = await resolveMemory(ctx).record(args.entries.map(entry => ({
          title: entry.title,
          keywords: entry.keywords,
          ...entry.outcome === undefined ? {} : { outcome: entry.outcome },
          body: entry.body,
        })), exec.signal)
        return `Stored ${String(stored.length)} experience(s): ${stored.map(memory => memory.id).join(', ')}`
      } catch (error: unknown) {
        if (error instanceof MemoryError) return `Memory store failed: ${error.message}`
        throw error
      }
    },
    presentCall: ({ entries }) => ({ card: 'generic' as const, kind: 'edit' as const, title: `Record ${String(entries.length)} experience(s)`, rawInput: String(entries.length) }),
  }))
}

function resolveMemory(ctx: Context): MemoryService {
  const memory = ctx.get('memory')
  if (memory === undefined) throw new MemoryError('dsh-memory failed to mount its service', 'MEMORY_NO_SERVICE')
  return memory
}
