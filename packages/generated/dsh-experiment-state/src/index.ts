/**
 * @deepseek-ai/dsh-experiment-state — shared external experiment-tree state
 * for hypothesis-driven multi-agent debugging. The coordinator (main agent)
 * creates experiments recording a suspected cause, a falsifiable question, a
 * scope, and shared info; investigation agents write back evidence and
 * conclusions; experiments form a tree via parent references. The store is
 * process-local, so every agent in the process reads the same debug state
 * instead of carrying it in chat context.
 * @module @deepseek-ai/dsh-experiment-state
 */

import type { Context } from '@deepseek-ai/cordis'
import { ExperimentStore } from './store.js'
import { createExperimentTool, EXPERIMENT_EXECUTOR, getExperimentTool, listExperimentsTool, updateExperimentTool } from './tools.js'
import type { ExperimentExecutor } from './tools.js'

export const name = 'experiment-state'
export const inject = ['tools'] as const

export { EXPERIMENT_EXECUTOR, type ExperimentExecutor, type ExperimentExecutorResult } from './tools.js'
export { ExperimentStore } from './store.js'
export type { CreateExperimentInput, ExperimentRecord, ExperimentStatus, ExperimentView, UpdateExperimentPatch } from './store.js'

export function apply(ctx: Context): void {
  const store = new ExperimentStore()

  ctx.effect(() => {
    const disposers = [
      // The optional experimentExecutor service resolves lazily through the
      // global service store, so the detector plugin may provide it after this
      // plugin loads; executor: 'detector' without it fails loudly at call time.
      ctx.tools.register(createExperimentTool(store, () => ctx.get(EXPERIMENT_EXECUTOR) as ExperimentExecutor | undefined)),
      ctx.tools.register(updateExperimentTool(store)),
      ctx.tools.register(getExperimentTool(store)),
      ctx.tools.register(listExperimentsTool(store)),
    ]
    return () => {
      for (const dispose of disposers) {
        dispose()
      }
      // Experiment state is shared debug context, not durable history: a
      // reload restarts the diagnosis fresh instead of mixing stale evidence
      // into a new plugin generation.
      store.clear()
    }
  }, 'experiment-state tools')
}
