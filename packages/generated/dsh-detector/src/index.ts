/**
 * @deepseek-ai/dsh-detector — the Detector investigation subagent of the
 * hypothesis-driven multi-agent debugger, delivered as a DSH agent preset.
 * This function plugin contributes the Detector persona (the experiment
 * structure contract) and the `delegate_experiment` tool, which spawns a
 * child Detector on the same role composition with a structured-output
 * schema and collects its verdict. Recursion closes over the shared
 * experiment tree: the preset composition is mounted once per process,
 * child detectors join it through `composeFrom`, and `dsh-experiment-state`
 * keeps one store for the whole recursive investigation.
 *
 * The plugin also provides the shared `experimentExecutor` service: when
 * `experiment_create` runs an experiment with `executor: 'detector'`, the
 * experiment-state plugin resolves this service and the Detector launches a
 * child Detector for that experiment, so the coordinator never wires the
 * investigation itself.
 * @module @deepseek-ai/dsh-detector
 */

import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import type { Agent } from '@deepseek-ai/dsh-agent'
import type { ContentBlock } from '@deepseek-ai/dsh-llm'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { ObjectJsonSchema } from '@deepseek-ai/dsh-tools'
import { assertSubagentMaxDepth } from '@deepseek-ai/dsh-subagent'
import type { SubagentResult, SubagentRun } from '@deepseek-ai/dsh-subagent'
import { PERSONA_ORDER } from '@deepseek-ai/dsh-system-prompt'
import type {} from '@deepseek-ai/dsh-system-prompt'
import { EXPERIMENT_EXECUTOR } from '@deepseek-ai/dsh-experiment-state'
import type { ExperimentExecutor, ExperimentExecutorResult, ExperimentRecord } from '@deepseek-ai/dsh-experiment-state'

export const name = 'detector'
export const inject = ['tools', 'subagents', 'systemPrompt'] as const

/** Model-facing name of the tool that delegates one sub-experiment to a child Detector. */
export const DELEGATE_TOOL = 'delegate_experiment'

/**
 * Prompt-section name of the Detector persona. Deliberately NOT
 * `deployment:persona`: that name already exists in the global prompt layer,
 * where a duplicate insert throws — the persona slot may only be shadowed
 * from a deeper scope (an agent preset), not re-registered globally. This
 * section registers at the persona order (0), so in a deployment with an
 * empty persona it is the first identity section, while a direct overlay or
 * preset mount both load without a layer collision.
 */
export const DETECTOR_PERSONA_SECTION = 'detector:persona'

/** The verdict vocabulary a Detector writes back, shared by the output schemas. */
type DetectorStatus = 'confirmed' | 'rejected' | 'completed'

/**
 * Structured conclusion a child Detector must report through its
 * `structured_output` tool: the same vocabulary a Detector writes back to
 * its experiment (`status`, `result`, `evidence`), so a parent can aggregate
 * child verdicts into its own evidence and conclusion without re-parsing
 * free text.
 */
const DETECTOR_RESULT_SCHEMA: ObjectJsonSchema = {
  type: 'object',
  additionalProperties: false,
  properties: {
    status: {
      type: 'string',
      enum: ['confirmed', 'rejected', 'completed'],
      description: 'Final verdict: confirmed (evidence supports the hypothesis), rejected (evidence refutes it), or completed (investigation done without a determinate verdict).',
    },
    conclusion: {
      type: 'string',
      description: 'The conclusion answering the experiment question, with reasons.',
    },
    evidence: {
      type: 'array',
      items: { type: 'string' },
      description: 'Observed facts as standalone sentences, supporting or contradicting the hypothesis.',
    },
  },
  required: ['status', 'conclusion', 'evidence'],
}

/** Detector persona: how the experiment structure drives the investigation. */
const DETECTOR_PERSONA = [
  '你是 Detector，假设驱动调试系统中的一个实验调查子代理。',
  '你的任务由一个 Experiment（实验）的结构化信息描述，它位于你收到的第一条用户消息中。',
  '',
  '实验字段（字段名与实验状态插件的实验投影一致）：',
  '- experiment_id：本实验的 id。它是 experiment_update 的写回目标；递归拆分时作为子实验的 parent_id。',
  '- hypothesis：本实验正在调查的怀疑故障原因。这是背景信息，不是你的结论。',
  '- question：本实验必须回答的可证伪问题。这是你的任务本体，所有调查围绕回答它展开。',
  '- scope：调查边界，允许你阅读的目录/文件路径列表。你的阅读与写入不得超出这些路径。',
  '- shared_info：启动方累积的上下文。它包含上级实验继承下来的调查结论与本层新补充的信息，是你回答 question 的既有证据，先读它可避免重复排查同一 repo 的相似问题。',
  '- executor：本实验的执行者标记。为 detector 表示本实验由 Detector 子代理自动执行；为 self 表示由调用方 agent 自己排查。',
  '',
  '调查规则：',
  '1. 先用文件读取与搜索工具（read/glob/grep）在 scope 内阅读代码；需要跨文件建立全局认识时，可调用 explorer 工具让只读 Explorer 子代理在 scope 内探查，并把结论写入本实验的 shared_info。禁止超出 scope。',
  '2. 允许为实验编写临时脚本，但只能写入系统临时目录或 test 目录。禁止修改任何源代码文件。',
  '3. 不使用 experiment_get 与 experiment_list 工具。你只通过实验写入口（experiment_create / experiment_update）维护实验状态。',
  '',
  '回答规则：',
  '1. 直接回答：若能在 scope 内直接得出对 question 的结论，用 experiment_update 一次写回：',
  '   - status：confirmed（证据支持 hypothesis）、rejected（证据否定 hypothesis）或 completed（调查完成但无法确定）。',
  '   - result：结论文本，直接回答 question，说明理由与置信度。',
  '   - evidence：观察到的独立事实条目列表，每条一句话，可标注支持或反对 hypothesis。',
  '2. 递归回答：若 question 过大，无法在 scope 内直接回答：',
  '   a. 用 experiment_create 把大问题拆成若干可独立验证的子问题，parent_id 传 experiment_id，每个子实验写明自己的 hypothesis、question、scope。',
  '   b. 子实验的 executor 默认继承本实验的 executor；需要子 Detector 自动执行时保持为 detector，并把本层已有的调查结论（例如 explorer 的发现）放入 shared_info，插件会将其拼接到上级累积上下文之后。',
  '   c. 对每个 executor 为 detector 的子实验，experiment_create 会启动一个子 Detector 自动调查并写回；对 executor 为 self 的子实验，由你自己调查后用 experiment_update 写回。等待全部子实验完成后，把它们的结果聚合为你的 evidence 与 result（result 汇总回答 question，标注每个子结论的来源实验），再用 experiment_update 写回。',
  '3. 调查开始时可以先把自身实验的 status 置为 running，便于上层观察进度。',
  '',
  '回合结束时：若 structured_output 工具可用，必须通过它提交最终结论 { status, conclusion, evidence }；否则用最终消息返回同样内容。',
].join('\n')

/** The Detector persona text, also passed as the child persona on every Detector start. */
export const DETECTOR_PERSONA_TEXT = DETECTOR_PERSONA

/**
 * Map a child stop reason to a model-facing failure headline; `undefined`
 * means the child finished cleanly.
 * @param result - the settled child result.
 * @returns the failure headline, or `undefined` on a clean completion.
 */
function stopReasonError(result: SubagentResult): string | undefined {
  switch (result.stopReason) {
    case 'completed':
      return undefined
    case 'aborted':
      return `${DELEGATE_TOOL}: child run was cancelled`
    case 'error':
      return `${DELEGATE_TOOL}: child run failed`
    case 'max-tokens':
      return `${DELEGATE_TOOL}: child run hit its token limit before finishing`
    case 'refusal':
      return `${DELEGATE_TOOL}: child declined the task`
    // Merge-extensible union: a backend may add stop reasons. Treat an unknown
    // terminal reason as a failure rather than reporting partial output.
    default:
      return `${DELEGATE_TOOL}: child run ended abnormally (${String(result.stopReason)})`
  }
}

/**
 * Collect and release one run without letting disposal replace an
 * independent result failure.
 * @param run - the started subagent run.
 * @returns the settled result.
 */
async function collectRun(run: SubagentRun): Promise<SubagentResult> {
  const [execution] = await Promise.allSettled([run.result])
  const [disposal] = await Promise.allSettled([Promise.resolve().then(() => run.dispose())])
  if (execution.status === 'rejected') {
    if (disposal.status === 'rejected') {
      throw new AggregateError(
        [execution.reason, disposal.reason],
        `${DELEGATE_TOOL}: child run failed and disposal also failed`,
      )
    }
    throw execution.reason
  }
  if (disposal.status === 'rejected') throw disposal.reason
  return execution.value
}

/** Arguments of the `delegate_experiment` tool (the child experiment's fields). */
interface DelegateArgs {
  experiment_id: string
  hypothesis: string
  question: string
  scope: string[]
  shared_info?: string | undefined
}

/**
 * Render the Detector task's first user message from the delegated
 * experiment's fields: the structured experiment information the persona
 * defines as the task input.
 * @param args - the delegated experiment's fields.
 * @returns the task prompt blocks.
 */
function buildDetectorTask(args: DelegateArgs): ContentBlock[] {
  const experiment = {
    experiment_id: args.experiment_id,
    hypothesis: args.hypothesis,
    question: args.question,
    scope: args.scope,
    ...(args.shared_info !== undefined && args.shared_info.length > 0
      ? { shared_info: args.shared_info }
      : {}),
  }
  return [{
    type: 'text',
    text: `请调查以下 Experiment 并返回结构化结论。\n\n${JSON.stringify(experiment, null, 2)}`,
  }]
}

/**
 * Extract the three structured fields a child Detector reports, narrowing the
 * opaque captured value into the tool's canonical output.
 * @param value - `SubagentResult.structured`, typed `unknown` because the
 *   runtime-validated capture is not statically the schema's type.
 * @returns the narrowed record, or `undefined` when the value is not usable.
 */
function structuredConclusion(value: unknown): {
  status: DetectorStatus
  conclusion: string
  evidence: string[]
} | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return undefined
  }
  const record = value as Record<string, unknown>
  const status = record.status
  if (status !== 'confirmed' && status !== 'rejected' && status !== 'completed') {
    return undefined
  }
  if (typeof record.conclusion !== 'string' || !Array.isArray(record.evidence)) {
    return undefined
  }
  return {
    status,
    conclusion: record.conclusion,
    evidence: record.evidence.map(entry => String(entry)),
  }
}

/** Config: the subagent provider child detectors run on plus the recursion budget. */
export interface Config {
  /** The `ctx.subagents` provider name child detectors start on (default `spawn`). */
  provider: string
  /**
   * Recursion budget for a delegated child detector: a non-negative safe
   * integer (default `3`), or `'provider-managed'` to send no cap. The
   * provider enforces the cap against the calling agent's own depth.
   */
  maxDepth?: number | 'provider-managed'
  /**
   * Whether to register the Detector persona as an order-0 prompt section on
   * the loading scope (default `true`). A coordinator composition that only
   * needs the `experimentExecutor` service and `delegate_experiment` tool —
   * for example the CoTracer composition, where the main agent must keep its
   * own identity — sets this to `false`.
   */
  persona: boolean
}

export const Config: z<Config> = z.object({
  provider: z.string().default('spawn'),
  maxDepth: z.union([z.natural().max(Number.MAX_SAFE_INTEGER), z.const('provider-managed' as const)]).default(3),
  persona: z.boolean().default(true),
})

/**
 * Start one child Detector for an experiment's fields and wait for its
 * structured verdict. Shared by the `delegate_experiment` tool and the
 * `experimentExecutor` service.
 * @param ctx - the plugin context carrying subagents and the caller agent.
 * @param config - the plugin configuration.
 * @param args - the experiment's fields to investigate.
 * @param options - the invoking execution context and persona policy.
 * @returns the child's structured verdict.
 */
async function startDetector(
  ctx: Context,
  config: Config,
  args: DelegateArgs,
  options: { agent: unknown; signal: AbortSignal; injectPersona: boolean },
): Promise<{ status: DetectorStatus; conclusion: string; evidence: string[] }> {
  if (options.agent === undefined) {
    throw new Error('experimentExecutor requires a calling agent to start a Detector')
  }
  const parent = options.agent as Agent
  const maxDepth = typeof config.maxDepth === 'number' ? config.maxDepth : undefined
  const run: SubagentRun = await ctx.subagents.start(config.provider, {
    label: `detector:${args.question.slice(0, 48)}`,
    // The delegate tool inherits the Detector persona from the preset
    // composition; the executor service (a coordinator without the persona
    // section, where the child joins the main agent's composition) injects
    // the persona explicitly so the child still identifies as a Detector.
    ...(options.injectPersona ? { persona: DETECTOR_PERSONA } : {}),
    prompt: buildDetectorTask(args),
    parent,
    signal: options.signal,
    outputSchema: DETECTOR_RESULT_SCHEMA,
    ...(maxDepth !== undefined ? { maxDepth } : {}),
    // The child Detector never reads the experiment tree: it works from
    // the injected experiment fields alone and writes only its own
    // experiment back (see the persona's tool rule).
    toolFilter: { deny: ['experiment_get', 'experiment_list'] },
  })
  const result = await collectRun(run)
  const error = stopReasonError(result)
  if (error !== undefined) throw new Error(error)
  const conclusion = structuredConclusion(result.structured)
  if (conclusion === undefined) {
    throw new Error('child detector returned no valid structured result')
  }
  return conclusion
}

/** The experimentExecutor service implementation: run one experiment via a child Detector. */
function detectorExperimentExecutor(ctx: Context, config: Config): ExperimentExecutor {
  return {
    async run(record: ExperimentRecord, context: { agent: unknown; signal: AbortSignal }): Promise<ExperimentExecutorResult> {
      const verdict = await startDetector(ctx, config, {
        experiment_id: record.id,
        hypothesis: record.hypothesis,
        question: record.question,
        scope: record.scope,
        ...(record.sharedInfo.length > 0 ? { shared_info: record.sharedInfo } : {}),
      }, { agent: context.agent, signal: context.signal, injectPersona: true })
      return {
        status: verdict.status,
        result: verdict.conclusion,
        evidence: verdict.evidence,
      }
    },
  }
}

/**
 * Register the Detector persona as the preset's order-0 persona slot, the
 * `delegate_experiment` tool, and the shared `experimentExecutor` service.
 * All registrations ride the calling scope, so a plain mount registers them
 * for every agent joined to the Detector preset.
 * @param ctx - Cordis context with the tools, subagents, and system-prompt services.
 * @param config - plugin configuration.
 */
export function apply(ctx: Context, config: Config): void {
  // A direct apply() bypasses Schemastery's numeric constraints; validate the
  // recursion budget at load (undefined stays valid).
  if (config.maxDepth !== 'provider-managed') assertSubagentMaxDepth(config.maxDepth)

  ctx.effect(() => {
    const disposers: Array<() => void> = []
    if (config.persona) {
      disposers.push(ctx.systemPrompt.section({
        name: DETECTOR_PERSONA_SECTION,
        order: PERSONA_ORDER,
        text: DETECTOR_PERSONA,
      }))
    }
    disposers.push(ctx.tools.register(defineTool({
      name: DELEGATE_TOOL,
      description: [
        'Spawn a child Detector to investigate one sub-experiment and wait for its structured conclusion.',
        'Call this after experiment_create split the current question into a sub-question, passing the child experiment\'s fields exactly as returned.',
        'The child Detector shares the same role composition and writes to the same experiment tree, then returns { experiment_id, status, conclusion, evidence }.',
      ].join(' '),
      parameters: {
        experiment_id: {
          type: 'string',
          required: true,
          description: 'The sub-experiment id returned by experiment_create.',
        },
        hypothesis: {
          type: 'string',
          required: true,
          description: 'The suspected cause this sub-experiment investigates.',
        },
        question: {
          type: 'string',
          required: true,
          description: 'The falsifiable question the child Detector must answer.',
        },
        scope: {
          type: 'array',
          required: true,
          description: 'Directories/files the child Detector may look at. Must contain at least one non-empty path.',
          items: { type: 'string' },
        },
        shared_info: {
          type: 'string',
          description: 'Extra information to pass to the child Detector; omit when empty.',
        },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            experiment_id: { type: 'string', required: true, description: 'The sub-experiment id.' },
            status: { type: 'string', required: true, enum: ['confirmed', 'rejected', 'completed'], description: 'The child Detector\'s verdict.' },
            conclusion: { type: 'string', required: true, description: 'The child Detector\'s conclusion.' },
            evidence: { type: 'array', required: true, items: { type: 'string' }, description: 'The child Detector\'s observed facts.' },
          },
        },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      async execute(args: DelegateArgs, exec) {
        return {
          experiment_id: args.experiment_id,
          ...(await startDetector(ctx, config, args, { agent: exec.agent, signal: exec.signal, injectPersona: false })),
        }
      },
    })))
    const disposeExecutor = ctx.provide(EXPERIMENT_EXECUTOR, detectorExperimentExecutor(ctx, config))
    return async () => {
      for (const dispose of disposers) dispose()
      await disposeExecutor()
    }
  }, 'detector persona, delegate_experiment tool, and experimentExecutor service')
}
