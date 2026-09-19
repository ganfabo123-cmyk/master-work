import assert from 'node:assert/strict'
import { createPowerShellExecutor, POWERSHELL_TIMEOUT_MS } from '../lib/executor.js'

assert.equal(POWERSHELL_TIMEOUT_MS, 120_000)

const result = await createPowerShellExecutor().execute({
  command: 'Write-Output DSH_POWERSHELL_OK',
  reason: 'PowerShell plugin smoke test',
  cwd: process.cwd(),
  timeoutMs: POWERSHELL_TIMEOUT_MS,
}, new AbortController().signal)

assert.equal(result.exitCode, 0)
assert.match(result.stdout, /DSH_POWERSHELL_OK/)
console.info('1/1 PowerShell plugin tests passed')
