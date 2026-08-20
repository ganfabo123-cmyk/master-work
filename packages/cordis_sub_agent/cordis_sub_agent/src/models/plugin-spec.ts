export interface PluginToolParameterSpec {
  name: string
  description: string
  type: string
  required: boolean
}

export interface PluginToolSpec {
  name: string
  description: string
  parameters: PluginToolParameterSpec[]
  output: string
}

export interface PluginDependencySpec {
  name: string
  reason: string
  required: boolean
}

export interface PluginSpec {
  /**
   * 插件名称。
   */
  name: string

  /**
   * 插件的一句话描述。
   */
  description: string

  /**
   * 面向用户的低信息密度整体说明。
   */
  overview: string

  /**
   * 详细目标。
   */
  goals: string[]

  /**
   * 明确不属于当前插件范围的能力。
   */
  nonGoals: string[]

  /**
   * 插件主要使用场景。
   */
  userScenarios: string[]

  /**
   * 插件需要提供给 Agent 的 Tool。
   */
  tools: PluginToolSpec[]

  /**
   * 插件需要复用的 DSH / Cordis / 外部依赖。
   */
  dependencies: PluginDependencySpec[]

  /**
   * 额外实现约束。
   */
  constraints: string[]

  /**
   * 已知边界情况。
   */
  edgeCases: string[]

  /**
   * 最终验收条件。
   */
  acceptanceCriteria: string[]
}


export interface PluginToolParameterSpec {
  name: string
  description: string
  type: string
  required: boolean
}

export interface PluginToolSpec {
  name: string
  description: string
  parameters: PluginToolParameterSpec[]
  output: string
}

export interface PluginDependencySpec {
  name: string
  reason: string
  required: boolean
}

export interface PluginSpec {
  name: string
  description: string
  overview: string

  goals: string[]
  nonGoals: string[]
  userScenarios: string[]

  tools: PluginToolSpec[]
  dependencies: PluginDependencySpec[]

  constraints: string[]
  edgeCases: string[]
  acceptanceCriteria: string[]
}

export function parsePluginSpec(value: unknown): PluginSpec {
  if (!isRecord(value)) {
    throw new Error('PluginSpec must be an object.')
  }

  return {
    name: requireString(value, 'name'),
    description: requireString(value, 'description'),
    overview: requireString(value, 'overview'),

    goals: requireStringArray(value, 'goals'),
    nonGoals: requireStringArray(value, 'nonGoals'),
    userScenarios: requireStringArray(value, 'userScenarios'),

    tools: requireArray(value, 'tools').map(
      parseToolSpec,
    ),

    dependencies: requireArray(
      value,
      'dependencies',
    ).map(parseDependencySpec),

    constraints: requireStringArray(
      value,
      'constraints',
    ),

    edgeCases: requireStringArray(
      value,
      'edgeCases',
    ),

    acceptanceCriteria: requireStringArray(
      value,
      'acceptanceCriteria',
    ),
  }
}

function parseToolSpec(
  value: unknown,
): PluginToolSpec {
  if (!isRecord(value)) {
    throw new Error(
      'PluginSpec.tools[] must be an object.',
    )
  }

  return {
    name: requireString(value, 'name'),
    description: requireString(
      value,
      'description',
    ),

    parameters: requireArray(
      value,
      'parameters',
    ).map(parseToolParameterSpec),

    output: requireString(value, 'output'),
  }
}

function parseToolParameterSpec(
  value: unknown,
): PluginToolParameterSpec {
  if (!isRecord(value)) {
    throw new Error(
      'PluginSpec.tools[].parameters[] must be an object.',
    )
  }

  return {
    name: requireString(value, 'name'),
    description: requireString(
      value,
      'description',
    ),
    type: requireString(value, 'type'),
    required: requireBoolean(
      value,
      'required',
    ),
  }
}

function parseDependencySpec(
  value: unknown,
): PluginDependencySpec {
  if (!isRecord(value)) {
    throw new Error(
      'PluginSpec.dependencies[] must be an object.',
    )
  }

  return {
    name: requireString(value, 'name'),
    reason: requireString(value, 'reason'),
    required: requireBoolean(
      value,
      'required',
    ),
  }
}

function requireString(
  value: Record<string, unknown>,
  key: string,
): string {
  const field = value[key]

  if (
    typeof field !== 'string' ||
    field.trim().length === 0
  ) {
    throw new Error(
      `PluginSpec.${key} must be a non-empty string.`,
    )
  }

  return field
}

function requireBoolean(
  value: Record<string, unknown>,
  key: string,
): boolean {
  const field = value[key]

  if (typeof field !== 'boolean') {
    throw new Error(
      `PluginSpec.${key} must be a boolean.`,
    )
  }

  return field
}

function requireArray(
  value: Record<string, unknown>,
  key: string,
): unknown[] {
  const field = value[key]

  if (!Array.isArray(field)) {
    throw new Error(
      `PluginSpec.${key} must be an array.`,
    )
  }

  return field
}

function requireStringArray(
  value: Record<string, unknown>,
  key: string,
): string[] {
  const field = requireArray(value, key)

  if (
    !field.every(
      item => typeof item === 'string',
    )
  ) {
    throw new Error(
      `PluginSpec.${key} must contain only strings.`,
    )
  }

  return field
}

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value)
  )
}
