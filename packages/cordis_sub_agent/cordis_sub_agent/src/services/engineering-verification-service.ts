import type { Context } from '@deepseek-ai/cordis'
import { readFile } from 'node:fs/promises'
import type {} from '@deepseek-ai/dsh-fs'
import type {} from '@deepseek-ai/dsh-shell'
import type { ArtifactEvidence, VerificationCheck } from '../models/test-evidence.js'
import { PluginContractValidator } from './plugin-contract-validator.js'

export interface EngineeringVerificationInput {
  workspacePath: string
  repositoryPath?: string
  pluginEntryPath: string
  expectedPluginName: string
  typecheckCommand?: string
  buildCommand?: string
  testCommand?: string
  docSyncCommand?: string
  timeoutMs?: number
}

export interface CommandVerificationResult {
  command: string
  exitCode: number | null
  stdout: string
  stderr: string
  stdoutTruncated: boolean
  stderrTruncated: boolean
  stdoutSpillPath?: string
  stderrSpillPath?: string
}

export interface EngineeringVerificationResult {
  success: boolean
  workspacePath: string
  pluginEntryPath: string
  checks: VerificationCheck[]
  artifact?: ArtifactEvidence
  structure?: VerificationCheck[]
  typecheck?: CommandVerificationResult
  build: CommandVerificationResult
  test?: CommandVerificationResult
  documentation?: CommandVerificationResult
  error?: string
}

export class EngineeringVerificationService {
  private readonly contracts = new PluginContractValidator()

  constructor(private readonly ctx: Context) {}

  async verify(input: EngineeringVerificationInput, signal?: AbortSignal): Promise<EngineeringVerificationResult> {
    signal?.throwIfAborted()
    const checks: VerificationCheck[] = []
    const inspected = this.contracts.inspect(input.workspacePath, input.expectedPluginName)
    for (const check of inspected.checks) checks.push({ ...check, type: 'structure', evidence: check.evidence })
    if (inspected.contract === undefined) {
      return {
        success: false,
        workspacePath: input.workspacePath,
        pluginEntryPath: input.pluginEntryPath,
        checks,
        artifact: inspected.artifact,
        build: this.skipped('pnpm build'),
        error: inspected.artifact.errors.join('; '),
      }
    }

    const typecheck = await this.runCommand(
      input.typecheckCommand ?? inspected.contract.typecheckCommand,
      input.workspacePath,
      input.timeoutMs,
      signal,
    )
    checks.push(this.commandCheck('typecheck', 'static', typecheck))
    if (typecheck.exitCode !== 0) {
      return this.failed(input, checks, inspected.artifact, typecheck, undefined, undefined, 'Typecheck failed.')
    }

    const build = await this.runCommand(
      input.buildCommand ?? inspected.contract.buildCommand,
      input.workspacePath,
      input.timeoutMs,
      signal,
    )
    checks.push(this.commandCheck('build', 'build', build))
    if (build.exitCode !== 0) {
      return this.failed(input, checks, inspected.artifact, typecheck, build, undefined, 'Build failed.')
    }

    const artifact = this.contracts.inspect(input.workspacePath, input.expectedPluginName).artifact
    checks.push({
      id: 'artifact',
      type: 'artifact',
      passed: artifact.passed,
      evidence: artifact.errors.join('; ') || 'Expected artifacts exist.',
    })
    if (!artifact.passed) {
      return this.failed(input, checks, artifact, typecheck, build, undefined, artifact.errors.join('; '))
    }

    let test: CommandVerificationResult | undefined
    const testCommand = input.testCommand ?? inspected.contract.testCommand
    if (testCommand !== undefined) {
      test = await this.runCommand(testCommand, input.workspacePath, input.timeoutMs, signal)
      checks.push(this.commandCheck('test', 'test', test))
      if (test.exitCode !== 0) {
        return this.failed(input, checks, artifact, typecheck, build, test, 'Local test failed.')
      }
    }

    let documentation: CommandVerificationResult | undefined
    for (const check of this.contracts.documentationChecks(input.workspacePath)) {
      checks.push({ ...check, type: 'documentation' })
    }
    const documentationChecks = checks.filter(check => check.type === 'documentation')
    if (documentationChecks.some(check => !check.passed)) {
      return this.failed(
        input,
        checks,
        artifact,
        typecheck,
        build,
        test,
        documentationChecks.filter(check => !check.passed).map(check => check.evidence).join('; '),
      )
    }
    if (input.docSyncCommand !== undefined) {
      documentation = await this.runCommand(
        input.docSyncCommand,
        input.repositoryPath ?? input.workspacePath,
        input.timeoutMs,
        signal,
      )
      checks.push(this.commandCheck('documentation', 'documentation', documentation))
      if (documentation.exitCode !== 0) {
        return this.failed(input, checks, artifact, typecheck, build, test, 'Documentation gate failed.', documentation)
      }
    }

    return {
      success: true,
      workspacePath: input.workspacePath,
      pluginEntryPath: input.pluginEntryPath,
      checks,
      artifact,
      typecheck,
      build,
      ...(test !== undefined ? { test } : {}),
      ...(documentation !== undefined ? { documentation } : {}),
    }
  }

  private async runCommand(command: string, workspacePath: string, timeoutMs?: number, signal?: AbortSignal): Promise<CommandVerificationResult> {
    const result = await this.ctx.shell.run(this.ctx.shell.resolve({
      command,
      workdir: workspacePath,
      stdoutMaxBytes: 64 * 1024 * 1024,
      ...(timeoutMs !== undefined ? { timeoutMs } : {}),
      ...(signal !== undefined ? { signal } : {}),
    }))
    if (result.aborted) throw new Error(`Command aborted: ${command}`)
    if (result.timedOut) throw new Error(`Command timed out after ${result.timeoutMs}ms: ${command}`)
    return {
      command,
      exitCode: result.exitCode,
      stdout: await completeOutput(result.stdout),
      stderr: await completeOutput(result.stderr),
      stdoutTruncated: result.stdout.truncated,
      stderrTruncated: result.stderr.truncated,
      ...(result.stdout.spillPath !== undefined ? { stdoutSpillPath: result.stdout.spillPath } : {}),
      ...(result.stderr.spillPath !== undefined ? { stderrSpillPath: result.stderr.spillPath } : {}),
    }
  }

  private commandCheck(id: string, type: VerificationCheck['type'], result: CommandVerificationResult): VerificationCheck {
    return {
      id,
      type,
      passed: result.exitCode === 0,
      command: result.command,
      exitCode: result.exitCode,
      stdout: result.stdout,
      stderr: result.stderr,
      evidence: result.exitCode === 0 ? `${id} passed.` : `${id} failed.`,
    }
  }

  private failed(input: EngineeringVerificationInput, checks: VerificationCheck[], artifact: ArtifactEvidence, typecheck: CommandVerificationResult, build: CommandVerificationResult | undefined, test: CommandVerificationResult | undefined, error: string, documentation?: CommandVerificationResult): EngineeringVerificationResult {
    return {
      success: false,
      workspacePath: input.workspacePath,
      pluginEntryPath: input.pluginEntryPath,
      checks,
      artifact,
      typecheck,
      build: build ?? this.skipped(input.buildCommand ?? 'pnpm build'),
      ...(test !== undefined ? { test } : {}),
      ...(documentation !== undefined ? { documentation } : {}),
      error,
    }
  }

  private skipped(command: string): CommandVerificationResult {
    return { command, exitCode: null, stdout: '', stderr: '', stdoutTruncated: false, stderrTruncated: false }
  }
}

async function completeOutput(output: { text: string; truncated: boolean; spillPath?: string }): Promise<string> {
  if (!output.truncated || output.spillPath === undefined) return output.text
  try {
    return await readFile(output.spillPath, 'utf8')
  } catch {
    return output.text
  }
}
