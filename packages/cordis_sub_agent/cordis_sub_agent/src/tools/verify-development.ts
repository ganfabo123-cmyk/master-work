import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'
import type { EngineeringVerificationService } from '../services/engineering-verification-service.js'

export interface VerifyDevelopmentToolOptions {
  repositoryPath: string
  typecheckCommand?: string
  buildCommand?: string
  testCommand?: string
  docSyncCommand?: string
  timeoutMs?: number
}

export function verifyDevelopmentTool(
  tasks: PluginMetadataTaskStore,
  verification: EngineeringVerificationService,
  options: VerifyDevelopmentToolOptions,
) {
  return defineTool({
    name: 'verify_development',
    description: 'Run the deterministic foreground Engineering Gate after Main Agent coding and documentation.',
    parameters: {
      task_id: { type: 'string', required: true, description: 'Development task id.' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args, exec) {
      const task = tasks.require(args.task_id)
      const result = await verification.verify({
        workspacePath: task.pluginRoot,
        repositoryPath: options.repositoryPath,
        pluginEntryPath: `${task.pluginRoot}/lib/index.js`,
        expectedPluginName: task.metadata.plugin_name,
        ...(options.typecheckCommand !== undefined ? { typecheckCommand: options.typecheckCommand } : {}),
        ...(options.buildCommand !== undefined ? { buildCommand: options.buildCommand } : {}),
        ...(options.testCommand !== undefined ? { testCommand: options.testCommand } : {}),
        ...(options.docSyncCommand !== undefined ? { docSyncCommand: options.docSyncCommand } : {}),
        ...(options.timeoutMs !== undefined ? { timeoutMs: options.timeoutMs } : {}),
      }, exec.signal)
      tasks.recordVerification(task.id, result)
      return {
        task_id: task.id,
        verification: JSON.parse(JSON.stringify(result)) as JsonValue,
      }
    },
  })
}
