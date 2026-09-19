/**
 * @deepseek-ai/dsh-explorer-agent — a reusable read-only directory Explorer
 * Agent. The caller passes one or more directories and a natural-language
 * question; the plugin starts an Explorer subagent scoped to those directories
 * (read/glob/grep plus the explore_paths / explore_semantics submission
 * channels) and returns a concise, evidence-backed answer.
 * @module @deepseek-ai/dsh-explorer-agent
 */

import { Context, Service } from '@deepseek-ai/cordis'
import { explorerTool, explorePathsTool, exploreSemanticsTool } from './tools.js'
import {
  type ExplorePathsResult,
  type ExploreSemanticsResult,
  ExplorerAgentWorkflow,
  type ExplorerWorkflowOptions,
} from './workflow.js'

declare module '@deepseek-ai/cordis' {
  interface Context {
    /** Shared read-only Explorer workflow supplied by dsh-explorer-agent. */
    explorerAgent: ExplorerAgentService
  }
}

/**
 * Cross-plugin Explorer capability. Consumers provide their own directory
 * scope and question; this plugin remains the single owner of the Explorer
 * subagent lifecycle and its structured result channels.
 */
export class ExplorerAgentService extends Service {
  static inject = ['subagents']

  private readonly workflow: ExplorerAgentWorkflow

  constructor(ctx: Context) {
    super(ctx, 'explorerAgent')
    this.workflow = new ExplorerAgentWorkflow(ctx)
  }

  recordPaths(result: ExplorePathsResult): void {
    this.workflow.recordPaths(result)
  }

  recordSemantics(result: ExploreSemanticsResult): void {
    this.workflow.recordSemantics(result)
  }

  run(directories: readonly string[], question: string, options: ExplorerWorkflowOptions): Promise<string> {
    return this.workflow.run(directories, question, options)
  }
}

export const name = 'explorer-agent'
export const inject = ['subagents', 'tools'] as const

export function apply(ctx: Context): void {
  // `ctx.plugin()` creates a nested injection boundary. Keep the service
  // instance here instead of reading ctx.explorerAgent back through the
  // parent plugin context, which has not declared that service as an inject.
  const explorer = new ExplorerAgentService(ctx)

  ctx.effect(() => {
    const disposers = [
      ctx.tools.register(explorePathsTool(explorer)),
      ctx.tools.register(exploreSemanticsTool(explorer)),
      ctx.tools.register(explorerTool(explorer)),
    ]
    return () => {
      for (const dispose of disposers) {
        dispose()
      }
    }
  }, 'explorer-agent tools')
}
