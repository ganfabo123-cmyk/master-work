---
name: cotracer-trace
description: Guide the agent to run hypothesis-driven multi-agent debugging (trace) on a repository with an issue, using the explorer, experiment, and detector tools: explore the repo, raise falsifiable hypotheses, run experiments (optionally delegated to Detector subagents), aggregate the experiment tree, and converge on a root cause. Load when the user provides a repo/issue and asks to debug, trace, investigate, or root-cause a bug, or when a task clearly needs recursive evidence-driven debugging.
---

# CoTracer: Hypothesis-Driven Multi-Agent Debugging

Run this skill when debugging a repo issue by hypothesis-driven multi-agent
trace. The agent orchestrates; the plugin provides tools and the skill provides
the process. Do not hard-code a state machine: call the tools freely in the
order the evidence requires.

## Input collection

- Required: a repository path/directory and an issue description (error text,
  failing test, logs, observed behavior).
- If either is missing or ambiguous, call `ask_user_question` (ask the user)
  to fill it in before starting. Never guess the repo or invent issue details.
- Record the repo scope: it is the root investigation boundary for every
  experiment's `scope`.

## The trace loop

Repeat rounds until the root cause is established with enough evidence:

### 1. Reconnaissance (explorer + direct reads)

- Call `explorer` with `directories` (sub-scopes of the repo relevant to the
  issue) and a `question` asking for evidence-backed findings about where the
  fault could live. The Explorer subagent submits paths and semantic findings.
- Read/glob/grep as needed to verify claims the explorer returned.
- Do not modify source files; temporary probe scripts go to system temp or a
  `test` directory only.

### 2. Hypotheses

- From the reconnaissance, write 2-4 competing, falsifiable hypotheses about
  the fault cause. Each hypothesis needs:
  - `hypothesis`: the suspected cause (background, not conclusion).
  - `question`: a falsifiable question whose answer distinguishes it.
  - `scope`: the directories/files the investigation may look at.
  - `shared_info`: context accumulated so far (for example what the explorer
    found); children inherit and append it automatically, so deeper
    investigations never re-survey what ancestors already covered.

### 3. Experiments (executor choice)

For each hypothesis call `experiment_create` and choose `executor`:

- `executor: "detector"` — the plugin automatically starts a Detector
  subagent for this experiment. The Detector reads inside `scope`, writes
  evidence back, and if the question is too large it recursively splits child
  experiments (inheriting `executor` and the accumulated `shared_info`) and
  delegates them to child Detectors automatically. Wait for its write-back.
- `executor: "self"` (default) — the experiment is a self-reflection record:
  investigate it yourself with the repo tools, then `experiment_update` the
  evidence, result, and status (`confirmed` / `rejected` / `completed`).

Choose `detector` for broad/scoped investigation questions and `self` for
small questions you can answer directly in a few reads.

### 4. Aggregate

- `experiment_get` / `experiment_list` to read the experiment tree: statuses,
  evidence, results, and child experiments.
- Drop or down-weight rejected hypotheses; merge compatible ones; shrink the
  search space to the surviving scope; raise finer-grained hypotheses and new
  rounds where evidence is indeterminate.

## Convergence

- Stop when one hypothesis has confirming evidence and the contradicting
  evidence is empty (or explained). Record it as root cause.
- If the tree is inconclusive after several rounds, do not force a verdict:
  report the leading hypothesis with its residual uncertainty.

## Output

Report to the user:
- `root_cause`: the root cause with the reasoning trail.
- `evidence`: the supporting facts (from the experiment tree).
- `experiment_tree` summary: round count, hypotheses tried, rejected/confirmed.
- `repair_suggestion`: the concrete fix if one follows from the root cause.