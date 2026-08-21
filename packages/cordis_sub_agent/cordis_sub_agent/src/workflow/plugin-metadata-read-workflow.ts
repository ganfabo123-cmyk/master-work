import type { Agent } from '@deepseek-ai/dsh-agent'
import type { Context } from '@deepseek-ai/cordis'
import type { ReadPlan } from '../models/read-plan.js'
import { ReaderConclusionStore } from '../tools/reader-conclusion.js'
import { READER_ROLE, READER_TOOLS } from './agent-roles.js'

export interface PluginMetadataReadWorkflowInput {
  taskId: string
  metadata: unknown
}

export interface PluginMetadataReadWorkflowOptions {
  parent: Agent
  signal: AbortSignal
}

/** Runs the existing read-only Reader Agent from submitted requirement metadata. */
export class PluginMetadataReadWorkflow {
  constructor(
    private readonly ctx: Context,
    private readonly conclusions: ReaderConclusionStore,
    private readonly repositoryPath: string,
  ) {}

  /** Send the stored requirement decomposition to the Reader Agent and return its reading plan. */
  async run(
    input: PluginMetadataReadWorkflowInput,
    options: PluginMetadataReadWorkflowOptions,
  ): Promise<ReadPlan> {
    const run = await this.ctx.subagents.start(this.resolveProvider(), {
      persona: READER_ROLE,
      prompt: [{
        type: 'text',
        text: [
          'User-submitted plugin requirement metadata:',
          JSON.stringify(input.metadata, null, 2),
          '',
          `Repository root to investigate: ${this.repositoryPath}`,
          `Use task_id=${input.taskId} when calling reader_conclusion.`,
          'Treat the metadata as the user requirement. Do not create a workspace, write files, or run build/test.',
        ].join('\n'),
      }],
      parent: options.parent,
      signal: options.signal,
      toolFilter: { allow: READER_TOOLS },
    })
    try {
      const result = await run.result
      if (result.stopReason !== 'completed') throw new Error(`Reader Agent stopped with reason ${result.stopReason}`)
      const plan = this.conclusions.take(input.taskId)
      if (plan === undefined) throw new Error('Reader Agent completed without calling reader_conclusion.')
      return plan
    } finally {
      await run.dispose()
    }
  }

  private resolveProvider(): string {
    for (const name of ['spawn', 'fork']) {
      if (this.ctx.subagents.getProvider(name)?.capabilities.toolFilter) return name
    }
    throw new Error('Plugin metadata reading requires a subagent provider with toolFilter capability.')
  }
}
