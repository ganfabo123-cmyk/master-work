import { describe, expect, it } from 'vitest'
import { dangerousCommandCwdReason } from '../../src/services/dangerous-command-cwd-policy.js'

describe('irreversible shell command policy', () => {
  it('rejects a model pnpm install and asks the user to run it in their own PowerShell', () => {
    const repositoryRoot = 'D:/CodeHarness'
    const worktreeRoot = 'D:/CodeHarness/.cordis/worktrees/hello-plugin'

    const rejection = dangerousCommandCwdReason({
      toolName: 'pwsh',
      argumentsValue: {
        command: 'pnpm install --filter hello-plugin',
        workdir: repositoryRoot,
      },
      sessionCwd: repositoryRoot,
      repositoryRoot,
      worktreeRoots: [worktreeRoot],
    })

    console.info(rejection)
    expect(rejection).toContain('IRREVERSIBLE_COMMAND_REJECTED')
    expect(rejection).toContain('用户在自己的 PowerShell')
    expect(rejection).toContain('D:\\CodeHarness')
    expect(rejection).toContain('本次命令尚未启动')
  })

  it('rejects the same command even when cwd is a task worktree', () => {
    const worktreeRoot = 'D:/CodeHarness/.cordis/worktrees/hello-plugin'

    const rejection = dangerousCommandCwdReason({
      toolName: 'pwsh',
      argumentsValue: {
        command: 'pnpm install --filter hello-plugin',
        workdir: worktreeRoot,
      },
      sessionCwd: 'D:/CodeHarness',
      repositoryRoot: 'D:/CodeHarness',
      worktreeRoots: [worktreeRoot],
    })

    expect(rejection).toContain('IRREVERSIBLE_COMMAND_REJECTED')
  })

  it('rejects destructive file and Git commands', () => {
    for (const command of ['Remove-Item .\\node_modules -Recurse', 'git reset --hard HEAD']) {
      expect(dangerousCommandCwdReason({
        toolName: 'pwsh',
        argumentsValue: { command },
        repositoryRoot: 'D:/CodeHarness',
        worktreeRoots: [],
      })).toContain('IRREVERSIBLE_COMMAND_REJECTED')
    }
  })
})
