import { defineTool } from '@deepseek-ai/dsh-tools'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'
import type { PluginMetadataReadWorkflow } from '../workflow/plugin-metadata-read-workflow.js'

/** Register the requirement-metadata Read Agent wrapper. */
export function createPluginTool(
  tasks: PluginMetadataTaskStore,
  reader: PluginMetadataReadWorkflow,
) {
  return defineTool({
    name: 'prepare_plugin_reading',
    description: [
      'Generate a repository reading plan from a submitted plugin metadata task.',
      '',
      'The task id must come from submit_plugin_metadata in this DSH process.',
      'The tool loads that metadata, sends it to the read-only Reader Agent as the user requirement, and returns the Reader Agent\'s JSON reading plan.',
      'It does not create a workspace, write files, or start implementation.',
    ].join('\n'),
    parameters: {
      task_id: { type: 'string', required: true, description: 'Task id returned by submit_plugin_metadata.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          task_id: { type: 'string', required: true },
          plugin_root: { type: 'string', required: true },
          read_plan: { type: 'object', additionalProperties: true, required: true },
          next_step: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: JSON.stringify(value, null, 2),
      }],
    },
    async execute(args, exec) {
      const parent = exec.agent
      if (parent === undefined) throw new Error('prepare_plugin_reading requires a calling Main Agent.')
      exec.signal.throwIfAborted()
      const task = tasks.require(args.task_id)
      const readPlan = await reader.run({
        taskId: task.id,
        metadata: task.metadata,
      }, { parent, signal: exec.signal })
      tasks.recordReadPlan(task.id, readPlan)
      return {
        task_id: task.id,
        plugin_root: task.pluginRoot,
        read_plan: JSON.parse(JSON.stringify(readPlan)),
        next_step: 'Use this reading plan to inspect the repository before deciding the next development action.',
      }
    },
  })
}
