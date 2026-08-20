import { defineTool } from '@deepseek-ai/dsh-tools'
import type { Agent } from '@deepseek-ai/dsh-agent'
import type { PluginDevelopmentService } from '../services/plugin-development-service.js'

export function resumeDevelopmentTool(service: PluginDevelopmentService) {
  return defineTool({
    name: 'resume_development',
    description: 'Send evidence to the same continuable Coding Agent and resume a development task.',
    parameters: {
      task_id: { type: 'string', required: true, description: 'Development task id.' },
      evidence: { type: 'string', required: true, description: 'Failure evidence or next work instruction.' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args, exec) {
      const parent = exec.agent as Agent | undefined
      if (parent === undefined) throw new Error('resume_development requires a calling agent.')
      const task = await service.followup(args.task_id, parent, args.evidence, exec.signal)
      return {
        task_id: task.id,
        status: task.status,
        ...(task.codingAgentId !== undefined ? { coding_agent_id: task.codingAgentId } : {}),
        workspace_path: task.workspacePath,
      }
    },
  })
}
