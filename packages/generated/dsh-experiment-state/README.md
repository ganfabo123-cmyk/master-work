English | [中文](README.zh.md)

# @deepseek-ai/dsh-experiment-state

Shared external experiment-tree state for hypothesis-driven multi-agent
debugging. The plugin is not a debugging agent: it records the debug process as
structured experiments so no agent has to carry the debug history in chat
context.

The main agent (coordinator), when it suspects a cause, calls
`experiment_create` with the hypothesis, a falsifiable question, the scope of
directories the investigation may look at, and optional shared info (for
example a survey result collected in advance). An investigation agent then
works inside that scope and writes its evidence and conclusion back with
`experiment_update`. Experiments reference a parent (`parent_id`), so refining
a hypothesis creates a child experiment — the whole debug session is one
experiment tree. `experiment_get` and `experiment_list` let the coordinator
aggregate the state and decide what to prune or refine next.

The store lives in process memory: every agent in the same process reads and
writes the same tree, and nothing is written to disk.

## Usage

Load the plugin in `dsh web`:

```sh
pnpm dsh web --patch ./packages/generated/dsh-experiment-state/cordis.yml
```

Ask the agent to debug something; when it suspects a cause it creates an
experiment, dispatches an investigation, and reads back the evidence to
converge on a root cause.

The plugin has no configuration.

### Tools

Four tools are registered, all returning the experiment as indented JSON.

- `experiment_create` — required `hypothesis`, `question`, `scope` (non-empty
  path list); optional `shared_info`, `executor`, `parent_id`. Fails loudly on
  a blank required field, an empty scope, or an unknown parent id.
- `experiment_update` — required `id`; at least one of optional `status`
  (`pending`, `running`, `completed`, `rejected`, `confirmed`), `evidence`
  (string list, replaces the current list), `result`, `shared_info`,
  `executor`.
- `experiment_get` — required `id`; returns the experiment with its direct
  children attached (one level) so a refined hypothesis is visible.
- `experiment_list` — no arguments; returns every experiment in creation
  order. Each entry carries `parent_id`; an empty `parent_id` marks a root
  experiment, so the tree can be reconstructed.

Experiment fields: `id`, `hypothesis`, `question`, `scope`, `shared_info`,
`executor`, `status`, `evidence`, `result`, `parent_id`, `created_at`,
`updated_at`.

### Execution owner (`executor`)

`experiment_create` accepts an optional `executor`:
`'detector'` runs the experiment automatically through a Detector subagent,
`'self'` (the default) keeps the experiment a record that the calling agent
investigates itself. A child experiment without an explicit `executor`
inherits its parent's. When `executor` is `'detector'`, the plugin resolves the
optional `experimentExecutor` service (`ctx.get`) and runs the experiment with
its `run(record, context)`, then writes the returned conclusion
(`status`/`result`/`evidence`) back before returning. Without a loaded
provider (the `dsh-detector` plugin), `executor: 'detector'` fails loudly.

`shared_info` accumulates along the tree: a child experiment (with
`parent_id`) inherits its parent's `shared_info` automatically and appends any
new `shared_info` the caller passes, so deeper investigations always carry the
context ancestors already gathered and similar issues in the same repo are
not re-surveyed.

## Model Experience

### Plugin interaction

#### What the model sees

The four tool schemas plus, per call, the rendered experiment JSON. The plugin
performs no model work of its own: arguments are validated locally and the
stored records are projected to JSON, so the tool result is the only text the
model sees from the plugin.

#### Token effect

No extra provider calls. The cost is the four tool schemas in the prompt and
the per-call JSON result (bounded by the fields above; `experiment_list`
returns every experiment).

#### KV Cache effect

None: the plugin never issues a provider request, so the request prefix is
unaffected.

## Known Limitations and Deferred Work

- The store is process-local memory: experiment state dies with the process,
  survives tool calls and subagents only within one process lifetime, and is
  cleared on plugin reload.
- The tree is shared process-wide; there is no per-agent access restriction on
  experiments.
- `parent_id` is fixed at creation; experiments cannot be re-parented,
  deleted, or archived.
- Child views expand one level only; deeper trees require following ids with
  `experiment_get`.
- `executor: 'detector'` requires the `experimentExecutor` service (provided
  by `dsh-detector`, or by any plugin that registers it). Nothing in this
  plugin starts subagents itself.
- The plugin records state only: hypothesis generation, experiment selection,
  evidence aggregation, and search-space refinement belong to the orchestrating
  agents, not to this plugin.