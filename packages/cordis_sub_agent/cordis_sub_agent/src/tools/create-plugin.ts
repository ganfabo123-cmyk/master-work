import { defineTool } from '@deepseek-ai/dsh-tools'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'
import type { ExplorerAgentService } from '../services/explorer-agent.js'

/** Register the requirement-metadata Explorer Agent wrapper. */
export function createPluginTool(
  tasks: PluginMetadataTaskStore,
  explorer: ExplorerAgentService,
  repositoryPath: string,
) {
  return defineTool({
    name: 'prepare_plugin_reading',
    description: [
      'Generate a repository reading plan from a submitted plugin metadata task.',
      '',
      'The task id must come from submit_plugin_metadata in this DSH process.',
      'The tool loads that metadata, sends it to the read-only Explorer Agent as the user requirement, and returns its readable exploration result.',
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
          read_plan: { type: 'string', required: true },
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
      const exploration = await explorer.run([repositoryPath], [
        'User-submitted plugin requirement metadata:',
        JSON.stringify(task.metadata, null, 2),
        '',
        `Task id: ${task.id}`,
      ].join('\n'), { parent, signal: exec.signal })
      tasks.recordReadPlan(task.id, exploration)
      return {
        task_id: task.id,
        plugin_root: task.pluginRoot,
        read_plan: exploration,
        next_step: 'Use this exploration result to inspect the repository before deciding the next development action.',
      }
    },
  })
}
