/**
 * Model-facing tools of @deepseek-ai/dsh-swebench: list the local cases,
 * run a model command or test script inside a case's eval container
 * (`swb_run`), and run the black-box official FAIL_TO_PASS / PASS_TO_PASS
 * verdict (`swb_eval`). The host case repo is the read/write workspace —
 * cotracer edits it with ordinary fs tools; only execution goes through
 * Docker, so the model never sees image tags, mounts, conda activation,
 * patches, or CRLF handling.
 * @module @deepseek-ai/dsh-swebench/tools
 */

import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type { SubprocessHandle } from '@deepseek-ai/dsh-subprocess'
import type { CaseEnvironment } from './cases.js'
import { imageTagForInstance } from './cases.js'
import { createRunDirectory, disposeRunDirectory, dockerSourcePath, runDocker, writeRunFile, HOST_REPO_MOUNT, RUN_MOUNT } from './docker.js'
import { buildEvalLauncher, buildEvaluator, buildRunLauncher, EVAL_RESULT_MARKER } from './scripts.js'

/** Verification group summary of {@link swb_eval}, one per list. */
export interface EvalGroup {
  /** Number of nodes in the list. */
  total: number
  /** Number of nodes that passed. */
  passed: number
  /** Test node names that failed (names only, never patch contents). */
  failed: string[]
}

/** Structured black-box verdict of {@link swb_eval}. */
export interface EvalVerdict {
  /** FAIL_TO_PASS group: the tests that must start failing and end passing. */
  fail_to_pass: EvalGroup
  /** PASS_TO_PASS group: the tests that must keep passing. */
  pass_to_pass: EvalGroup
  /** True when every FAIL_TO_PASS passed and no PASS_TO_PASS regressed. */
  resolved: boolean
}

/** Render any tool value as indented JSON text. */
function renderJson(_args: unknown, value: JsonValue): [{ type: 'text'; text: string }] {
  return [{ type: 'text', text: JSON.stringify(value, null, 2) }]
}

/**
 * Parse the `SWE_EVAL_RESULT <json>` marker line from an eval run's stdout.
 * @param stdout - the evaluator's full stdout.
 * @param stderr - the evaluator's full stderr; its tail is included in the
 *   failure diagnostic when the marker line is missing.
 * @returns the parsed verdict.
 * @throws when the marker line is absent or malformed.
 */
function parseEvalVerdict(stdout: string, stderr: string): EvalVerdict {
  const line = stdout
    .split('\n')
    .map(lineText => lineText.trim())
    .find(lineText => lineText.startsWith(`${EVAL_RESULT_MARKER} `))
  if (line === undefined) {
    const stderrTail = stderr.trim().length > 0 ? `${stderr.slice(-2000)}\n` : ''
    throw new Error(`swb_eval: no ${EVAL_RESULT_MARKER} result line in evaluator output:\n${stderrTail}${stdout.slice(-2000)}`)
  }
  try {
    return JSON.parse(line.slice(EVAL_RESULT_MARKER.length + 1)) as EvalVerdict
  } catch (error: unknown) {
    throw new Error(`swb_eval: malformed ${EVAL_RESULT_MARKER} line (${error instanceof Error ? error.message : String(error)})`)
  }
}

/**
 * Check which of the given image tags are present locally through one
 * `docker images` listing, so `swb_list_cases` can report readiness without
 * one inspect per case.
 * @param ctx - the plugin context; execution uses its `subprocess` service.
 * @param signal - the tool's abort signal.
 * @returns the set of present image tags.
 */
async function presentImageTags(ctx: Context, signal: AbortSignal): Promise<Set<string>> {
  let handle: SubprocessHandle
  try {
    handle = ctx.subprocess.spawn({
      argv: ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
      cwd: process.cwd(),
      stdio: {
        stdin: 'ignore',
        stdout: { maxBytes: 64 * 1024 },
        stderr: { maxBytes: 16 * 1024 },
      },
      graceMs: 5_000,
      signal,
    })
  } catch (error: unknown) {
    throw new Error(`swb_list_cases: docker images could not start (${error instanceof Error ? error.message : String(error)})`)
  }
  const outcome = await handle.done
  if (outcome.exitCode !== 0) {
    throw new Error(`swb_list_cases: docker images listing failed (exit ${String(outcome.exitCode)})`)
  }
  const stdout = handle.collected.stdout?.readFrom(0)
  const tags = new Set<string>()
  if (stdout !== undefined) {
    for (const line of stdout.text.split('\n')) {
      const tag = line.trim()
      if (tag.length > 0) tags.add(tag)
    }
  }
  return tags
}

/** Resolve one case environment or fail with a loud message. */
function resolveEnvironment(registry: Map<string, CaseEnvironment>, instanceId: string): CaseEnvironment {
  const env = registry.get(instanceId)
  if (env === undefined) {
    const known = [...registry.keys()].join(', ')
    throw new Error(`swb: unknown instance_id ${JSON.stringify(instanceId)}; known cases: ${known}`)
  }
  return env
}

/** The docker argv tail shared by swb_run and swb_eval. */
function containerArgv(env: CaseEnvironment, runDirHostPath: string, containerName: string): string[] {
  return [
    '--name', containerName,
    '--mount', `type=bind,source=${dockerSourcePath(env.case.repo_path)},target=${HOST_REPO_MOUNT},readonly`,
    '--mount', `type=bind,source=${dockerSourcePath(runDirHostPath)},target=${RUN_MOUNT},readonly`,
    env.imageTag,
  ]
}

/** Tool: list the local cases with their environment readiness. */
export function listCasesTool(ctx: Context, registry: () => Map<string, CaseEnvironment>) {
  return defineTool({
    name: 'swb_list_cases',
    description: [
      'List the local SWE-bench Lite cases and their runtime readiness.',
      'Each entry reports the instance id, the host repository path, the official eval image tag, whether that image is present locally, and the repo\'s test runner (pytest or Django runtests).',
      'Call this first to see which cases exist and whether their docker images are ready before running swb_run or swb_eval.',
    ].join(' '),
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          cases: {
            type: 'array',
            required: true,
            description: 'All local cases in manifest order.',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                instance_id: { type: 'string', required: true, description: 'Dataset instance id.' },
                repo_path: { type: 'string', required: true, description: 'Host path of the case repository worktree.' },
                base_commit: { type: 'string', required: true, description: 'Base commit the repo is checked out at.' },
                image_tag: { type: 'string', required: true, description: 'The official eval image tag.' },
                image_present: { type: 'boolean', required: true, description: 'Whether the eval image is already pulled locally.' },
                runner: { type: 'string', required: true, description: 'The repo\'s official test runner: pytest or runtests.' },
              },
            },
          },
        },
      },
      render: renderJson,
    },
    async execute(_args, exec) {
      const cases = [...registry().values()]
      const present = await presentImageTags(ctx, exec.signal)
      return {
        cases: cases.map(env => ({
          instance_id: env.case.instance_id,
          repo_path: env.case.repo_path,
          base_commit: env.case.base_commit,
          image_tag: env.imageTag,
          image_present: present.has(env.imageTag),
          runner: env.runner,
        })),
      }
    },
  })
}

/** Arguments of the `swb_run` tool. */
interface RunArgs {
  instance_id: string
  command: string
  workdir?: string
}

/** Tool: run a model command inside one case's eval container. */
export function runTool(ctx: Context, registry: () => Map<string, CaseEnvironment>) {
  return defineTool({
    name: 'swb_run',
    description: [
      'Run one shell command inside a SWE-bench case\'s official evaluation container, like a local execution environment for that case.',
      'The current host repository state (including any files you just wrote or edited there) is copied into the container, the case conda environment is activated, and the command runs in workdir (default /testbed) with its full stdout, stderr, and exit code returned.',
      'Use this to run tests, probe scripts, or any Python/shell command against the real case environment without knowing image tags, mounts, or docker commands.',
      'This tool never touches the official gold or test patch — write your own test scripts and run them here.',
    ].join(' '),
    parameters: {
      instance_id: {
        type: 'string',
        required: true,
        description: 'The SWE-bench case to run in, e.g. astropy__astropy-12907.',
      },
      command: {
        type: 'string',
        required: true,
        description: 'The shell command to execute inside the container (e.g. python my_probe.py or pytest -q astropy/modeling/tests/test_separable.py).',
      },
      workdir: {
        type: 'string',
        description: 'In-container working directory for the command; default /testbed (the copied repo root).',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          instance_id: { type: 'string', required: true, description: 'The case that ran.' },
          exit_code: { type: 'number', required: true, description: 'Exit code of the in-container command; 0 means success.' },
          stdout: { type: 'string', required: true, description: 'The command\'s complete standard output.' },
          stderr: { type: 'string', required: true, description: 'The command\'s complete standard error output.' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: renderRun(value) }],
    },
    async execute(args: RunArgs, exec) {
      const env = resolveEnvironment(registry(), args.instance_id)
      const dir = createRunDirectory()
      try {
        writeRunFile(dir, 'run.sh', buildRunLauncher(args.workdir ?? '/testbed'))
        writeRunFile(dir, 'command.sh', args.command)
        const result = await runDocker(ctx, exec, [
          ...containerArgv(env, dir.path, `dsh-sweb-run-${Date.now().toString(36)}`),
          'bash', `${RUN_MOUNT}/run.sh`,
        ])
        return {
          instance_id: args.instance_id,
          exit_code: result.exitCode ?? -1,
          stdout: result.stdout,
          stderr: result.stderr,
        }
      } finally {
        disposeRunDirectory(dir)
      }
    },
  })
}

/** Tool: black-box official verification of one case. */
export function evalTool(ctx: Context, registry: () => Map<string, CaseEnvironment>) {
  return defineTool({
    name: 'swb_eval',
    description: [
      'Run the official SWE-bench verification for one case, black-box.',
      'Inside the container, the current host repository state is copied in, the official test patch for this instance is fetched and applied (its contents never leave the container), and every FAIL_TO_PASS and PASS_TO_PASS test node is run with the repo\'s official runner.',
      'Returns a structured verdict: pass/fail counts per group, the failing test node names, and whether the case is resolved (all FAIL_TO_PASS passing, no PASS_TO_PASS regression).',
      'Test source and assertion details are deliberately withheld to avoid leaking the benchmark; debug your own scripts with swb_run instead.',
    ].join(' '),
    parameters: {
      instance_id: {
        type: 'string',
        required: true,
        description: 'The SWE-bench case to verify, e.g. astropy__astropy-12907.',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          instance_id: { type: 'string', required: true, description: 'The case that was evaluated.' },
          fail_to_pass: {
            type: 'object',
            required: true,
            additionalProperties: false,
            properties: {
              total: { type: 'number', required: true, description: 'Number of FAIL_TO_PASS nodes.' },
              passed: { type: 'number', required: true, description: 'Number that passed.' },
              failed: { type: 'array', required: true, description: 'Failing test node names.', items: { type: 'string' } },
            },
          },
          pass_to_pass: {
            type: 'object',
            required: true,
            additionalProperties: false,
            properties: {
              total: { type: 'number', required: true, description: 'Number of PASS_TO_PASS nodes.' },
              passed: { type: 'number', required: true, description: 'Number that passed.' },
              failed: { type: 'array', required: true, description: 'Regressed test node names.', items: { type: 'string' } },
            },
          },
          resolved: { type: 'boolean', required: true, description: 'True when every FAIL_TO_PASS passed and no PASS_TO_PASS regressed.' },
        },
      },
      render: renderJson,
    },
    async execute(args: { instance_id: string }, exec) {
      const env = resolveEnvironment(registry(), args.instance_id)
      const dir = createRunDirectory()
      try {
        writeRunFile(dir, 'run.sh', buildEvalLauncher())
        writeRunFile(dir, 'evaluator.py', buildEvaluator(args.instance_id, env.runner))
        const result = await runDocker(ctx, exec, [
          ...containerArgv(env, dir.path, `dsh-sweb-eval-${Date.now().toString(36)}`),
          'bash', `${RUN_MOUNT}/run.sh`,
        ])
        const verdict = parseEvalVerdict(result.stdout, result.stderr)
        if (result.exitCode !== 0 && result.exitCode !== null) {
          const detail = (result.stderr + '\n' + result.stdout).slice(-2000)
          throw new Error(`swb_eval: container exited ${String(result.exitCode)}; ${detail}`)
        }
        return { instance_id: args.instance_id, ...verdict }
      } finally {
        disposeRunDirectory(dir)
      }
    },
  })
}

/** Render a swb_run result as text blocks (full debug output). */
function renderRun(value: { instance_id: string; exit_code: number; stdout: string; stderr: string }): string {
  const parts = [
    `instance_id: ${value.instance_id}`,
    `exit_code: ${value.exit_code}`,
  ]
  if (value.stdout.trim().length > 0) parts.push(`stdout:\n${value.stdout}`)
  if (value.stderr.trim().length > 0) parts.push(`stderr:\n${value.stderr}`)
  return parts.join('\n')
}

/** Keep the image derivation export importable from tests. */
export { imageTagForInstance }
