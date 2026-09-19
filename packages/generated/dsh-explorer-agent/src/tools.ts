/**
 * Model-facing tools of explorer-agent: the `explorer` entry tool plus the two
 * structured submission channels used by the Explorer child agent.
 */

import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import type {
  ExplorerAgentCapability,
  ExplorePathsResult,
  ExploreSemanticsResult,
} from './workflow.js'

const PATH_ITEM_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    path: { type: 'string', required: true },
    kind: { type: 'string', required: true, enum: ['directory', 'file'] },
    summary: { type: 'string', required: true },
    reason: { type: 'string', required: true },
  },
} as const

const EVIDENCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    path: { type: 'string', required: true },
    kind: { type: 'string', required: true, enum: ['directory', 'file'] },
    lines: { type: 'string' },
    reason: { type: 'string', required: true },
  },
} as const

const FINDING_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    title: { type: 'string', required: true },
    summary: { type: 'string', required: true },
    evidence: { type: 'array', required: true, items: EVIDENCE_SCHEMA },
  },
} as const

/** Submission channel for path-discovery results, called by the Explorer child agent. */
export function explorePathsTool(workflow: ExplorerAgentCapability) {
  return defineTool({
    name: 'explore_paths',
    description: 'Submit the directories and files relevant to the exploration question.',
    parameters: {
      question: { type: 'string', required: true },
      answer: { type: 'string', required: true },
      paths: { type: 'array', required: true, items: PATH_ITEM_SCHEMA },
      risks: { type: 'array', required: true, items: { type: 'string' } },
      gaps: { type: 'array', required: true, items: { type: 'string' } },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args) {
      workflow.recordPaths(args as ExplorePathsResult)
      return JSON.parse(JSON.stringify(args)) as Record<string, JsonValue>
    },
  })
}

/** Submission channel for multi-file semantic analysis results, called by the Explorer child agent. */
export function exploreSemanticsTool(workflow: ExplorerAgentCapability) {
  return defineTool({
    name: 'explore_semantics',
    description: 'Submit semantic conclusions and evidence from multi-file exploration.',
    parameters: {
      question: { type: 'string', required: true },
      answer: { type: 'string', required: true },
      findings: { type: 'array', required: true, items: FINDING_SCHEMA },
      risks: { type: 'array', required: true, items: { type: 'string' } },
      gaps: { type: 'array', required: true, items: { type: 'string' } },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args) {
      workflow.recordSemantics(args as ExploreSemanticsResult)
      return JSON.parse(JSON.stringify(args)) as Record<string, JsonValue>
    },
  })
}

/** Entry tool: explore one or more directories to answer a question. */
export function explorerTool(workflow: ExplorerAgentCapability) {
  return defineTool({
    name: 'explorer',
    description: 'Ask an Explorer Agent to investigate the given directories and return a concise evidence-backed answer.',
    parameters: {
      directories: {
        type: 'array',
        required: true,
        description: 'The directories to explore. Multiple directories are supported; the Explorer Agent may explore only within these directories.',
        items: { type: 'string' },
      },
      question: {
        type: 'string',
        required: true,
        description: 'The exploration question the Explorer Agent must answer from the directories.',
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(args, exec) {
      if (exec.agent === undefined) throw new Error('explorer requires a calling agent.')
      return workflow.run(args.directories, args.question, { parent: exec.agent, signal: exec.signal })
    },
  })
}
