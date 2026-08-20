import { defineTool } from '@deepseek-ai/dsh-tools'
import type { PluginDevelopmentService } from '../services/plugin-development-service.js'

export function discardDevelopmentTool(service: PluginDevelopmentService) {
  return defineTool({
    name: 'discard_development',
    description: 'Explicitly remove a task-owned worktree and branch for a development task.',
    parameters: { task_id: { type: 'string', required: true, description: 'Development task id.' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args, exec) {
      const task = await service.discard(args.task_id, exec.signal)
      return { task_id: task.id, status: task.status, workspace_path: task.workspacePath }
    },
  })
}
