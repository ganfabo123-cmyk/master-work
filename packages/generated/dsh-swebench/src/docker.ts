/**
 * Docker execution of @deepseek-ai/dsh-swebench: every tool runs the case
 * repository inside one throwaway (`--rm`) official eval container. The host
 * repo is bound read-only to `/host-testbed`; a generated run directory
 * (run scripts, model command, optional eval output) is bound read-only to
 * `/sweb`; the container copies the host tree into `/testbed` (excluding the
 * Windows worktree `.git` pointer), applies patches in-container with
 * `git apply --no-index` after CRLF defense, and never writes back to the
 * host repo. Docker is invoked as a CLI through `ctx.subprocess.spawn` — no
 * shell layer, mirroring the ripgrep consumer pattern.
 * @module @deepseek-ai/dsh-swebench/docker
 */

import { mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, sep } from 'node:path'
import { randomUUID } from 'node:crypto'
import type { Context } from '@deepseek-ai/cordis'
import type { ToolExecution } from '@deepseek-ai/dsh-tools'
import type { SubprocessHandle, SubprocessOutcome } from '@deepseek-ai/dsh-subprocess'

/** The in-container mount point of the read-only host case repo. */
export const HOST_REPO_MOUNT = '/host-testbed'
/** The in-container mount point of the generated run directory. */
export const RUN_MOUNT = '/sweb'
/** The in-container working copy of the case repo. */
export const TESTBED = '/testbed'
/** Conda activation script inside the official eval images. */
export const CONDA_ACTIVATE = '/opt/miniconda3/bin/activate'
/** Bounded collection cap for a docker run's stdout/stderr (64 KiB tail). */
const OUTPUT_MAX_BYTES = 64 * 1024

/** Exit facts of one docker run. */
export interface DockerRunResult {
  /** Exit code of the in-container bash script; null when killed by a signal. */
  exitCode: number | null
  /** Captured stdout of the whole run. */
  stdout: string
  /** Captured stderr of the whole run. */
  stderr: string
}

/** A generated run directory: its host path and every file written into it. */
export interface RunDirectory {
  /** Absolute host path, bound read-only into the container at `RUN_MOUNT`. */
  path: string
}

/**
 * Create a fresh run directory for one docker invocation.
 * @returns the run directory handle.
 */
export function createRunDirectory(): RunDirectory {
  const path = join(tmpdir(), `dsh-swebench-${process.pid}-${randomUUID()}`)
  mkdirSync(path, { recursive: true })
  return { path }
}

/**
 * Write one file inside a run directory.
 * @param dir - the run directory.
 * @param relativePath - path relative to the run directory.
 * @param content - file content.
 */
export function writeRunFile(dir: RunDirectory, relativePath: string, content: string): void {
  // Relative paths come from the plugin's own fixed templates, never from
  // model input.
  const target = join(dir.path, relativePath)
  mkdirSync(target.slice(0, target.lastIndexOf(sep)) || dir.path, { recursive: true })
  writeFileSync(target, content, 'utf8')
}

/**
 * Remove a run directory after the docker invocation settles.
 * @param dir - the run directory.
 */
export function disposeRunDirectory(dir: RunDirectory): void {
  rmSync(dir.path, { recursive: true, force: true, maxRetries: 3 })
}

/**
 * Convert a Windows host path into the forward-slash form Docker accepts in a
 * bind source (`D:\repo\x` → `D:/repo/x`).
 * @param hostPath - absolute host path.
 * @returns the docker-safe source form.
 */
export function dockerSourcePath(hostPath: string): string {
  return hostPath.replaceAll('\\', '/')
}

/**
 * Spawn `docker run` with the given argv tail and collect its output. The
 * child carries the tool's abort signal so timeout/cancellation terminates the
 * whole process tree.
 * @param ctx - the plugin context; execution uses its `subprocess` service.
 * @param exec - the tool-execution context; supplies the abort signal.
 * @param argv - docker run arguments after the fixed `docker run` prefix.
 * @returns the collected run result.
 */
export async function runDocker(
  ctx: Context,
  exec: ToolExecution,
  argv: readonly string[],
): Promise<DockerRunResult> {
  const dockerArgv = ['docker', 'run', '--rm', ...argv]
  let handle: SubprocessHandle
  try {
    handle = ctx.subprocess.spawn({
      argv: dockerArgv,
      cwd: process.cwd(),
      stdio: {
        stdin: 'ignore',
        stdout: { maxBytes: OUTPUT_MAX_BYTES, spill: { maxBytes: 8 * 1024 * 1024 } },
        stderr: { maxBytes: OUTPUT_MAX_BYTES, spill: { maxBytes: 8 * 1024 * 1024 } },
      },
      graceMs: 5_000,
      signal: exec.signal,
    })
  } catch (error: unknown) {
    if (exec.signal.aborted) {
      throw new Error('swb: docker run was aborted before launch (tool timeout or caller cancellation)')
    }
    throw new Error(`swb: docker run could not start (${error instanceof Error ? error.message : String(error)})`)
  }
  let outcome: SubprocessOutcome
  try {
    outcome = await handle.done
  } catch (error: unknown) {
    throw new Error(`swb: docker run failed to launch (${error instanceof Error ? error.message : String(error)})`)
  }
  const stdout = handle.collected.stdout?.readFrom(0)
  const stderr = handle.collected.stderr?.readFrom(0)
  return {
    exitCode: outcome.exitCode,
    stdout: stdout === undefined ? '' : stdout.text,
    stderr: stderr === undefined ? '' : stderr.text,
  }
}
