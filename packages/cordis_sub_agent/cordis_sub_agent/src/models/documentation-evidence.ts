export interface DocumentationEvidence {
  changedFiles: string[]
  sourceFilesRead: string[]
  commands: string[]
  docSync?: {
    command: string
    exitCode: number | null
    stdout: string
    stderr: string
    stdoutTruncated: boolean
    stderrTruncated: boolean
  }
  pairing?: {
    command: string
    exitCode: number | null
    stdout: string
    stderr: string
    stdoutTruncated: boolean
    stderrTruncated: boolean
  }
  outOfScopeFiles: string[]
  unresolved: string[]
}
