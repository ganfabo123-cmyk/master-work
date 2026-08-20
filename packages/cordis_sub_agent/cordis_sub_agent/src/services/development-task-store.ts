import type {
  DevelopmentTask,
} from '../models/development-task.js'

import type {
  EngineeringVerificationResult,
} from './engineering-verification-service.js'

import type {
  DevelopmentWorkflowResult,
} from '../workflow/development-workflow.js'


export interface StoredDevelopmentTask {
  task: DevelopmentTask

  workflow?: DevelopmentWorkflowResult

  verification?: EngineeringVerificationResult

  acceptanceId?: string
}


export class DevelopmentTaskStore {
  private readonly tasks =
    new Map<string, StoredDevelopmentTask>()


  create(
    task: DevelopmentTask,
  ): StoredDevelopmentTask {
    if (this.tasks.has(task.id)) {
      throw new Error(
        `Development task already exists: ${task.id}`,
      )
    }

    const record: StoredDevelopmentTask = {
      task,
    }

    this.tasks.set(
      task.id,
      record,
    )

    return record
  }


  get(
    taskId: string,
  ): StoredDevelopmentTask | undefined {
    return this.tasks.get(taskId)
  }


  require(
    taskId: string,
  ): StoredDevelopmentTask {
    const record =
      this.tasks.get(taskId)

    if (record === undefined) {
      throw new Error(
        `Unknown development task: ${taskId}`,
      )
    }

    return record
  }


  setWorkflowResult(
    taskId: string,
    workflow:
    DevelopmentWorkflowResult,
  ): void {
    const record =
      this.require(taskId)

    record.workflow = workflow
  }


  setVerificationResult(
    taskId: string,
    verification:
    EngineeringVerificationResult,
  ): void {
    const record =
      this.require(taskId)

    record.verification =
      verification
  }


  setAcceptanceId(
    taskId: string,
    acceptanceId: string,
  ): void {
    const record =
      this.require(taskId)

    record.acceptanceId =
      acceptanceId
  }

  setCodingAgentId(taskId: string, codingAgentId: string): void {
    const record = this.require(taskId)
    record.task.codingAgentId = codingAgentId
    record.task.updatedAt = Date.now()
  }

  setStatus(
    taskId: string,
    status: DevelopmentTask['status'],
    error?: string,
  ): void {
    const record = this.require(taskId)
    record.task.status = status
    record.task.updatedAt = Date.now()
    if (error !== undefined) record.task.error = error
  }


  clearAcceptanceId(
    taskId: string,
  ): void {
    const record =
      this.require(taskId)

    delete record.acceptanceId
  }


  delete(
    taskId: string,
  ): boolean {
    return this.tasks.delete(taskId)
  }


  list(): StoredDevelopmentTask[] {
    return [
      ...this.tasks.values(),
    ]
  }
}
