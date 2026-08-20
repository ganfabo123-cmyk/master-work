import type { PluginSpec } from './plugin-spec.js'

export type DevelopmentTaskStatus =
  | 'draft'
  | 'requirements_confirmed'
  | 'workspace_ready'
  | 'reading'
  | 'developing'
  | 'engineering_verifying'
  | 'ready_for_acceptance'
  | 'accepting'
  | 'repairing'
  | 'completed'
  | 'failed'
  | 'discarded'

export interface DevelopmentArtifact {
  path: string
  description?: string
}

export interface DevelopmentTask {
  id: string

  spec: PluginSpec

  workspacePath: string

  workspace?: DevelopmentWorkspace

  codingAgentId?: string

  readPlan?: unknown

  status: DevelopmentTaskStatus

  artifacts: DevelopmentArtifact[]

  createdAt: number

  updatedAt: number

  error?: string
}

export interface DevelopmentWorkspace {
  repoRoot: string
  worktreePath: string
  branchName: string
  baseCommit: string
  createdAt: number
  status: 'active' | 'completed' | 'failed' | 'discarded'
}
