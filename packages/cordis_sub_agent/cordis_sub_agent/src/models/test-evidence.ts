export type VerificationCheckType = 'structure' | 'static' | 'build' | 'test' | 'documentation' | 'artifact'

export interface VerificationCheck {
  id: string
  type: VerificationCheckType
  passed: boolean
  command?: string
  exitCode?: number | null
  stdout?: string
  stderr?: string
  evidence: string
}

export interface ArtifactEvidence {
  packagePath: string
  entryPath: string
  typesPath: string
  packageName: string
  passed: boolean
  errors: string[]
}
