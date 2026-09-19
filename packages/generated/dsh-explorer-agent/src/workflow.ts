/**
 * Explorer workflow: starts a read-only subagent over caller-supplied
 * directories, collects its structured submissions (`explore_paths` /
 * `explore_semantics`) keyed by question, and formats one answer string.
 */

import type { Agent } from '@deepseek-ai/dsh-agent'
import type {} from '@deepseek-ai/dsh-subagent' // side-effect type import: activates the `ctx.subagents` declaration merge
import type { Context } from '@deepseek-ai/cordis'
import { resolve } from 'node:path'
import { EXPLORER_ROLE, EXPLORER_TOOLS } from './roles.js'

/** One path the Explorer Agent found relevant to the question. */
export interface ExplorePath {
  path: string
  kind: 'directory' | 'file'
  summary: string
  reason: string
}

/** One piece of evidence backing a semantic finding. */
export interface ExploreEvidence {
  path: string
  kind: 'directory' | 'file'
  lines?: string
  reason: string
}

/** Result of the `explore_paths` submission channel. */
export interface ExplorePathsResult {
  question: string
  answer: string
  paths: ExplorePath[]
  risks: string[]
  gaps: string[]
}

/** One semantic finding backed by evidence. */
export interface ExploreFinding {
  title: string
  summary: string
  evidence: ExploreEvidence[]
}

/** Result of the `explore_semantics` submission channel. */
export interface ExploreSemanticsResult {
  question: string
  answer: string
  findings: ExploreFinding[]
  risks: string[]
  gaps: string[]
}

interface ExplorerResults {
  paths?: ExplorePathsResult
  semantics?: ExploreSemanticsResult
}

/** Options for one {@link ExplorerAgentWorkflow.run} call. */
export interface ExplorerWorkflowOptions {
  /** The spawning agent whose session scope and lineage the child inherits. */
  parent: Agent
  /** Cancellation signal from the spawning tool execution. */
  signal: AbortSignal
  /** Optional preferred subagent provider name. */
  provider?: string
}

/**
 * Explorer capability consumed by the model-facing tools and other plugins.
 * The workflow and its public service deliberately share this small contract.
 */
export interface ExplorerAgentCapability {
  recordPaths(result: ExplorePathsResult): void
  recordSemantics(result: ExploreSemanticsResult): void
  run(directories: readonly string[], question: string, options: ExplorerWorkflowOptions): Promise<string>
}

/**
 * Normalize a caller-supplied directory list: drop blank entries, resolve every
 * remaining entry against the current working directory, and deduplicate.
 * @param directories - raw directory entries from the tool arguments.
 * @returns absolute, deduplicated, non-empty directories.
 */
export function normalizeDirectories(directories: readonly string[]): string[] {
  const normalized = [
    ...new Set(
      directories
        .map(directory => directory.trim())
        .filter(directory => directory.length > 0)
        .map(directory => resolve(directory)),
    ),
  ]
  if (normalized.length === 0) {
    throw new Error('explorer requires at least one non-empty directory.')
  }
  return normalized
}

/** Runs the read-only Explorer Agent over caller-supplied directories and collects its structured result tools. */
export class ExplorerAgentWorkflow {
  private readonly results = new Map<string, ExplorerResults>()

  constructor(private readonly ctx: Context) {}

  recordPaths(result: ExplorePathsResult): void {
    const current = this.results.get(result.question) ?? {}
    this.results.set(result.question, { ...current, paths: result })
  }

  recordSemantics(result: ExploreSemanticsResult): void {
    const current = this.results.get(result.question) ?? {}
    this.results.set(result.question, { ...current, semantics: result })
  }

  /**
   * Explore the given directories to answer a question and return the
   * formatted evidence-backed answer.
   * @param directories - directory list scoping the exploration.
   * @param question - the exploration question, also the submission match key.
   * @param options - parent agent, cancellation signal, optional provider.
   * @returns the formatted answer covering the submitted `explore_paths` and/or `explore_semantics` results.
   */
  async run(directories: readonly string[], question: string, options: ExplorerWorkflowOptions): Promise<string> {
    const normalized = normalizeDirectories(directories)
    const run = await this.ctx.subagents.start(this.resolveProvider(options.provider), {
      label: 'explorer',
      persona: EXPLORER_ROLE,
      prompt: [{
        type: 'text',
        text: [
          `Exploration directories:\n${normalized.join('\n')}`,
          `Question from the caller: ${question}`,
          `Use this exact question value when calling explore_paths or explore_semantics: ${question}`,
          'Explore only within the listed directories. Select explore_paths, explore_semantics, or both.',
          'Do not modify files, run commands, build, or test.',
        ].join('\n'),
      }],
      parent: options.parent,
      signal: options.signal,
      toolFilter: { allow: EXPLORER_TOOLS },
    })

    try {
      const result = await run.result
      if (result.stopReason !== 'completed') throw new Error(`Explorer Agent stopped with reason ${result.stopReason}`)
      const collected = this.results.get(question)
      if (collected === undefined || (collected.paths === undefined && collected.semantics === undefined)) {
        throw new Error('Explorer Agent completed without submitting an exploration result.')
      }
      return this.format(collected)
    } finally {
      this.results.delete(question)
      await run.dispose()
    }
  }

  private format(results: ExplorerResults): string {
    const sections: string[] = []
    if (results.paths !== undefined) sections.push(`# Explored paths\n\n${JSON.stringify(results.paths, null, 2)}`)
    if (results.semantics !== undefined) sections.push(`# Semantic findings\n\n${JSON.stringify(results.semantics, null, 2)}`)
    return sections.join('\n\n')
  }

  private resolveProvider(preferred?: string): string {
    for (const name of [preferred, 'spawn', 'fork'].filter((value): value is string => value !== undefined)) {
      if (this.ctx.subagents.getProvider(name)?.capabilities.toolFilter) return name
    }
    throw new Error('explorer requires a subagent provider with toolFilter capability.')
  }
}
