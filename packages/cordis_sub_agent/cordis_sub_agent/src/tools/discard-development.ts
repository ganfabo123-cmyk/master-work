import { defineTool } from '@deepseek-ai/dsh-tools'
import type { AcceptanceService } from '../services/acceptance-service.js'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'

export function discardDevelopmentTool(
  tasks: PluginMetadataTaskStore,
  acceptance: AcceptanceService,
) {
  return defineTool({
    name: 'discard_development',
    description: 'Explicitly stop the V3 task-owned acceptance runtime and remove its task-owned generated plugin directory.',
    parameters: { task_id: { type: 'string', required: true, description: 'V3 task id returned by submit_plugin_metadata.' } },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args, exec) {
      const task = tasks.require(args.task_id)
      if (task.acceptanceId !== undefined) {
        try {
          await acceptance.stop(task.acceptanceId, 'stopped')
        } finally {
          tasks.clearAcceptanceId(task.id)
        }
      }
      const discarded = await tasks.discard(task.id)
      void exec.signal
      return { task_id: discarded.id, status: 'discarded', plugin_root: discarded.pluginRoot }
    },
  })
}
