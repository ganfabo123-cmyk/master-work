import { defineTool } from '@deepseek-ai/dsh-tools'
import type { Agent } from '@deepseek-ai/dsh-agent'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'
import type { DocumentationWorkflow } from '../workflow/documentation-workflow.js'

/** Register the Documentation Agent wrapper for an in-memory metadata task. */
export function documentDevelopmentTool(
  tasks: PluginMetadataTaskStore,
  documentation: DocumentationWorkflow,
  repositoryPath: string,
) {
  return defineTool({
    name: 'document_development',
    description: 'Run the Documentation Agent for the plugin directory stored by submit_plugin_metadata.',
    parameters: {
      task_id: { type: 'string', required: true, description: 'Task id returned by submit_plugin_metadata.' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args, exec) {
      const parent = exec.agent as Agent | undefined
      if (parent === undefined) throw new Error('document_development requires a calling Main Agent.')
      const task = tasks.require(args.task_id)
      const documentationEvidence = await documentation.run({
        requirementMetadata: task.metadata,
        workspacePath: task.pluginRoot,
        repositoryPath,
      }, { parent, signal: exec.signal })
      tasks.recordDocumentation(task.id, documentationEvidence)
      return {
        task_id: task.id,
        plugin_root: task.pluginRoot,
        documentation: JSON.parse(JSON.stringify(documentationEvidence)),
      }
    },
  })
}
