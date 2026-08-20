export type AcceptanceActor = 'agent' | 'user'

export type AcceptanceSessionStatus =
  | 'starting'
  | 'running'
  | 'passed'
  | 'failed'
  | 'stopped'

export interface AcceptanceMessage {
  actor: AcceptanceActor
  input: string
  output?: string
  timestamp: number
  error?: string
  completed?: boolean
}

export interface AcceptanceSession {
  id: string

  taskId: string

  status: AcceptanceSessionStatus

  /**
   * 用于真实验收的 DSH 子会话标识。
   *
   * 具体类型暂时保持 string，
   * 等确认官方 session/subagent API 后再决定是否使用官方类型。
   */
  childSessionId?: string

  messages: AcceptanceMessage[]

  startedAt: number

  endedAt?: number

  error?: string
}
