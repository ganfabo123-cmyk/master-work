import { defineTool } from '@deepseek-ai/dsh-tools'
import type { PluginMetadataTaskStore } from '../services/plugin-metadata-task-store.js'

const FIELD_SCHEMA = {
  type: 'object' as const,
  additionalProperties: false,
  properties: {
    name: { type: 'string' as const, required: true, description: 'Stable field name used by the plugin contract.' },
    type: { type: 'string' as const, required: true, description: 'Conceptual value type, such as string, number, boolean, object, or array.' },
    required: { type: 'boolean' as const, required: true, description: 'Whether this field must be present for the plugin interaction to be valid.' },
    description: { type: 'string' as const, required: true, description: 'Non-empty explanation of the field meaning, constraints, and consumer-visible purpose.' },
  },
} as const

const FLOW_BLOCK_SCHEMA = {
  type: 'object' as const,
  additionalProperties: false,
  properties: {
    id: { type: 'string' as const, required: true, description: 'Stable identifier referenced by execution arrows.' },
    label: { type: 'string' as const, required: true, description: 'Short name shown inside this execution-process block.' },
    description: { type: 'string' as const, required: true, description: 'Non-empty explanation of the work performed by this block.' },
  },
} as const

const FLOW_ARROW_SCHEMA = {
  type: 'object' as const,
  additionalProperties: false,
  properties: {
    from: { type: 'string' as const, required: true, description: 'Source execution block id.' },
    to: { type: 'string' as const, required: true, description: 'Destination execution block id.' },
    description: { type: 'string' as const, required: true, description: 'Non-empty explanation of the information or effect carried by this arrow.' },
  },
} as const

/**
 * Register the requirement-stage plugin metadata submission tool.
 *
 * @returns A model-facing tool that validates and returns the submitted metadata.
 */
export function submitPluginMetadataTool(tasks: PluginMetadataTaskStore) {
  return defineTool({
    name: 'submit_plugin_metadata',
    description: [
      'Submit the structured requirement metadata for a DeepSeek Harness plugin.',
      'Use it during requirement decomposition after describing the plugin input schema, output schema, block-and-arrow execution flow, and detailed plugin document.',
      'Every input/output field and every flow block/arrow requires a non-empty description.',
      'This tool creates one task-owned plugin scaffold under packages/generated, records the metadata in memory, and does not implement business behavior.',
    ].join('\n'),
    parameters: {
      plugin_name: { type: 'string', required: true, description: 'Non-empty package or plugin name being designed.' },
      plugin_description: { type: 'string', required: true, description: 'Non-empty concise description of the plugin purpose.' },
      input_schema: { type: 'array', required: true, description: 'Plugin input schema. Every field must state name, type, requiredness, and description.', items: FIELD_SCHEMA },
      output_schema: { type: 'array', required: true, description: 'Plugin output schema. Every field must state name, type, requiredness, and description.', items: FIELD_SCHEMA },
      brief_execution_flow: {
        type: 'object',
        required: true,
        description: 'Brief execution process expressed as named blocks and directed arrows between those blocks.',
        additionalProperties: false,
        properties: {
          blocks: { type: 'array', required: true, description: 'Execution-process blocks. Each block describes one participant or processing step.', items: FLOW_BLOCK_SCHEMA },
          arrows: { type: 'array', required: true, description: 'Directed arrows connecting execution-process blocks in the brief flow.', items: FLOW_ARROW_SCHEMA },
        },
      },
      detailed_plugin_document: { type: 'string', required: true, description: 'Non-empty detailed plugin document expanded from the submitted input/output schemas and brief execution flow.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          task_id: { type: 'string', required: true },
          plugin_root: { type: 'string', required: true },
          plugin_metadata: {
            type: 'object',
            required: true,
            description: 'Validated metadata submitted for the current requirement decomposition.',
            additionalProperties: false,
            properties: {
              plugin_name: { type: 'string', required: true },
              plugin_description: { type: 'string', required: true },
              input_schema: { type: 'array', required: true, items: FIELD_SCHEMA },
              output_schema: { type: 'array', required: true, items: FIELD_SCHEMA },
              brief_execution_flow: {
                type: 'object',
                required: true,
                additionalProperties: false,
                properties: {
                  blocks: { type: 'array', required: true, items: FLOW_BLOCK_SCHEMA },
                  arrows: { type: 'array', required: true, items: FLOW_ARROW_SCHEMA },
                },
              },
              detailed_plugin_document: { type: 'string', required: true },
            },
          },
          summary: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.summary }],
    },
    async execute(args) {
      const metadata = {
        plugin_name: requireText(args.plugin_name, 'plugin_name'),
        plugin_description: requireText(args.plugin_description, 'plugin_description'),
        input_schema: validateFields(args.input_schema, 'input_schema'),
        output_schema: validateFields(args.output_schema, 'output_schema'),
        brief_execution_flow: validateFlow(args.brief_execution_flow),
        detailed_plugin_document: requireText(args.detailed_plugin_document, 'detailed_plugin_document'),
      }

      const task = await tasks.create(metadata.plugin_name, metadata)
      return {
        task_id: task.id,
        plugin_root: task.pluginRoot,
        plugin_metadata: metadata,
        summary: `Plugin metadata submitted for ${metadata.plugin_name} as task ${task.id}. Plugin scaffold is ready at ${task.pluginRoot}; fill the generated source and documentation before verification. It includes package.json, tsconfig.json, src/index.ts, src/invariant.ts, and README.md. The scaffold has ${metadata.input_schema.length} input field(s), ${metadata.output_schema.length} output field(s), and ${metadata.brief_execution_flow.blocks.length} execution block(s).`,
      }
    },
  })
}

interface MetadataField {
  name: string
  type: string
  required: boolean
  description: string
}

interface FlowBlock {
  id: string
  label: string
  description: string
}

interface FlowArrow {
  from: string
  to: string
  description: string
}

function validateFields(value: unknown, field: string): MetadataField[] {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array.`)
  return value.map((item, index) => {
    const record = requireRecord(item, `${field}[${index}]`)
    return {
      name: requireText(record.name, `${field}[${index}].name`),
      type: requireText(record.type, `${field}[${index}].type`),
      required: requireBoolean(record.required, `${field}[${index}].required`),
      description: requireText(record.description, `${field}[${index}].description`),
    }
  })
}

function validateFlow(value: unknown): { blocks: FlowBlock[]; arrows: FlowArrow[] } {
  const flow = requireRecord(value, 'brief_execution_flow')
  if (!Array.isArray(flow.blocks)) throw new Error('brief_execution_flow.blocks must be an array.')
  if (!Array.isArray(flow.arrows)) throw new Error('brief_execution_flow.arrows must be an array.')
  const blocks = flow.blocks.map((item, index) => {
    const record = requireRecord(item, `brief_execution_flow.blocks[${index}]`)
    return {
      id: requireText(record.id, `brief_execution_flow.blocks[${index}].id`),
      label: requireText(record.label, `brief_execution_flow.blocks[${index}].label`),
      description: requireText(record.description, `brief_execution_flow.blocks[${index}].description`),
    }
  })
  const blockIds = new Set(blocks.map(block => block.id))
  if (blockIds.size !== blocks.length) throw new Error('brief_execution_flow.blocks must use unique ids.')
  const arrows = flow.arrows.map((item, index) => {
    const record = requireRecord(item, `brief_execution_flow.arrows[${index}]`)
    const arrow = {
      from: requireText(record.from, `brief_execution_flow.arrows[${index}].from`),
      to: requireText(record.to, `brief_execution_flow.arrows[${index}].to`),
      description: requireText(record.description, `brief_execution_flow.arrows[${index}].description`),
    }
    if (!blockIds.has(arrow.from) || !blockIds.has(arrow.to)) throw new Error(`brief_execution_flow.arrows[${index}] must reference existing block ids.`)
    return arrow
  })
  return { blocks, arrows }
}

function requireRecord(value: unknown, field: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error(`${field} must be an object.`)
  return value as Record<string, unknown>
}

function requireText(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) throw new Error(`${field} must be a non-empty string.`)
  return value
}

function requireBoolean(value: unknown, field: string): boolean {
  if (typeof value !== 'boolean') throw new Error(`${field} must be a boolean.`)
  return value
}
