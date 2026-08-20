import type { Agent } from '@deepseek-ai/dsh-agent'
import type { Context } from '@deepseek-ai/cordis'

import type { PluginSpec } from '../models/plugin-spec.js'
import {
  CODING_ROLE,
  CODING_TOOLS,
  READER_ROLE,
  READER_TOOLS,
} from './agent-roles.js'

export interface DevelopmentWorkflowInput {
  pluginSpec: PluginSpec
  workspacePath: string
}

export interface DevelopmentWorkflowOptions {
  parent: Agent
  signal: AbortSignal
  preferredProvider?: string
}

export interface DevelopmentWorkflowResult {
  readPlan: unknown
  codingAgentId: string
}

export class DevelopmentWorkflow {
  constructor(private readonly ctx: Context) {}

  getContext(): Context {
    return this.ctx
  }

  async run(input: DevelopmentWorkflowInput, options: DevelopmentWorkflowOptions): Promise<DevelopmentWorkflowResult> {
    const provider = this.resolveDevelopmentProvider(options.preferredProvider)
    const pluginSpecJson = JSON.stringify(input.pluginSpec, null, 2)
    const readerRun = await this.ctx.subagents.start(provider, {
      prompt: [{ type: 'text', text: [
        READER_ROLE,
        '',
        'Confirmed PluginSpec:',
        pluginSpecJson,
        '',
        `Target worktree: ${input.workspacePath}`,
      ].join('\n') }],
      parent: options.parent,
      signal: options.signal,
      toolFilter: { allow: READER_TOOLS },
    })

    let readerResult: Awaited<typeof readerRun.result>
    try {
      readerResult = await readerRun.result
      this.assertCompleted('Reader / Scout Agent', readerResult.stopReason)
    } finally {
      await readerRun.dispose()
    }

    const coding = await this.ctx.subagents.startContinuable({
      provider,
      label: `Coding plugin ${input.pluginSpec.name}`,
      request: {
        prompt: [{ type: 'text', text: [
          CODING_ROLE,
          '',
          'Confirmed PluginSpec:',
          pluginSpecJson,
          '',
          'Reader / Scout Read Plan:',
          JSON.stringify(readerResult.output, null, 2),
          '',
          `Assigned worktree (and cwd): ${input.workspacePath}`,
          'All writes must stay inside this worktree.',
        ].join('\n') }],
        parent: options.parent,
        toolFilter: { allow: CODING_TOOLS },
      },
      signal: options.signal,
    })

    return { readPlan: readerResult.output, codingAgentId: String(coding.childId) }
  }

  private assertCompleted(agentName: string, stopReason: string): void {
    if (stopReason !== 'completed') throw new Error(`${agentName} stopped with reason: ${stopReason}`)
  }

  private resolveDevelopmentProvider(preferred?: string): string {
    const candidates = [preferred, 'spawn', 'fork'].filter((name): name is string => name !== undefined)
    for (const name of [...new Set(candidates)]) {
      const provider = this.ctx.subagents.getProvider(name)
      if (provider !== undefined && provider.capabilities.toolFilter) return name
    }
    throw new Error('Development workflow requires a subagent provider with toolFilter capability.')
  }
}
