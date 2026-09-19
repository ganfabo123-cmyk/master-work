English | [中文](README.zh.md)

# @deepseek-ai/dsh-detector

Detector is the investigation subagent of the hypothesis-driven multi-agent debugger: it answers one locally scoped experiment question (question), writes evidence and a conclusion back to the shared experiment tree, and — when the question is too large to answer directly inside its scope — recursively splits it into child experiments, delegates each child experiment to a child Detector, and aggregates the child verdicts into its own answer. It also exposes its launch logic as the shared `experimentExecutor` service, which `experiment_create` with `executor: "detector"` resolves to start a Detector automatically.

Detector investigates one experiment at a time. Its input is the experiment's structured information (`experiment_id`, `hypothesis`, `question`, `scope`, `shared_info`, `executor`), defined by [`@deepseek-ai/dsh-experiment-state`](../dsh-experiment-state/README.md); the experiment field names and write-back semantics follow that plugin's real projection, which is the only authority. This package delivers the role as an agent preset (a directory with `agent.cordis.yml` and `preset.yml`) plus a function plugin that provides the Detector persona and the `delegate_experiment` tool and the `experimentExecutor` service.

This is the read-only baseline for the hypothesis-driven debugger's ablation study: a Detector reads code inside its scope and writes the experiment tree, but carries no investigation tooling (runtime traces, instrumentation, breakpoints, and so on). Later versions mount tools derived from single-agent trace papers onto this same role, and the baseline is the comparison control.

## Composition

```text
packages/generated/dsh-detector/
├── agent.cordis.yml   # the detector agent preset: this plugin + dsh-experiment-state + dsh-explorer-agent
├── preset.yml         # display metadata for the preset roster
├── cordis.yml         # verification overlay: load the role into the host composition
├── cordis.acceptance.yml
└── src/index.ts       # the function plugin: persona section + delegate_experiment tool + experimentExecutor service
```

The preset composition contains only the role plugin, `dsh-experiment-state`,
and `dsh-explorer-agent`. The host composition already supplies the filesystem
tools (read/search), the `ctx.subagents` service, and the in-process `spawn`
provider; the preset must not re-load those, because a repeated root-realm
service or duplicate tool registration fails the mount. The composition is
mounted once per process (a standing mount), and every child Detector joins it
through the subagent service's `composeFrom`, so the experiment-state store is
one instance shared by the whole recursive investigation and every layer can
call the `explorer` tool inside its scope.

## Usage

### As an agent preset (production path)

The coordinator plugin (a separate planned package, not this one) registers this directory as an agent-presets root, creates the root experiment, and starts a Detector with the experiment's structured information as the first user message. A Detector that cannot answer directly creates child experiments itself and delegates them through `delegate_experiment`, so no further wiring is needed inside the recursion.

### Direct verification overlay

```sh
pnpm dsh web --patch ./packages/generated/dsh-detector/cordis.yml
```

The root agent becomes a Detector: the persona replaces the deployment persona, and `experiment_create`, `experiment_update`, and `delegate_experiment` appear in its tool set. Use this to exercise the role manually. Real orchestration mounts the preset directory instead; the overlay is the self-contained verification/demo form.

## Tools

### `delegate_experiment`

Spawn one child Detector for a sub-experiment and wait for its structured conclusion.

| Argument | Type | Required | Meaning |
|---|---|---|---|
| `experiment_id` | string | yes | The sub-experiment id returned by `experiment_create`. |
| `hypothesis` | string | yes | The suspected cause this sub-experiment investigates. |
| `question` | string | yes | The falsifiable question the child Detector must answer. |
| `scope` | string[] | yes | Directories/files the child Detector may look at. |
| `shared_info` | string | no | Extra information passed to the child Detector. |

The tool starts the child through `ctx.subagents.start` on the configured provider, requires a structured output schema (`{ status, conclusion, evidence }`), hides `experiment_get`/`experiment_list` from the child via `toolFilter`, and returns the child's verdict as `{ experiment_id, status, conclusion, evidence }`. The child Detector inherits the same role composition (including the `explorer` tool), so it can recurse further.

### `experimentExecutor` service

Registers under the shared key `experimentExecutor` (the constant exported by
`dsh-experiment-state`). `run(record, context)` starts one child Detector for
the given experiment record and returns the write-back conclusion
(`{ status, result, evidence }`), so `experiment_create` with
`executor: "detector"` can run any experiment through a Detector automatically,
without the caller wiring the investigation itself. The child persona is
injected per start, so a coordinator loading this plugin with `persona: false`
still produces correctly-identified Detector children.

## Configuration

| Field | Default | Meaning |
|---|---|---|
| `provider` | `spawn` | The `ctx.subagents` provider name child Detectors start on. |
| `maxDepth` | `3` | Recursion budget for a delegated child Detector: a non-negative safe integer, or `'provider-managed'` to send no cap. The provider enforces the cap against the calling agent's own depth. |
| `persona` | `true` | Whether to register the Detector persona as an order-0 prompt section on the loading scope. A coordinator composition that only needs the tool and the executor service (for example CoTracer) sets this to `false` so the main agent keeps its own identity. |

## The experiment-structure contract (the persona)

The persona registers as an order-0 prompt section named `detector:persona` — at the deployment persona's position, so in a deployment with an empty persona it is the first identity section. The name deliberately differs from `deployment:persona` (that slot may only be shadowed from a deeper scope, never re-registered in a global layer), so both the preset mount and the direct overlay load without a layer collision. Every agent joined to the preset reads it. It defines how the Detector uses the experiment data:

- `question` is the task: the falsifiable question the investigation must answer. `hypothesis` is background, never the conclusion. `scope` is the hard investigation boundary: reading and writing beyond it is a violation. `shared_info` is accumulated context inherited from ancestors plus the caller's new findings. `executor` marks who runs the experiment (`detector`, or `self` for the calling agent). `experiment_id` is the write-back target and the `parent_id` for child experiments.
- Investigation uses the filesystem read/search tools inside `scope`; the `explorer` tool may be called for cross-file reconnaissance inside `scope`, and its findings should be folded into `shared_info`. Temporary experiment scripts may be written, but only into the system temp directory or a `test` directory; source files must not be modified.
- A directly answerable question is written back once with `experiment_update`: `evidence` (standalone fact sentences, supporting or contradicting), `result` (the conclusion answering `question`), and `status` (`confirmed` / `rejected` / `completed`, matching the experiment-state lifecycle).
- A question that is too large is split with `experiment_create` (`parent_id` = own `experiment_id`; child `executor` inherits the parent's; new findings go into `shared_info`), each child experiment is either delegated (its `executor` is `detector`, so `experiment_create` starts the child Detector automatically) or investigated directly, and the collected child verdicts are aggregated into the Detector's own `evidence` and `result` before the write-back.
- `experiment_get` and `experiment_list` are not used; the experiment tree is maintained through the write entries only.

The exact persona text lives in `src/index.ts` and is the contract this README summarizes.

## Recursion and the shared experiment tree

The experiment-state store inside the preset composition is a single instance for the whole recursion: the standing mount applies `dsh-experiment-state` once, and every delegated child joins that same composition through `composeFrom`. A parent Detector therefore sees the child experiments its children wrote back, and the tree grows as one coherent structure. Recursion is bounded by `Config.maxDepth` and the provider's depth enforcement.

## Model Experience

### System prompt

#### What the model sees

The Detector persona replaces the deployment persona for agents on this preset, and the global tool guidance of the host composition remains. The persona text is stable prose; it is not per-request evaluated.

#### Token effect

Fixed per-request cost: the persona section plus the schemas of the visible tools (`delegate_experiment`, `experiment_create`, `experiment_update`, and the inherited filesystem tools). Child Detector conversations are separate sessions and pay their own tokens.

#### KV Cache effect

Prefix-stable for the life of an agent: the preset composition is installed once, before the agent's first request, and is never re-read while the agent runs. A delegate call's structured-output schema is registered in the child's own scope and does not touch the parent prefix.

### Behavior notes

- A child run that does not finish cleanly (cancelled, failed, token limit, refusal) surfaces as a tool error naming the reason; partial child output is not treated as success.
- A child that never commits a structured value reports an error, because the structured-output runtime requires exactly one `structured_output` call to finish.

## Known Limitations and Deferred Work

- **`experiment_get`/`experiment_list` hiding is soft for the root Detector.** Every delegated child gets a hard `toolFilter` deny for the two read tools. A root Detector's own tool set still exposes them (the experiment-state plugin registers all four tools); the persona forbids their use, and a hard hide requires either a configuration option in `dsh-experiment-state` or an agent-scope `ctx.tools.restrict` from the coordinator plugin.
- **The root experiment must be created in the same store as the Detectors.** The store lives in the loading composition (a preset standing mount or the host layer); an experiment created by a separate `dsh-experiment-state` instance is not visible to a Detector's write-back. The coordinator must compose one `dsh-experiment-state` shared by the main agent and its Detectors (CoTracer's `cordis.yml` does exactly this by loading it in the host layer).
- **Temp-script placement is persona guidance, not enforcement.** The agent has write tools; the restriction to temp/test directories is a stated rule, not a runtime gate.
- **No investigation tooling ships in this baseline.** Runtime traces, instrumentation, and other single-agent trace tools are deferred to later versions mounted on this role.
- **No coordinator logic ships here.** Creating the root experiment, choosing `executor`, and aggregating top-level verdicts belong to the coordinating plugin (for example CoTracer), not to this package; this package only provides the Detector role and the executor service.