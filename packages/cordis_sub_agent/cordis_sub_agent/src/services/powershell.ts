import type { ToolDefinition } from '@deepseek-ai/dsh-tools'

/** Runtime contract implemented by the separately loaded dsh-powershell plugin. */
export interface PowerShellService {
  createUserPowerShellTool(repositoryRoot: string): ToolDefinition
}

declare module '@deepseek-ai/cordis' {
  interface Context {
    powershell: PowerShellService
  }
}
