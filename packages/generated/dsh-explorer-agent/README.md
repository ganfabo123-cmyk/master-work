English | [中文](README.zh.md)

# @deepseek-ai/dsh-explorer-agent

A reusable read-only directory Explorer Agent for DeepSeek Harness.

The plugin registers the `explorer` tool. The calling agent passes one or more
directories and a natural-language question; the plugin starts a read-only
Explorer subagent scoped to exactly those directories, restricted to
`read`/`glob`/`grep` plus two structured submission channels, and returns a
concise, evidence-backed answer covering the paths and semantic findings the
subagent submitted.

The plugin is the extracted, generalized form of the Explorer Agent that
`cordis-sub-agent` used to embed for its own plugin-development workflow: the
fixed single repository root is replaced by caller-supplied directories, so
any directory or set of directories can be explored.

## Usage

Load the plugin in `dsh web`:

```sh
pnpm dsh web --patch ./packages/generated/explorer-agent/cordis.yml
```

Ask the agent to explore a directory, for example:

> Explore `packages/fs` and `packages/subagent` and tell me how a model-facing
> filesystem search tool registers itself.

The agent calls `explorer` with `directories` and `question` and summarizes
the evidence-backed answer.

### Tool: explorer

Inputs:

- `directories` (required): the directory paths to explore. Multiple
  directories are supported; entries are trimmed, resolved against the current
  working directory, and deduplicated. The Explorer subagent may explore only
  within these directories; a blank list fails loudly.
- `question` (required): the exploration question, passed verbatim to the
  Explorer subagent and used as the match key for its submissions.

Output: a string with two optional sections — `# Explored paths` (the
`explore_paths` submission) and `# Semantic findings` (the `explore_semantics`
submission), each the raw JSON the subagent submitted. The tool fails loudly
when the subagent stops abnormally, when it completes without submitting any
structured result, or when no subagent provider with the `toolFilter`
capability is available.

The Explorer subagent submits findings through `explore_paths` (path
discovery) and `explore_semantics` (multi-file semantic analysis). Both tools
are registered by this plugin and are also visible to the calling agent
because they live on the shared tool registry; only the Explorer subagent is
expected to call them.

## Model Experience

### Plugin interaction

#### What the model sees

The `explorer` tool schema (required `directories` array and `question`), and
per call the formatted answer string with the submitted paths/semantics JSON.
One subagent run per call: the child agent performs the exploration with
`read`/`glob`/`grep` and submits through the structured channels; each call is
one additional model conversation in a fresh child session.

#### Token effect

Each `explorer` call spawns one subagent run, which consumes its own model
budget from the composed LLM provider. The returned answer string is added to
the calling agent's context; `explore_paths`/`explore_semantics` responses
are the JSON the subagent submitted.

#### KV Cache effect

The plugin adds no fixed prompt prefix of its own. Subagent runs are separate
sessions whose cache behavior follows the composed provider and agent-loop
configuration.

## Requirements

- `subagents` service with at least one provider carrying the `toolFilter`
  capability (the in-process `spawn`/`fork` providers qualify).
- `read`/`glob`/`grep` tools composed in the same process, so the Explorer
  subagent can explore: load `@deepseek-ai/dsh-tool-fs` (read) and
  `@deepseek-ai/dsh-tool-fs-search` (glob/grep) when your composition lacks a
  filesystem tool suite.
- An LLM provider configured for subagent runs.

## Known Limitations and Deferred Work

- Exploration scope is enforced by persona and prompt text, not by a
  filesystem policy fence: `read`/`glob`/`grep` are not path-confined to the
  passed directories. The plugin never registers write tools itself, and the
  child agent's toolFilter hides everything but the five read/submission
  tools, but a composed `read` that supports arbitrary paths can still be
  pointed anywhere by the child.
- The subagent's structured submissions are matched to the run by the exact
  question string; two concurrent runs with identical questions on the same
  workflow would collide records. The model-facing tool returns before a new
  call can start, so this does not occur through normal tool usage.
- Result records are process-local and die with the process; there is no
  durable cache of previous explorations.