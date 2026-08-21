import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'

export function getTaskStatusTool(tasks: PluginMetadataTaskStore) {
  return defineTool({
    name: 'get_development_task',
    description: 'Return the in-process V3 metadata task facts and evidence for a generated plugin.',
    parameters: {
      task_id: { type: 'string', required: true, description: 'V3 task id returned by submit_plugin_metadata.' },
    },
    output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }] },
    async execute(args) {
      const record = tasks.require(args.task_id)
      return JSON.parse(JSON.stringify({
        task_id: record.id,
        plugin_metadata: record.metadata,
        plugin_root: record.pluginRoot,
        read_plan: record.readPlan,
        evidence: record.evidence,
        documentation: record.documentation,
        verification: record.verification,
        acceptance_id: record.acceptanceId,
        error: record.error,
        discarded_at: record.discardedAt,
      })) as Record<string, JsonValue>
    },
  })
}
