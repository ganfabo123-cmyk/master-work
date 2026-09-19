import type { Agent } from '@deepseek-ai/dsh-agent'

/** Runtime contract implemented by the separately loaded dsh-explorer-agent plugin. */
export interface ExplorerAgentService {
  run(
    directories: readonly string[],
    question: string,
    options: { parent: Agent; signal: AbortSignal; provider?: string },
  ): Promise<string>
}

declare module '@deepseek-ai/cordis' {
  interface Context {
    /** Explorer capability required from the independently loaded Explorer plugin. */
    explorerAgent: ExplorerAgentService
  }
}
