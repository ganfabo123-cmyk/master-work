import { defineTool } from '@deepseek-ai/dsh-tools'

const QUESTION_SCHEMA = {
  type: 'object' as const,
  additionalProperties: false,
  properties: {
    'i want to know': {
      type: 'string' as const,
      required: true,
      description: 'The information the model wants to learn from the repository.',
    },
    because: {
      type: 'string' as const,
      required: true,
      description: 'Why this information is needed.',
    },
  },
} as const

const READING_GUIDANCE =
  'Use the submitted questions as reading goals. Locate the relevant directories in the repository and read the necessary files to understand them. Do not answer the questions from assumptions; inspect the repository first.'

export function whatIWantToKnowTool() {
  return defineTool({
    name: 'what i want to know',
    description: 'Declare what you want to know before exploring the repository.',
    parameters: {
      questions: {
        type: 'array',
        required: true,
        description: 'A list of information requests, each with an explanation of why it is needed.',
        items: QUESTION_SCHEMA,
      },
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: value }],
    },
    async execute(_args) {
      return READING_GUIDANCE
    },
  })
}
