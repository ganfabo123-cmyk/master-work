import { spawn } from 'node:child_process'

export const POWERSHELL_TIMEOUT_MS = 2 * 60 * 1000

export interface PowerShellRequest {
  command: string
  reason: string
  cwd: string
  timeoutMs: number
}

export interface PowerShellResult {
  status: 'executed' | 'permission-rejected' | 'permission-unavailable' | 'bridge-unavailable'
  command: string
  reason: string
  cwd: string
  timeoutMs: number
  stdout: string
  stderr: string
  exitCode: number | null
}

export interface PowerShellExecutor {
  execute(request: PowerShellRequest, signal: AbortSignal): Promise<Pick<PowerShellResult, 'stdout' | 'stderr' | 'exitCode'>>
}

export function createPowerShellExecutor(): PowerShellExecutor {
  return {
    async execute(request, signal) {
      if (signal.aborted) throw new Error('PowerShell command was aborted before it started')
      return await new Promise((resolve, reject) => {
        const child = spawn('powershell.exe', ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', request.command], {
          cwd: request.cwd,
          env: { ...process.env },
          windowsHide: true,
          stdio: ['ignore', 'pipe', 'pipe'],
        })
        let stdout = ''
        let stderr = ''
        let settled = false
        const timeout = setTimeout(() => {
          if (settled) return
          stderr += `\nPowerShell command timed out after ${request.timeoutMs}ms.`
          child.kill()
        }, request.timeoutMs)
        const abort = () => { if (!settled) child.kill() }
        signal.addEventListener('abort', abort, { once: true })
        child.stdout.on('data', (chunk) => { stdout += String(chunk) })
        child.stderr.on('data', (chunk) => { stderr += String(chunk) })
        child.once('error', (error) => {
          settled = true
          clearTimeout(timeout)
          signal.removeEventListener('abort', abort)
          reject(error)
        })
        child.once('close', (exitCode) => {
          settled = true
          clearTimeout(timeout)
          signal.removeEventListener('abort', abort)
          resolve({ stdout, stderr, exitCode })
        })
      })
    },
  }
}
