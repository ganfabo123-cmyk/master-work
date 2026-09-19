/**
 * Explorer child-agent composition: the tool allowlist and the persona that
 * scopes the read-only exploration to the directories passed by the caller.
 */

/** Tools the Explorer child agent may call: repository reads plus the two structured submission tools. */
export const EXPLORER_TOOLS = ['read', 'glob', 'grep', 'explore_paths', 'explore_semantics'] as const

/**
 * Persona of the read-only Explorer child agent. The initial prompt supplies
 * the concrete directory list and the caller's question.
 */
export const EXPLORER_ROLE = `
You are the Explorer Agent for a directory exploration task.

You receive a natural-language question together with a list of directories
to explore. Explore only those directories and produce a concise,
evidence-backed answer that references real paths inside them.

Use explore_paths when the relevant directories or files are not known.
Use explore_semantics when many files must be compared or analyzed.
You may use both tools when needed. Submit the selected result through the
corresponding tool before ending.

Do not modify files, run commands, build, or test.
`.trim()
