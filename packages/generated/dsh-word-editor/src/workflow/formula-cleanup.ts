/**
 * Formula-cleanup subagent lifecycle of @deepseek-ai/dsh-word-editor. When
 * `formula_scan` finds candidates that a static scanner cannot reliably
 * isolate, a cleanup subagent is spawned via `ctx.subagents.start` with a
 * structured output schema (the `submit_formula_candidates` shape). The
 * subagent has no write tools and cannot touch the document; it only reports
 * normalized linear math candidates back for the deterministic converter.
 * @module @deepseek-ai/dsh-word-editor/workflow/formula-cleanup
 */

import type { Context } from '@deepseek-ai/cordis'
import type { Agent } from '@deepseek-ai/dsh-agent'
import type { ContentBlock } from '@deepseek-ai/dsh-llm'
import type { ObjectJsonSchema } from '@deepseek-ai/dsh-tools'
// Side-effect type import: activate the `ctx.subagents` declaration merge.
import type {} from '@deepseek-ai/dsh-subagent'
import type { FormulaCandidate } from '../types.js'

/** The structured schema a cleanup subagent must answer with. */
export const FORMULA_CANDIDATES_SCHEMA: ObjectJsonSchema = {
  type: 'object',
  additionalProperties: false,
  properties: {
    candidates: {
      type: 'array',
      description: 'Each confirmed formula candidate with its precise source span and normalized linear math.',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          source_start: { type: 'number', description: 'Character offset where the formula starts in the source paragraph/cell text.' },
          source_end: { type: 'number', description: 'Character offset where the formula ends (exclusive).' },
          source_text: { type: 'string', description: 'The verbatim source slice to be replaced.' },
          normalized_latex: { type: 'string', description: 'Cleaned linear math (UnicodeMath / linear LaTeX) that Word builds up.' },
          display: { type: 'string', enum: ['inline', 'block'], description: 'inline (inside the paragraph) or block (its own display equation).' },
          confidence: { type: 'number', description: '0..1 confidence that the normalization is safe to convert.' },
          reason: { type: 'string', description: 'Why this span is (or is not) a formula and why the normalization is trusted.' },
        },
        required: ['source_start', 'source_end', 'source_text', 'normalized_latex', 'display', 'confidence', 'reason'],
      },
    },
  },
  required: ['candidates'],
}

/** A narrowed cleanup subagent verdict. */
export interface CleanupVerdict {
  candidates: Array<{
    source_start: number
    source_end: number
    source_text: string
    normalized_latex: string
    display: 'inline' | 'block'
    confidence: number
    reason: string
  }>
}

/** The persona shown to a formula-cleanup subagent. */
const CLEANUP_PERSONA = [
  '你是公式清理子代理，只负责把候选文本中的公式清洗为标准化线性数学。',
  '你的输入只有一个段落/单元格的原文、Word run 边界提示、前后少量上下文、已有 OMath 的占位符，以及候选产生原因。',
  '规则：',
  '1. 只判断哪些字符是真正的公式并给出 source_start/source_end，不得凭空补充原文本中不存在的变量、上下标或运算符。',
  '2. 去除 Markdown 围栏、零宽字符、网页复制噪声与不必要空格；可以补回能确定的转义或分隔符。',
  '3. normalized_latex 输出 Word 能识别的线性数学（UnicodeMath 或线性 LaTeX）。',
  '4. 区分 inline（段内公式）与 block（独立公式段）。',
  '5. 低于信任的候选仍报告，但 confidence < 0.5，让调用方不自动转换。',
  '6. 你没有 find、文件写入或文档修改工具；不得改动任何文档，只通过 structured_output 提交你的判断。',
  '',
  '回合结束时：通过 structured_output 提交 { candidates }，每条包含 source_start/source_end/source_text/normalized_latex/display/confidence/reason。',
].join('\n')

/**
 * Start a formula-cleanup subagent for a batch and wait for its structured
 * verdict.
 * @param ctx - the plugin context carrying `subagents`.
 * @param provider - the `ctx.subagents` provider name.
 * @param agent - the calling agent (parent).
 * @param signal - abort signal.
 * @param task - the candidates and context to clean.
 * @returns the structured verdict.
 */
export async function runFormulaCleanup(
  ctx: Context,
  provider: string,
  agent: Agent | undefined,
  signal: AbortSignal,
  task: { candidates: FormulaCandidate[]; paragraphText: string; prevText?: string; nextText?: string; omathMasked: string },
): Promise<CleanupVerdict> {
  if (agent === undefined) {
    throw new Error('formula_scan requires a calling agent to start the cleanup subagent')
  }
  const prompt: ContentBlock[] = [
    { type: 'text', text: buildCleanupTask(task) },
  ]
  const run = await ctx.subagents.start(provider, {
    label: `formula-clean:${task.candidates.length} candidates`,
    persona: CLEANUP_PERSONA,
    prompt,
    parent: agent,
    signal,
    outputSchema: FORMULA_CANDIDATES_SCHEMA,
    // The subagent must not edit the document or read the source: it works
    // from the injected candidate text alone and writes only its structured
    // verdict. Deny the editor's tools and the filesystem read/write tools by
    // exact name (the tool filter does not accept a wildcard).
    toolFilter: {
      deny: [
        'word_open', 'word_read', 'word_find', 'word_str_replace', 'word_add_to', 'word_delete',
        'word_formula_scan', 'word_formula_convert', 'word_save', 'read', 'write', 'edit',
      ],
    },
  })
  const result = await run.result
  if (result.stopReason !== 'completed') {
    throw new Error(`formula cleanup subagent ended with stop reason ${String(result.stopReason)}`)
  }
  try {
    await run.dispose()
  } catch {
    // disposal after a clean result is best-effort
  }
  const verdict = narrowVerdict(result.structured)
  if (verdict === null) {
    throw new Error('formula cleanup subagent returned no usable structured candidates')
  }
  return verdict
}

/** Build the cleanup subagent's single task message. */
function buildCleanupTask(task: { candidates: FormulaCandidate[]; paragraphText: string; prevText?: string; nextText?: string; omathMasked: string }): string {
  return JSON.stringify(
    {
      context: {
        prev_text: task.prevText ?? '',
        paragraph_text: task.paragraphText,
        next_text: task.nextText ?? '',
        omath_mask: task.omathMasked,
      },
      candidates: task.candidates.map(c => ({
        source_start: c.source_start,
        source_end: c.source_end,
        source_text: c.source_text,
        reason: c.reason,
      })),
    },
    null,
    2,
  )
}

/** Narrow an unknown structured result into a usable verdict. */
function narrowVerdict(value: unknown): CleanupVerdict | null {
  if (typeof value !== 'object' || value === null) return null
  const record = value as Record<string, unknown>
  const list = record.candidates
  if (!Array.isArray(list)) return null
  const candidates: CleanupVerdict['candidates'] = []
  for (const raw of list) {
    if (typeof raw !== 'object' || raw === null) return null
    const c = raw as Record<string, unknown>
    if (
      typeof c.source_start !== 'number' || typeof c.source_end !== 'number' ||
      typeof c.source_text !== 'string' || typeof c.normalized_latex !== 'string' ||
      (c.display !== 'inline' && c.display !== 'block') ||
      typeof c.confidence !== 'number' || typeof c.reason !== 'string'
    ) {
      return null
    }
    candidates.push({
      source_start: c.source_start,
      source_end: c.source_end,
      source_text: c.source_text,
      normalized_latex: c.normalized_latex,
      display: c.display,
      confidence: c.confidence,
      reason: c.reason,
    })
  }
  return { candidates }
}
