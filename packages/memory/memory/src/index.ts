/**
 * Keyword experience-memory plugin, cwd-scoped fact memory, and their model-facing tools.
 *
 * Experience memory keeps reusable successes and failures as few-shot records
 * retrieved through `memory_search`/`memory_get`/`memory_record`. Fact memory
 * keeps stable per-working-directory facts (for example the user's name) that
 * are injected automatically into the model context on every assembly.
 *
 * @module @deepseek-ai/dsh-memory
 */

import { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { PromptAssembly } from '@deepseek-ai/dsh-system-prompt'
import { resolveConfig, type Config } from './config.ts'
import { normalizeFactTitle } from './fact.ts'
import { EXPERIENCE_BODY_TEMPLATE, formatExperience, formatFactSection, formatSearchCandidates } from './model.ts'
import { MemoryError, MemoryService, type MemoryRuntime } from './service.ts'

declare module '@deepseek-ai/cordis' {
  interface Context {
    memory: MemoryService
  }
}

export { Config, resolveConfig } from './config.ts'
export { factFileFor, factFileNameFor, normalizeFactTitle, parseFactsJson, serializeFactsJson } from './fact.ts'
export type { FactMemory } from './fact.ts'
export { MEMORY_ID_PREFIX, normalizeKeywords } from './memory.ts'
export type { ExperienceMemory, MemoryOutcome, MemorySearchDocument, NewExperienceMemory } from './memory.ts'
export { formatFactSection } from './model.ts'
export { KeywordRetriever } from './retrieval/keyword_retriever.ts'
export type { InternalRetrievalResult, MemoryRetriever, MemorySearchQuery } from './retrieval/retriever.ts'
export { MemoryError, MemoryService } from './service.ts'
export type { MemoryRuntime, MemorySearchCandidate, MemorySearchRequest } from './service.ts'
export { parseMemoryMarkdown, serializeMemoryMarkdown } from './store/markdown.ts'
export { FactStore } from './store/fact_store.ts'
export type { FactSource } from './store/fact_store.ts'
export { MemoryStore } from './store/memory_store.ts'
export type { MemorySearchSource } from './store/memory_store.ts'

/** Cordis plugin name. */
export const name = 'memory'
/** Capability services required by the model-facing consumer. */
export const inject = ['tools', 'systemPrompt']

const SYSTEM_PROMPT = 'Use experience memory when a past success or failure may help the current task. Generate several specific keywords, call memory_search, judge candidates from their title, keywords, matched keywords, outcome, and current context, then call memory_get only for candidates worth reading. Search results are candidates only: presentation order does not guarantee relevance or correctness. Treat loaded memories as past evidence that may be stale, not as truth. Record only reusable lessons with memory_record; do not record routine errors or complete session history.'

const FACT_SYSTEM_PROMPT = 'Remembered facts for this working directory are injected into your context on every turn. Treat them as known, current facts about the user or this workspace unless the user contradicts them. When the user explicitly asks you to remember something, or states a stable personal or project fact (such as their name, preferences, or environment), call fact_remember to save it for this working directory. When the user says a remembered fact is wrong or asks you to forget it, call fact_forget.'

const TEXT_OUTPUT = {
  schema: { type: 'string' as const },
  render: (_args: unknown, value: string) => [{ type: 'text' as const, text: value }],
}

/** Mount the memory service, the fact injection, and all model-facing tools. */
export function apply(ctx: Context, config: Config): void {
  const resolved = resolveConfig(config)
  const runtime: MemoryRuntime = {
    memoryFile: resolved.memoryFile,
    factsDir: resolved.factsDir,
    maxFacts: resolved.maxFacts,
  }
  ctx.plugin(MemoryService, runtime)
  ctx.systemPrompt.section({ name: 'tool:memory', order: 114, text: SYSTEM_PROMPT })
  ctx.systemPrompt.section({ name: 'memory:facts', order: 115, text: FACT_SYSTEM_PROMPT })
  ctx.on('system-prompt/assemble', async (assembly, _context, next): Promise<PromptAssembly> => {
    const memory = resolveMemory(ctx)
    const cwd = assembly.variables.cwd
    const limits = memory.factBudget()
    if (cwd === undefined || limits <= 0) return next()
    // Load facts before delegating so other listeners see a complete picture.
    const facts = (await memory.facts(cwd, _context.signal)).slice(0, limits)
    const rendered = formatFactSection(facts)
    const assembled = await next()
    if (rendered.length === 0) return assembled
    return {
      ...assembled,
      sections: [...assembled.sections, {
        name: 'memory:facts:injected',
        text: rendered,
      }],
    }
  })

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

  ctx.tools.register(defineTool({
    name: 'fact_remember',
    description: 'Save one stable fact for the current working directory. Write the fact title as a markdown heading without numbering, and write the concrete fact body below it. The fact is injected into your context on every future turn in this cwd until forgotten. Use it when the user asks you to remember something or states a stable personal or project fact.',
    parameters: {
      title: { type: 'string', required: true, description: 'Markdown heading text without numbering, e.g. "严格遵守当前指令范围"; trimmed and lowercased.' },
      body: { type: 'string', required: true, description: 'Concrete fact body for that title, written below the heading.' },
    },
    output: TEXT_OUTPUT,
    execute: async (args, exec) => {
      const cwd = exec.agent?.session.header.cwd
      if (cwd === undefined) throw new MemoryError('fact_remember requires a session working directory', 'FACT_NO_CWD')
      try {
        const fact = await resolveMemory(ctx).rememberFact(cwd, { title: args.title, body: args.body }, exec.signal)
        return `Remembered: ${fact.title}`
      } catch (error: unknown) {
        if (error instanceof MemoryError) return `Fact store failed: ${error.message}`
        throw error
      }
    },
    presentCall: ({ title, body }) => ({ card: 'generic' as const, kind: 'edit' as const, title: `Remember fact "${title}"`, rawInput: body }),
  }))

  ctx.tools.register(defineTool({
    name: 'fact_forget',
    description: 'Remove one saved fact for the current working directory by its title. Use it when the user says a remembered fact is wrong or asks you to forget it.',
    parameters: { title: { type: 'string', required: true, description: 'The fact title to forget, e.g. "user name"; trimmed and lowercased.' } },
    output: TEXT_OUTPUT,
    execute: async (args, exec) => {
      const cwd = exec.agent?.session.header.cwd
      if (cwd === undefined) throw new MemoryError('fact_forget requires a session working directory', 'FACT_NO_CWD')
      const title = normalizeFactTitle(args.title)
      const removed = await resolveMemory(ctx).forgetFact(cwd, title, exec.signal)
      return removed ? `Forgot: ${title}` : `No saved fact with title "${title}".`
    },
    presentCall: ({ title }) => ({ card: 'generic' as const, kind: 'edit' as const, title: `Forget fact "${title}"`, rawInput: '' }),
  }))
}

function resolveMemory(ctx: Context): MemoryService {
  const memory = ctx.get('memory')
  if (memory === undefined) throw new MemoryError('dsh-memory failed to mount its service', 'MEMORY_NO_SERVICE')
  return memory
}
