import { isAbsolute, normalize, relative, resolve } from 'node:path'

import type { Context } from '@deepseek-ai/cordis'

import type { DevelopmentWorkspace } from '../models/development-task.js'

export interface WorkspaceManagerOptions {
  repoRoot: string
  workspaceRoot: string
}

export class WorkspaceManager {
  constructor(
    private readonly ctx: Context,
    private readonly options: WorkspaceManagerOptions,
  ) {}

  async create(taskId: string, signal?: AbortSignal): Promise<DevelopmentWorkspace> {
    const repoRoot = resolve(this.options.repoRoot)
    const worktreePath = resolve(this.options.workspaceRoot, taskId)
    const branchName = `cordis-sub-agent/${taskId}`

    this.assertOwnedPath(worktreePath)
    const baseCommit = await this.git(`-C ${quote(repoRoot)} rev-parse HEAD`, repoRoot, signal)
    await this.git(
      `-C ${quote(repoRoot)} worktree add -b ${quote(branchName)} ${quote(worktreePath)} ${quote(baseCommit)}`,
      repoRoot,
      signal,
    )

    return {
      repoRoot,
      worktreePath,
      branchName,
      baseCommit,
      createdAt: Date.now(),
      status: 'active',
    }
  }

  async discard(workspace: DevelopmentWorkspace, signal?: AbortSignal): Promise<void> {
    this.assertOwnedPath(workspace.worktreePath)
    const repoRoot = resolve(workspace.repoRoot)
    await this.git(
      `-C ${quote(repoRoot)} worktree remove --force ${quote(workspace.worktreePath)}`,
      repoRoot,
      signal,
    )
    await this.git(`-C ${quote(repoRoot)} branch -D ${quote(workspace.branchName)}`, repoRoot, signal)
  }

  private async git(command: string, workdir: string, signal?: AbortSignal): Promise<string> {
    const result = await this.ctx.shell.run(this.ctx.shell.resolve({ command, workdir, signal }))
    if (result.aborted || result.timedOut || result.exitCode !== 0) {
      throw new Error([`Git command failed: ${command}`, result.stderr.text].join('\n'))
    }
    return result.stdout.text.trim()
  }

  private assertOwnedPath(worktreePath: string): void {
    const root = normalize(resolve(this.options.workspaceRoot))
    const target = normalize(resolve(worktreePath))
    const child = relative(root, target)
    if (child.startsWith('..') || isAbsolute(child) || target === normalize(resolve(this.options.repoRoot))) {
      throw new Error(`Refusing to operate on non-owned worktree path: ${target}`)
    }
  }
}

function quote(value: string): string {
  return `"${value.replaceAll('"', '\\"')}"`
}
