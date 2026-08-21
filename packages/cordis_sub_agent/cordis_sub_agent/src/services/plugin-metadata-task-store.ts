import { randomUUID } from 'node:crypto'
import { mkdir, rm, stat } from 'node:fs/promises'
import { isAbsolute, relative, resolve } from 'node:path'
import type { EngineeringVerificationResult } from './engineering-verification-service.js'

export interface PluginMetadata {
  plugin_name: string
  plugin_description: string
  input_schema: unknown[]
  output_schema: unknown[]
  brief_execution_flow: {
    blocks: unknown[]
    arrows: unknown[]
  }
  detailed_plugin_document: string
}

export interface PluginMetadataTaskEvidence {
  type: 'reading' | 'documentation' | 'verification' | 'acceptance' | 'discard'
  createdAt: number
  summary: string
  details?: unknown
}

export interface PluginMetadataTask {
  id: string
  metadata: PluginMetadata
  pluginRoot: string
  createdAt: number
  readPlan?: unknown
  documentation?: unknown
  verification?: EngineeringVerificationResult
  acceptanceId?: string
  evidence: PluginMetadataTaskEvidence[]
  error?: string
  discardedAt?: number
}

/** Keeps requirement-stage plugin metadata available to later tools in this DSH process. */
export class PluginMetadataTaskStore {
  private readonly tasks = new Map<string, PluginMetadataTask>()

  constructor(private readonly generatedRoot: string) {}

  /** Create an empty task-owned generated plugin directory and retain its metadata in memory. */
  async create(pluginName: string, metadata: PluginMetadata): Promise<PluginMetadataTask> {
    const pluginRoot = this.resolvePluginRoot(pluginName)
    if (await pathExists(pluginRoot)) {
      throw new Error(`Generated plugin directory already exists and cannot be claimed by a new task: ${pluginRoot}`)
    }
    await mkdir(pluginRoot)
    const task: PluginMetadataTask = {
      id: randomUUID(),
      metadata,
      pluginRoot,
      createdAt: Date.now(),
      evidence: [],
    }
    this.tasks.set(task.id, task)
    return task
  }

  /** Return the submitted metadata task or fail when the id is unknown in this process. */
  require(taskId: string): PluginMetadataTask {
    const task = this.tasks.get(taskId)
    if (task === undefined) throw new Error(`Unknown in-memory plugin metadata task: ${taskId}`)
    return task
  }

  recordReadPlan(taskId: string, readPlan: unknown): void {
    const task = this.requireActive(taskId)
    task.readPlan = readPlan
    this.addEvidence(taskId, {
      type: 'reading',
      createdAt: Date.now(),
      summary: 'Reader Agent returned a structured reading plan.',
      details: { readPlan },
    })
  }

  recordDocumentation(taskId: string, documentation: unknown): void {
    const task = this.requireActive(taskId)
    task.documentation = documentation
    this.addEvidence(taskId, {
      type: 'documentation',
      createdAt: Date.now(),
      summary: 'Documentation Agent completed.',
      details: documentation,
    })
  }

  recordVerification(taskId: string, verification: EngineeringVerificationResult): void {
    const task = this.requireActive(taskId)
    task.verification = verification
    this.addEvidence(taskId, {
      type: 'verification',
      createdAt: Date.now(),
      summary: verification.success ? 'Engineering verification passed.' : 'Engineering verification failed.',
      details: verification,
    })
    if (verification.success || verification.error === undefined) delete task.error
    else task.error = verification.error
  }

  setAcceptanceId(taskId: string, acceptanceId: string): void {
    this.requireActive(taskId).acceptanceId = acceptanceId
  }

  clearAcceptanceId(taskId: string): void {
    delete this.require(taskId).acceptanceId
  }

  recordAcceptance(taskId: string, details: unknown, passed?: boolean): void {
    const task = this.requireActive(taskId)
    this.addEvidence(taskId, {
      type: 'acceptance',
      createdAt: Date.now(),
      summary: passed === true ? 'Real-host acceptance passed.' : passed === false ? 'Real-host acceptance failed.' : 'Real-host acceptance stopped.',
      details,
    })
    if (passed === false) task.error = 'Real-host acceptance failed; Main Agent may continue modifying the same plugin root.'
    else if (passed === true) delete task.error
  }

  async discard(taskId: string): Promise<PluginMetadataTask> {
    const task = this.requireActive(taskId)
    await rm(task.pluginRoot, { recursive: true, force: true })
    task.discardedAt = Date.now()
    this.addEvidence(taskId, {
      type: 'discard',
      createdAt: task.discardedAt,
      summary: 'Task-owned generated plugin directory was discarded.',
      details: { pluginRoot: task.pluginRoot },
    })
    return task
  }

  private requireActive(taskId: string): PluginMetadataTask {
    const task = this.require(taskId)
    if (task.discardedAt !== undefined) throw new Error(`Plugin metadata task has been discarded: ${taskId}`)
    return task
  }

  private addEvidence(taskId: string, evidence: PluginMetadataTaskEvidence): void {
    this.require(taskId).evidence.push(evidence)
  }

  private resolvePluginRoot(pluginName: string): string {
    const root = resolve(this.generatedRoot)
    const directoryName = pluginName.includes('/')
      ? pluginName.slice(pluginName.lastIndexOf('/') + 1)
      : pluginName
    if (!/^[a-z0-9][a-z0-9._-]*$/i.test(directoryName) || directoryName === '.' || directoryName === '..') {
      throw new Error(`Plugin name must resolve to a safe package directory: ${pluginName}`)
    }
    const pluginRoot = resolve(root, directoryName)
    const child = relative(root, pluginRoot)
    if (child.startsWith('..') || isAbsolute(child) || child.length === 0) {
      throw new Error(`Plugin name resolves outside the generated plugin root: ${pluginName}`)
    }
    return pluginRoot
  }
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await stat(path)
    return true
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false
    throw error
  }
}
