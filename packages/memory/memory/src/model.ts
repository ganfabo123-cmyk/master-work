/**
 * Model-facing experience templates and result formatting.
 *
 * @module @deepseek-ai/dsh-memory/model
 */

import type { FactMemory } from './fact.ts'
import type { ExperienceMemory } from './memory.ts'
import type { MemorySearchCandidate } from './service.ts'

/** Recommended structure for a reusable experience body. */
export const EXPERIENCE_BODY_TEMPLATE = `在 {YYYY-MM-DD}（能确认时刻再补 {HH:mm}），我做了 {事情}。
反馈为 {成功 / 失败}（根据用户反馈 {推测依据}）。

当时我的做法是：
{具体做法}

我需要深刻思考一下这次成功/失败的背后原因：
为什么我能成功/失败，我认为原因是：
{原因分析与可迁移原则}`

/**
 * Render lightweight candidates without exposing internal ranking signals.
 * @param candidates - selected search candidates in presentation order.
 * @returns model-facing candidate metadata.
 */
export function formatSearchCandidates(candidates: readonly MemorySearchCandidate[]): string {
  if (candidates.length === 0) return 'No candidate memories matched the supplied keywords.'
  return candidates.map(candidate => [
    `[${candidate.id}]`,
    `title: ${candidate.title}`,
    `keywords: ${candidate.keywords.join(', ')}`,
    `matched keywords: ${candidate.matchedKeywords.join(', ')}`,
    `outcome: ${candidate.outcome}`,
  ].join('\n')).join('\n\n')
}

/**
 * Render the complete block listing for model use.
 * @param blocks - normalized block names owning durable files, in file order.
 * @returns one named block per line, or an explicit empty message.
 */
export function formatBlockIndex(blocks: readonly string[]): string {
  if (blocks.length === 0) return 'No experience memory blocks exist.'
  return ['Experience memory blocks:', ...blocks.map(block => `- ${block}`)].join('\n')
}

/**
 * Render one complete experience for model use.
 * @param memory - durable experience selected by id.
 * @returns model-facing metadata and complete body.
 */
export function formatExperience(memory: ExperienceMemory): string {
  return [
    `# ${memory.title} {${memory.id}}`,
    '',
    `Keywords: ${memory.keywords.join(', ')}`,
    `Recorded At: ${memory.recordedAt}`,
    `Outcome: ${memory.outcome}`,
    '',
    memory.body,
  ].join('\n')
}

/**
 * Render the injected per-cwd facts the model should treat as known context.
 * Facts are stable title/body pairs the user or the model deliberately saved for
 * this working directory; they are not retrieval candidates and are not stale
 * few-shot — each is asserted as a current fact for this cwd.
 * @param facts - durable cwd-scoped facts in file order.
 * @returns the injected system-prompt fact block, or `''` when there are none.
 */
export function formatFactSection(facts: readonly FactMemory[]): string {
  if (facts.length === 0) return ''
  const lines = facts.map((fact, index) => [
    `## ${String(index + 1)}. ${fact.title}`,
    '',
    fact.body,
  ].join('\n'))
  return 'Remembered facts for this working directory (saved by the user or the model; treat them as known, current facts unless contradicted by the user):\n' + lines.join('\n\n')
}
