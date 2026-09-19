/**
 * In-memory experiment store: the shared external debug-state backend of
 * @deepseek-ai/dsh-experiment-state. A single store instance lives for the
 * plugin's lifetime inside one process, so every agent (the coordinator, its
 * investigation agents) reads and writes the same experiment tree instead of
 * carrying debug history in chat context.
 * @module @deepseek-ai/dsh-experiment-state/store
 */

import { randomUUID } from 'node:crypto'

/** Valid experiment statuses, in lifecycle order as read by the model. */
export const EXPERIMENT_STATUSES = [
  'pending',
  'running',
  'completed',
  'rejected',
  'confirmed',
] as const

/** Lifecycle status of one experiment. */
export type ExperimentStatus = (typeof EXPERIMENT_STATUSES)[number]

/** Who executes an experiment: `detector` starts a Detector subagent automatically, `self` leaves the investigation to the calling agent. */
export const EXPERIMENT_EXECUTORS = ['detector', 'self'] as const

/** Execution owner of one experiment. */
export type ExperimentExecutor = (typeof EXPERIMENT_EXECUTORS)[number]

/** Internal mutable record for one experiment (camelCase field names). */
export interface ExperimentRecord {
  /** Process-local unique id. */
  readonly id: string
  /** The suspected fault cause this experiment investigates. */
  hypothesis: string
  /** The falsifiable question this experiment must answer. */
  question: string
  /** Directories/files the investigation is allowed to look at. */
  scope: string[]
  /** Extra information the coordinator shares with the investigation agent. */
  sharedInfo: string
  /** Execution owner: `detector` or `self` (the calling agent investigates). */
  executor: ExperimentExecutor
  status: ExperimentStatus
  /** Supporting/contradicting facts written back by the investigator. */
  evidence: string[]
  /** Conclusion written back by the investigator; empty means pending. */
  result: string
  /** Parent experiment id; empty string means a root experiment. */
  parentId: string
  /** ISO 8601 creation time. */
  readonly createdAt: string
  /** ISO 8601 last update time. */
  updatedAt: string
}

/** Model-facing projection of one experiment (snake_case field names). */
export interface ExperimentView {
  id: string
  hypothesis: string
  question: string
  scope: string[]
  shared_info: string
  /** Execution owner: `detector` or `self` (the calling agent investigates). */
  executor: ExperimentExecutor
  status: ExperimentStatus
  evidence: string[]
  result: string
  /** Empty string means a root experiment. */
  parent_id: string
  created_at: string
  updated_at: string
  /**
   * Direct child experiments (one level, without their own children).
   * Present only when the caller asked for the tree view.
   */
  children?: ExperimentView[]
}

/** Arguments accepted by {@link ExperimentStore.create}. */
export interface CreateExperimentInput {
  hypothesis: string
  question: string
  scope: string[]
  sharedInfo?: string | undefined
  /** Execution owner; a child without one inherits its parent's executor. */
  executor?: ExperimentExecutor | undefined
  parentId?: string | undefined
}

/** Partial update applied by {@link ExperimentStore.update}. */
export interface UpdateExperimentPatch {
  status?: string | undefined
  evidence?: string[] | undefined
  result?: string | undefined
  sharedInfo?: string | undefined
  /** Execution owner change; only a valid executor value is applied. */
  executor?: ExperimentExecutor | undefined
}

function isExperimentStatus(value: string): value is ExperimentStatus {
  return (EXPERIMENT_STATUSES as readonly string[]).includes(value)
}

function isExperimentExecutor(value: string): value is ExperimentExecutor {
  return (EXPERIMENT_EXECUTORS as readonly string[]).includes(value)
}

function requireNonEmpty(value: string, field: string): string {
  const trimmed = value.trim()
  if (trimmed.length === 0) throw new Error(`experiment ${field} must be non-empty`)
  return trimmed
}

function requireCleanScope(scope: string[]): string[] {
  if (scope.length === 0) throw new Error('experiment scope must contain at least one path')
  const cleaned = scope.map(entry => entry.trim())
  if (cleaned.some(entry => entry.length === 0)) {
    throw new Error('experiment scope entries must be non-empty')
  }
  return cleaned
}

/**
 * Resolve the execution owner of a new experiment: an explicit `executor`
 * wins, a child without one inherits its parent's executor, and a root
 * experiment defaults to `self` (the calling agent investigates).
 * @param requested - the caller-supplied executor, if any.
 * @param parent - the parent record, or `undefined` for a root experiment.
 * @returns the resolved executor.
 */
function resolveExecutor(
  requested: ExperimentExecutor | undefined,
  parent: ExperimentRecord | undefined,
): ExperimentExecutor {
  if (requested !== undefined) return requested
  return parent?.executor ?? 'self'
}

/**
 * Accumulate shared info for a child experiment: the parent's accumulated
 * shared info is inherited automatically and the caller's new findings are
 * appended below it, so a deeper experiment never loses the context its
 * ancestors already gathered (for example earlier explorer conclusions).
 * @param parentInfo - the parent experiment's shared info.
 * @param callerInfo - the caller-supplied new findings, or `undefined`.
 * @returns the combined shared info.
 */
function accumulateSharedInfo(parentInfo: string, callerInfo: string | undefined): string {
  const caller = (callerInfo ?? '').trim()
  if (parentInfo.length === 0) return caller
  if (caller.length === 0) return parentInfo
  return `${parentInfo}\n${caller}`
}

/**
 * Process-local experiment store. Insertion order is creation order, so
 * {@link list} returns experiments oldest first.
 */
export class ExperimentStore {
  private readonly records = new Map<string, ExperimentRecord>()

  /**
   * Create one experiment. `parentId` must reference an existing experiment;
   * an unknown parent fails loudly rather than being silently dropped, so the
   * tree never grows a dangling edge.
   * @param input - the coordinator's experiment description.
   * @returns the stored record with `pending` status and empty evidence/result.
   */
  create(input: CreateExperimentInput): ExperimentRecord {
    const hypothesis = requireNonEmpty(input.hypothesis, 'hypothesis')
    const question = requireNonEmpty(input.question, 'question')
    const scope = requireCleanScope(input.scope)
    const parentId = (input.parentId ?? '').trim()
    if (parentId !== '' && !this.records.has(parentId)) {
      throw new Error(`experiment parent ${JSON.stringify(parentId)} does not exist`)
    }
    const parent = parentId === '' ? undefined : this.records.get(parentId)
    const executor = resolveExecutor(input.executor, parent)
    const sharedInfo = parent === undefined
      ? (input.sharedInfo ?? '').trim()
      : accumulateSharedInfo(parent.sharedInfo, input.sharedInfo)
    const now = new Date().toISOString()
    const record: ExperimentRecord = {
      id: randomUUID(),
      hypothesis,
      question,
      scope,
      sharedInfo,
      executor,
      status: 'pending',
      evidence: [],
      result: '',
      parentId,
      createdAt: now,
      updatedAt: now,
    }
    this.records.set(record.id, record)
    return record
  }

  /**
   * Write back evidence, a conclusion, a status change, or shared info onto
   * one existing experiment. At least one field must be supplied and `status`
   * must be a valid lifecycle value.
   * @param id - the experiment to update.
   * @param patch - the fields to replace.
   * @returns the updated record.
   */
  update(id: string, patch: UpdateExperimentPatch): ExperimentRecord {
    const record = this.records.get(id)
    if (record === undefined) throw new Error(`experiment ${JSON.stringify(id)} does not exist`)
    const { status, evidence, result, sharedInfo, executor } = patch
    if (status === undefined && evidence === undefined && result === undefined && sharedInfo === undefined && executor === undefined) {
      throw new Error('experiment_update requires at least one field to update')
    }
    if (status !== undefined) {
      if (!isExperimentStatus(status)) {
        throw new Error(`invalid experiment status ${JSON.stringify(status)}; expected one of ${EXPERIMENT_STATUSES.join(', ')}`)
      }
      record.status = status
    }
    if (evidence !== undefined) {
      const cleaned = evidence.map(entry => entry.trim())
      if (cleaned.some(entry => entry.length === 0)) {
        throw new Error('experiment evidence entries must be non-empty')
      }
      record.evidence = cleaned
    }
    if (result !== undefined) record.result = result.trim()
    if (sharedInfo !== undefined) record.sharedInfo = sharedInfo.trim()
    if (executor !== undefined) {
      if (!isExperimentExecutor(executor)) {
        throw new Error(`invalid experiment executor ${JSON.stringify(executor)}; expected one of ${EXPERIMENT_EXECUTORS.join(', ')}`)
      }
      record.executor = executor
    }
    record.updatedAt = new Date().toISOString()
    return record
  }

  /**
   * Read one experiment by id.
   * @param id - the experiment id.
   * @returns the record, or `undefined` when no experiment has that id.
   */
  get(id: string): ExperimentRecord | undefined {
    return this.records.get(id)
  }

  /**
   * Read every experiment, in creation order.
   * @returns all stored records.
   */
  list(): ExperimentRecord[] {
    return [...this.records.values()]
  }

  /**
   * Project one record into its model-facing shape.
   * @param record - the stored record.
   * @param includeChildren - whether to attach the direct child views.
   * @returns the projection.
   */
  viewOf(record: ExperimentRecord, includeChildren: boolean): ExperimentView {
    const view: ExperimentView = {
      id: record.id,
      hypothesis: record.hypothesis,
      question: record.question,
      scope: [...record.scope],
      shared_info: record.sharedInfo,
      executor: record.executor,
      status: record.status,
      evidence: [...record.evidence],
      result: record.result,
      parent_id: record.parentId,
      created_at: record.createdAt,
      updated_at: record.updatedAt,
    }
    if (includeChildren) view.children = this.childrenOf(record.id)
    return view
  }

  /** Direct children of one experiment as one-level views. */
  private childrenOf(id: string): ExperimentView[] {
    return [...this.records.values()]
      .filter(record => record.parentId === id)
      .map(record => this.viewOf(record, false))
  }

  /** Drop every stored experiment (used by the plugin disposer). */
  clear(): void {
    this.records.clear()
  }
}
