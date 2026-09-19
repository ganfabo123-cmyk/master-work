---
name: swe-bench
description: Guide the agent to work on a local SWE-bench Lite case with the swe-bench tools (swb_list_cases, swb_run, swb_eval) as if it were a local execution environment: read the issue, explore and edit the host case repo with ordinary file tools, run model-written test scripts or commands inside the case's official evaluation container, and verify the fix against the official black-box FAIL_TO_PASS / PASS_TO_PASS tests. Load when the task is to debug, fix, or evaluate one of the local SWE-bench cases.
---

# SWE-bench Case Workflow

Use this skill when debugging or fixing a local SWE-bench Lite case. The
plugin hides Docker entirely; the host case repository is your normal
read/write workspace and only execution goes through the case's official
eval container.

## Input collection

- A SWE-bench case is identified by its `instance_id`
  (e.g. `astropy__astropy-12907`).
- Read the issue from `<repo_path>/issue.md` (or the issue text you were
  given). The case metadata lives in `manifest.json` and per-case `case.json`
  under the benckmark root.
- Call `swb_list_cases` first to see the cases and whether their eval images
  are ready.

## The fix loop

Repeat until `swb_eval` reports `resolved: true`:

1. Understand the bug: read the relevant source in the host repo, run a
   quick `swb_run` reproduction command (e.g. the failing pytest node or a
   small Python probe script you write into the repo) to observe the actual
   faulty behavior. Use `swb_run` for all in-environment execution.
2. Diagnose: trace the responsible code paths, form and test hypotheses with
   your own probe scripts via `swb_run` (full stdout/stderr debug output is
   returned — use it).
3. Fix: edit the host repo source files directly with your file-edit tools.
   The next `swb_run`/`swb_eval` automatically picks up your changes because
   the current host repository state is copied into the container.
4. Self-check: run your own targeted tests/scripts with `swb_run` to confirm
   the fix behaves; iterate on failures.
5. Verify: call `swb_eval` with the same `instance_id`. It applies the
   official test patch inside the container (never shown to you, to keep the
   benchmark honest) and runs the official FAIL_TO_PASS / PASS_TO_PASS nodes,
   returning counts and failing node names.

## Rules

- Never edit files inside the container; edit the host repo only.
- Never attempt to read the official test patch or gold patch — they are
  intentionally withheld (anti-leak); `swb_eval` is the only sanctioned
  official verdict.
- Do not fabricate docker commands; use the plugin tools.
- A case is done when `swb_eval` returns `resolved: true` (all FAIL_TO_PASS
  passed, no PASS_TO_PASS regression).

## Output

Report per case: the root cause, the applied fix (files changed), the
self-check evidence (`swb_run` outputs), and the final `swb_eval` verdict.