/**
 * Model-facing tools of @deepseek-ai/dsh-experiment-state: create
 * experiments, write back evidence, read one experiment, and list the whole
 * tree. The coordinator creates and reads; investigation agents write back.
 * @module @deepseek-ai/dsh-experiment-state/tools
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import { EXPERIMENT_EXECUTORS, EXPERIMENT_STATUSES } from './store.js'
import type { ExperimentRecord, ExperimentStore, ExperimentView } from './store.js'

/**
 * Service key of the optional experiment executor: the detector plugin
 * provides an executor under this name, and `experiment_create` with
 * `executor: 'detector'` resolves it through `ctx.get` to start a Detector
 * subagent for the experiment automatically.
 */
export const EXPERIMENT_EXECUTOR = 'experimentExecutor'

/** The conclusion an experiment executor writes back onto one experiment. */
export interface ExperimentExecutorResult {
  status: 'confirmed' | 'rejected' | 'completed'
  result: string
  evidence: string[]
}

/** The experiment executor contract: run one experiment and return its conclusion. */
export interface ExperimentExecutor {
  /**
   * Execute one experiment: start the investigation (for example a Detector
   * subagent) and return the structured conclusion to write back.
   * @param record - the experiment record to execute.
   * @param context - the invoking tool execution context.
   * @returns the conclusion to write back.
   */
  run(record: ExperimentRecord, context: { agent: unknown; signal: AbortSignal }): Promise<ExperimentExecutorResult>
}

/** One experiment without its children; the shared projection of every tool. */
const EXPERIMENT_VIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    id: { type: 'string', required: true, description: 'Experiment id.' },
    hypothesis: { type: 'string', required: true, description: 'The suspected fault cause this experiment investigates.' },
    question: { type: 'string', required: true, description: 'The falsifiable question this experiment must answer.' },
    scope: { type: 'array', required: true, description: 'Directories/files the investigation may look at.', items: { type: 'string' } },
    shared_info: { type: 'string', description: 'Accumulated context inherited from ancestors plus the caller\'s new findings; empty when none was set.' },
    executor: { type: 'string', required: true, enum: [...EXPERIMENT_EXECUTORS], description: 'Execution owner: detector (a Detector subagent runs the experiment automatically) or self (the calling agent investigates).' },
    status: { type: 'string', required: true, enum: [...EXPERIMENT_STATUSES], description: 'Experiment lifecycle status.' },
    evidence: { type: 'array', required: true, description: 'Supporting/contradicting facts written back by the investigator.', items: { type: 'string' } },
    result: { type: 'string', required: true, description: 'Conclusion written back by the investigator; empty means pending.' },
    parent_id: { type: 'string', required: true, description: 'Parent experiment id; empty string means a root experiment.' },
    created_at: { type: 'string', required: true, description: 'ISO 8601 creation time.' },
    updated_at: { type: 'string', required: true, description: 'ISO 8601 last update time.' },
  },
} as const

/** One experiment with its direct children attached (tree view). */
const EXPERIMENT_TREE_VIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    id: { type: 'string', required: true },
    hypothesis: { type: 'string', required: true },
    question: { type: 'string', required: true },
    scope: { type: 'array', required: true, items: { type: 'string' } },
    shared_info: { type: 'string' },
    executor: { type: 'string', required: true, enum: [...EXPERIMENT_EXECUTORS] },
    status: { type: 'string', required: true, enum: [...EXPERIMENT_STATUSES] },
    evidence: { type: 'array', required: true, items: { type: 'string' } },
    result: { type: 'string', required: true },
    parent_id: { type: 'string', required: true },
    created_at: { type: 'string', required: true },
    updated_at: { type: 'string', required: true },
    children: { type: 'array', description: 'Direct child experiments (one level, without their own children).', items: EXPERIMENT_VIEW_SCHEMA },
  },
} as const

/** Render any experiment value as indented JSON text. */
function renderJson(_args: unknown, value: JsonValue): [{ type: 'text'; text: string }] {
  return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
}

/** Tree view of one record for the create/update/get tools. */
function treeView(store: ExperimentStore, record: ExperimentRecord): ExperimentView {
  return store.viewOf(record, true)
}

/**
 * Tool: create one experiment.
 * @param store - the shared experiment store.
 * @param resolveExecutor - resolves the optional `experimentExecutor` service
 *   from the calling context; used only when `executor: 'detector'` is passed,
 *   which starts a Detector subagent for the experiment automatically.
 */
export function createExperimentTool(
  store: ExperimentStore,
  resolveExecutor: () => ExperimentExecutor | undefined,
) {
  return defineTool({
    name: 'experiment_create',
    description: [
      'Create one debug experiment in the shared experiment tree.',
      'Call this when a suspected fault cause (hypothesis) needs a falsifiable question investigated.',
      'The experiment starts pending with empty evidence and result; an investigation agent later writes them back with experiment_update, or sets executor to "detector" so a Detector subagent runs it automatically.',
      'A child experiment (with parent_id) inherits the parent\'s accumulated shared_info and executor unless overridden.',
    ].join(' '),
    parameters: {
      hypothesis: {
        type: 'string',
        required: true,
        description: 'The suspected fault cause this experiment investigates (for example "cache initialization order is wrong").',
      },
      question: {
        type: 'string',
        required: true,
        description: 'The falsifiable question this experiment must answer (for example "in the failing case, is the cache initialized before the first access?").',
      },
      scope: {
        type: 'array',
        required: true,
        description: 'Directories/files the investigation agent may look at. Must contain at least one non-empty path.',
        items: { type: 'string' },
      },
      shared_info: {
        type: 'string',
        description: 'New context for this experiment (for example an explorer conclusion gathered so far). For a child experiment this is appended to the parent\'s accumulated shared_info, which is inherited automatically; omit to inherit the parent\'s context unchanged.',
      },
      executor: {
        type: 'string',
        description: 'Execution owner: "detector" starts a Detector subagent for this experiment and waits for its write-back; "self" (default) leaves the investigation to the calling agent, which writes back with experiment_update.',
        enum: [...EXPERIMENT_EXECUTORS],
      },
      parent_id: {
        type: 'string',
        description: 'Parent experiment id when this experiment refines or verifies an existing hypothesis; omit for a root experiment. The parent must already exist.',
      },
    },
    output: {
      schema: EXPERIMENT_TREE_VIEW_SCHEMA,
      render: renderJson,
    },
    async execute(args, exec) {
      const record = store.create({
        hypothesis: args.hypothesis,
        question: args.question,
        scope: args.scope,
        sharedInfo: args.shared_info,
        executor: args.executor,
        parentId: args.parent_id,
      })
      if (record.executor === 'detector') {
        const executor = resolveExecutor()
        if (executor === undefined) {
          throw new Error('experiment executor "detector" requires the dsh-detector plugin to be loaded (no experimentExecutor service)')
        }
        const conclusion = await executor.run(store.get(record.id) ?? record, { agent: exec.agent, signal: exec.signal })
        return treeView(store, store.update(record.id, {
          status: conclusion.status,
          result: conclusion.result,
          evidence: conclusion.evidence,
        }))
      }
      return treeView(store, record)
    },
  })
}

/** Tool: write evidence, a conclusion, a status, or shared info back onto one experiment. */
export function updateExperimentTool(store: ExperimentStore) {
  return defineTool({
    name: 'experiment_update',
    description: [
      'Write back evidence, a conclusion, a status change, or shared info onto one existing experiment.',
      'Investigation agents use this to record their findings; the coordinator uses it to mark experiments running, completed, rejected, or confirmed.',
      'At least one field is required.',
    ].join(' '),
    parameters: {
      id: { type: 'string', required: true, description: 'The experiment id to update.' },
      status: {
        type: 'string',
        description: 'New lifecycle status: pending, running, completed, rejected, or confirmed.',
        enum: [...EXPERIMENT_STATUSES],
      },
      evidence: {
        type: 'array',
        description: 'Supporting or contradicting facts observed by the investigation; replaces the current list.',
        items: { type: 'string' },
      },
      result: { type: 'string', description: 'The experiment conclusion; an empty string resets it to pending.' },
      shared_info: { type: 'string', description: 'Replacement shared info for later investigation agents.' },
      executor: {
        type: 'string',
        description: 'Execution owner change: "detector" or "self". Only a valid executor value is applied.',
        enum: [...EXPERIMENT_EXECUTORS],
      },
    },
    output: {
      schema: EXPERIMENT_TREE_VIEW_SCHEMA,
      render: renderJson,
    },
    async execute(args) {
      const record = store.update(args.id, {
        status: args.status,
        evidence: args.evidence,
        result: args.result,
        sharedInfo: args.shared_info,
        executor: args.executor,
      })
      return treeView(store, record)
    },
  })
}

/** Tool: read one experiment, including its direct children. */
export function getExperimentTool(store: ExperimentStore) {
  return defineTool({
    name: 'experiment_get',
    description: 'Read one experiment by id, including its direct child experiments (one level) to see how a hypothesis was refined.',
    parameters: {
      id: { type: 'string', required: true, description: 'The experiment id to read.' },
    },
    output: {
      schema: EXPERIMENT_TREE_VIEW_SCHEMA,
      render: renderJson,
    },
    async execute(args) {
      const record = store.get(args.id)
      if (record === undefined) throw new Error(`experiment ${JSON.stringify(args.id)} does not exist`)
      return treeView(store, record)
    },
  })
}

/** Tool: list every experiment in creation order. */
export function listExperimentsTool(store: ExperimentStore) {
  return defineTool({
    name: 'experiment_list',
    description: 'List every experiment in creation order. Each entry carries its parent_id; an empty parent_id marks a root experiment, so the tree can be reconstructed. Use this to aggregate the shared debug state.',
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          experiments: { type: 'array', required: true, items: EXPERIMENT_VIEW_SCHEMA },
        },
      },
      render: renderJson,
    },
    async execute() {
      return { experiments: store.list().map(record => store.viewOf(record, false)) }
    },
  })
}
