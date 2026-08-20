import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type { DevelopmentTaskStore } from '../services/development-task-store.js'

export function getTaskStatusTool(tasks: DevelopmentTaskStore) {
  return defineTool({
    name: 'get_development_task',
    description: 'Return the persisted state and evidence pointers for a plugin development task.',
    parameters: {
      task_id: { type: 'string', required: true, description: 'Development task id.' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args) {
      const record = tasks.require(args.task_id)
      return JSON.parse(JSON.stringify({
        task_id: record.task.id,
        status: record.task.status,
        workspace: record.task.workspace,
        workspace_path: record.task.workspacePath,
        coding_agent_id: record.task.codingAgentId,
        read_plan: record.task.readPlan,
        verification: record.verification,
        acceptance_id: record.acceptanceId,
        error: record.task.error,
      })) as Record<string, JsonValue>
    },
  })
}
