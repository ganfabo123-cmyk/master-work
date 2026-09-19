English | [中文](README.zh.md)

# @deepseek-ai/dsh-cotracer

CoTracer is the hypothesis-driven multi-agent debugging (trace)
orchestration plugin. It registers one `cotracer-trace` skill and, through
its `cordis.yml` composition, loads the three infrastructure plugins beside
it: `dsh-explorer-agent` (read-only repo exploration), `dsh-experiment-state`
(shared experiment tree, with the `executor` parameter), and `dsh-detector`
(the investigation subagent plus the shared `experimentExecutor` service).
After loading the skill, the main agent drives the composed tool set itself,
recursively converging from "repository + issue" to a root cause; the skill
guides `ask_user_question` follow-ups when input is incomplete.

## Plugin form

Identical in form to `dsh-cordis-sub-agent`: **one SKILL.md (ordinary catalog
matching; the model loads it when it recognizes a trace task) + a tool set
(contributed by the composed plugins) + program-side glue (composing the three
plugins and wiring the detector executor into `experiment_create`)**. The
plugin itself registers no tools; every tool comes from the composed plugins,
and the model orchestrates by the skill's description — no state machine or
workflow hard-coding.

## Composition

Both `cordis.yml` (for `dsh web --patch`) and `cordis.acceptance.yml` (for
acceptance) load four plugins through `insert:` + `file://` direct URLs:

- `cotracer`: this plugin; registers the `cotracer-trace` skill.
- `explorer-agent`: registers the `explorer` tool (shared by the main agent
  and Detector subagents).
- `experiment-state`: registers `experiment_create` / `experiment_update` /
  `experiment_get` / `experiment_list`; the `executor` parameter of
  `experiment_create` decides who runs the experiment.
- `detector` (`persona: false`): registers only the `delegate_experiment` tool
  and the shared `experimentExecutor` service; it does not register the
  Detector identity section for the main agent.

The main-agent composition does not load the Detector persona, so the main
agent keeps its own identity; each Detector subagent is started by the
executor service with the Detector persona.

## Tools

- `explorer`: asks a read-only Explorer subagent to answer an investigation
  question inside the given directories, returning an evidence-backed answer
  (paths plus semantic findings). Used for reconnaissance and search-space
  narrowing.
- `experiment_create`: creates one experiment. The `executor` parameter:
  - `detector`: the plugin starts a Detector subagent for the experiment
    automatically through the shared service and waits for its write-back
    (status/result/evidence).
  - `self` (default): the experiment is only a record; the caller
    investigates itself and writes back with `experiment_update`.
  A child experiment (with `parent_id`) automatically inherits and appends
  the parent's `shared_info` (accumulated ancestor context plus new findings),
  so similar issues in the same repo are not re-surveyed; it also inherits the
  parent's `executor`, so recursion flows naturally through the main agent or
  detector.
- `experiment_update`: writes back status/evidence/result/shared_info/executor.
- `experiment_get` / `experiment_list`: aggregate the experiment tree so the
  main agent can prune hypotheses and narrow the scope.
- `ask_user_question`: follows up when the repo or issue is missing; ships
  with the standard preset's `tool-ask-user`.

## Skill: cotracer-trace

`skills/dsh-cotracer/SKILL.md` describes the full flow:

1. **Input collection**: require the repo and the issue; if either is missing
   or ambiguous, ask with `ask_user_question` before starting — never guess.
2. **Reconnaissance**: gather initial evidence with `explorer` plus direct
   reads/searches inside the repo.
3. **Hypotheses**: generate 2-4 falsifiable competing hypotheses
   (hypothesis + falsifiable question + scope + shared_info).
4. **Experiments**: `experiment_create` per hypothesis; choose `executor`
   (detector delegates automatically, self investigates directly).
5. **Aggregate**: read the tree with `experiment_get` / `experiment_list`,
   drop or down-weight rejected hypotheses, merge compatible ones, shrink the
   search space, and raise finer-grained hypotheses for indeterminate regions
   in the next round.
6. **Converge**: stop at a root cause when one hypothesis has confirming
   evidence and no (or explained) contradicting evidence.
7. **Output**: root cause + evidence + experiment-tree summary + repair
   suggestion.

## Model Experience

### System prompt

The skill registers as an ordinary runtime skill (`source: 'runtime'`) and can
be loaded once visible; the plugin registers no persona section and does not
change the main agent's identity.

### Token effect

Fixed cost is the tool schemas; `explorer`, `experiment_create` with
`executor: "detector"`, and `delegate_experiment` each start a subagent that
spends its own model budget; the skill body is injected on load. Experiment
result JSON returns into the main agent's context.

### KV Cache effect

No fixed prefix: the plugin appends no per-request text; subagent sessions are
independent.

## Requirements

- `explorer-agent` needs a `subagents` provider with the `toolFilter`
  capability (in-process `spawn`/`fork`) and `read`/`glob`/`grep` tools.
- The detector's executor service and `delegate_experiment` need the
  `subagents` `spawn` provider with `outputSchema` support.
- `experiment-state` must share the process (the experiment tree is process
  memory).
- The dsh web base profile already provides these; the acceptance overlay
  adds them explicitly (see `cordis.acceptance.yml`).

## Known Limitations and Deferred Work

- **The experiment tree is process memory**: experiment state dies with the
  process and is cleared on plugin reload; no cross-session persistence.
- **`executor: "detector"` waits synchronously**: `experiment_create` blocks
  until the Detector (and its recursive children) write back; a long
  investigation occupies one tool call.
- **Scope boundaries are guidance, not enforcement**: the Detector's scope
  restriction is persona/tool-description pressure, as is the main agent's
  own execution; there is no filesystem policy fence.
- **Detector is a read-only baseline**: it carries no runtime trace or
  instrumentation tools; richer investigation tooling can be mounted on the
  same role in a later version.