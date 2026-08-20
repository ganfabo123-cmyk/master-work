import type { Agent } from '@deepseek-ai/dsh-agent'
import type { ContentBlock } from '@deepseek-ai/dsh-llm'
import type { SessionId } from '@deepseek-ai/dsh-session'

import type {
  DevelopmentTask,
} from '../models/development-task.js'

import type {
  PluginSpec,
} from '../models/plugin-spec.js'

import type {
  EngineeringVerificationResult,
} from './engineering-verification-service.js'

import {
  PluginBuilder,
} from './plugin-builder.js'

import {
  DevelopmentWorkflow,
  type DevelopmentWorkflowResult,
} from '../workflow/development-workflow.js'

import {
  DevelopmentTaskStore,
} from './development-task-store.js'

import { WorkspaceManager } from './workspace-manager.js'

export interface StartPluginDevelopmentInput {
  taskId: string
  spec: PluginSpec
}


export interface StartPluginDevelopmentOptions {
  parent: Agent

  signal?: AbortSignal

  /**
   * Preferred subagent provider.
   *
   * DevelopmentWorkflow will still verify that
   * the provider supports toolFilter capability.
   */
  preferredProvider?: string

  /**
   * Build command used during engineering verification.
   *
   * MVP default:
   * pnpm build
   */
  buildCommand?: string

  /**
   * Optional test command.
   *
   * If omitted, engineering verification only performs
   * the build and artifact existence check.
   */
  testCommand?: string

  /**
   * Optional timeout for each engineering command.
   */
  verificationTimeoutMs?: number
}


export interface PluginDevelopmentResult {
  task: DevelopmentTask

  workflow: DevelopmentWorkflowResult

  verification?: EngineeringVerificationResult
}


export class PluginDevelopmentService {
  constructor(
    private readonly builder: PluginBuilder,
    private readonly workflow: DevelopmentWorkflow,
    private readonly tasks:
    DevelopmentTaskStore,
    private readonly workspaces: WorkspaceManager,
  ) {}


  async develop(
    input: StartPluginDevelopmentInput,

    options: StartPluginDevelopmentOptions,
  ): Promise<PluginDevelopmentResult> {
    const now = Date.now()

    /*
     * MVP convention:
     *
     * Every generated plugin builds:
     *
     *   src/index.ts
     *       ↓
     *   lib/index.js
     *
     * This convention is intentionally centralized here
     * instead of being guessed by AcceptanceService.
     */
    const workspace = await this.workspaces.create(
      input.taskId,
      options.signal,
    )

    const workspacePath = workspace.worktreePath

    const task: DevelopmentTask = {
      id: input.taskId,
      spec: input.spec,
      workspacePath,
      status: 'requirements_confirmed',
      workspace,
      artifacts: [],
      createdAt: now,
      updatedAt: now,
    }

    this.tasks.create(task)

    try {
      task.status = 'workspace_ready'
      task.updatedAt = Date.now()

      task.artifacts.push(
        ...(await this.builder.createBaseProjectAt(
          workspacePath,
          input.spec.name,
          options.signal,
        )),
      )

      task.status = 'reading'
      task.updatedAt = Date.now()

      const workflowResult =
        await this.workflow.run(
          {
            pluginSpec: input.spec,
            workspacePath,
          },
          {
            parent: options.parent,
            signal:
              options.signal ??
              new AbortController().signal,

            ...(options.preferredProvider !== undefined
              ? {
                preferredProvider:
                    options.preferredProvider,
              }
              : {}),
          },
        )

      this.tasks.setWorkflowResult(
        task.id,
        workflowResult,
      )
      task.readPlan = workflowResult.readPlan
      task.codingAgentId = workflowResult.codingAgentId
      task.status = 'developing'
      task.updatedAt = Date.now()

      return {
        task,
        workflow:
          workflowResult,
      }
    } catch (error) {
      task.status = 'failed'
      task.updatedAt = Date.now()
      task.error =
        error instanceof Error
          ? error.message
          : String(error)

      throw error
    }
  }

  async followup(
    taskId: string,
    parent: Agent,
    evidence: string,
    signal: AbortSignal,
  ): Promise<DevelopmentTask> {
    const record = this.tasks.require(taskId)
    const codingAgentId = record.task.codingAgentId
    if (codingAgentId === undefined) {
      throw new Error(`Development task has no Coding Agent session: ${taskId}`)
    }

    this.tasks.setStatus(taskId, 'repairing')
    const content: ContentBlock[] = [{
      type: 'text',
      text: [
        'Continue the same development task in the existing worktree.',
        'Acceptance or engineering failure evidence:',
        evidence,
        'Read the current files and reproduce the issue before fixing it.',
        'Run the complete required regression checks before reporting ready.',
      ].join('\n'),
    }]

    try {
      await this.workflowContext().subagents.followup(
        parent,
        codingAgentId as SessionId,
        content,
        { source: { kind: 'user' }, signal },
      )
      this.tasks.setStatus(taskId, 'developing')
    } catch (error) {
      this.tasks.setStatus(taskId, 'repairing', errorMessage(error))
      throw error
    }
    return this.tasks.require(taskId).task
  }

  async discard(taskId: string, signal?: AbortSignal): Promise<DevelopmentTask> {
    const record = this.tasks.require(taskId)
    if (record.task.workspace === undefined) {
      throw new Error(`Development task has no managed workspace: ${taskId}`)
    }
    await this.workspaces.discard(record.task.workspace, signal)
    record.task.workspace.status = 'discarded'
    this.tasks.setStatus(taskId, 'discarded')
    return record.task
  }

  private workflowContext(): import('@deepseek-ai/cordis').Context {
    return this.workflow.getContext()
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
