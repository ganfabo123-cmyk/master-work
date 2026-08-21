import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type { ReadPlan, ReadPlanItem } from '../models/read-plan.js'

export class ReaderConclusionStore {
  private readonly plans = new Map<string, ReadPlan>()

  set(taskId: string, plan: ReadPlan): void {
    this.plans.set(taskId, plan)
  }

  take(taskId: string): ReadPlan | undefined {
    const plan = this.plans.get(taskId)
    this.plans.delete(taskId)
    return plan
  }
}

export function readerConclusionTool(store: ReaderConclusionStore) {
  return defineTool({
    name: 'reader_conclusion',
    description: 'Return the required JSON reading plan after read-only repository exploration.',
    parameters: {
      task_id: { type: 'string', required: true, description: 'The current plugin development task id.' },
      mustRead: { type: 'array', required: true, description: 'Load-bearing files the Main Agent must read.' },
      recommendedRead: { type: 'array', required: true, description: 'Additional useful files for the Main Agent to read.' },
      confirmedFacts: { type: 'array', required: true, description: 'Facts confirmed from repository source.' },
      risks: { type: 'array', required: true, description: 'Implementation risks discovered during exploration.' },
      irrelevantOrAvoid: { type: 'array', required: true, description: 'Files or areas the Main Agent should avoid.' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args) {
      const plan: ReadPlan = {
        mustRead: parseItems(args.mustRead, 'mustRead'),
        recommendedRead: parseItems(args.recommendedRead, 'recommendedRead'),
        confirmedFacts: parseStrings(args.confirmedFacts, 'confirmedFacts'),
        risks: parseStrings(args.risks, 'risks'),
        irrelevantOrAvoid: parseStrings(args.irrelevantOrAvoid, 'irrelevantOrAvoid'),
      }
      store.set(args.task_id, plan)
      return JSON.parse(JSON.stringify(plan)) as Record<string, JsonValue>
    },
  })
}

function parseItems(value: unknown, field: string): ReadPlanItem[] {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array.`)
  return value.map((item, index) => {
    if (typeof item !== 'object' || item === null || Array.isArray(item)) throw new Error(`${field}[${index}] must be an object.`)
    const record = item as Record<string, unknown>
    if (typeof record.path !== 'string' || typeof record.reason !== 'string') throw new Error(`${field}[${index}] requires path and reason strings.`)
    return { path: record.path, reason: record.reason }
  })
}

function parseStrings(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || !value.every(item => typeof item === 'string')) throw new Error(`${field} must be an array of strings.`)
  return value
}
