import { describe, expect, it, vi } from 'vitest'
import { createUserPowerShellExecutor, executeUserPowerShellRequest, type UserPowerShellExecutor } from '../../src/tools/user-powershell.js'

function execStub() {
  return {
    callId: 'user-powershell-test-call' as never,
    agent: { session: { header: { cwd: 'D:/CodeHarness' } } } as never,
    signal: new AbortController().signal,
  } as never
}

describe('user_powershell permission gate', () => {
  it('executes a harmless command after allowed-once approval and returns feedback', async () => {
    const executor: UserPowerShellExecutor = {
      execute: vi.fn(async () => ({ stdout: 'DSH_POWERSHELL_OK\n', stderr: '', exitCode: 0 })),
    }
    const approval = {
      request: vi.fn(async (request: { reason: string }) => {
        expect(request.reason).toContain('Write-Output DSH_POWERSHELL_OK')
        expect(request.reason).toContain('test harmless PowerShell command')
        return 'allowed-once' as const
      }),
    }

    const result = await executeUserPowerShellRequest(
      { command: 'Write-Output DSH_POWERSHELL_OK', reason: 'test harmless PowerShell command', cwd: 'D:/CodeHarness' },
      execStub(),
      approval,
      executor,
    )

    expect(result).toMatchObject({ status: 'executed', stdout: 'DSH_POWERSHELL_OK\n', exitCode: 0 })
    expect(executor.execute).toHaveBeenCalledOnce()
  })

  it('does not execute when the user rejects permission', async () => {
    const executor: UserPowerShellExecutor = {
      execute: vi.fn(async () => ({ stdout: '', stderr: '', exitCode: 0 })),
    }
    const result = await executeUserPowerShellRequest(
      { command: 'Write-Output SHOULD_NOT_RUN', reason: 'rejection test', cwd: 'D:/CodeHarness' },
      execStub(),
      { request: async () => 'rejected' },
      executor,
    )

    expect(result.status).toBe('permission-rejected')
    expect(executor.execute).not.toHaveBeenCalled()
  })

  it('runs a harmless command in a DSH-owned PowerShell process after approval', async () => {
    const result = await executeUserPowerShellRequest(
      { command: 'Write-Output DSH_POWERSHELL_OK', reason: 'real harmless PowerShell smoke test', cwd: process.cwd() },
      execStub(),
      { request: async () => 'allowed-once' },
      createUserPowerShellExecutor(),
    )

    expect(result.status).toBe('executed')
    expect(result.stdout).toContain('DSH_POWERSHELL_OK')
    expect(result.exitCode).toBe(0)
  })
})
