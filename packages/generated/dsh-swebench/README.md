English | [中文](README.zh.md)

# @deepseek-ai/dsh-swebench

Encapsulate the local SWE-bench Lite cases' Docker runtime environments
behind three high-level tools plus a workflow skill, so a tracing agent like
cotracer works against the cases as if they were a local execution
environment: read and edit the host case repo with ordinary filesystem
tools, run any command or model-written test script inside the case's real
evaluation container with `swb_run`, and verify the fix with the official
black-box FAIL_TO_PASS / PASS_TO_PASS verdict via `swb_eval`.

The plugin owns all Docker specifics — image tags, read-only bind mounts,
throwaway `--rm` containers, conda activation, `git apply --no-index`, and
CRLF defense — so the model never sees them. The host repository is the
read/write workspace; only execution goes through Docker.

## Plugin form

Function plugin registering three tools (`swb_list_cases`, `swb_run`,
`swb_eval`) and one runtime skill (`swe-bench`), composed through
`cordis.yml`. Requires the `subprocess` service (runs the docker CLI) and the
standard `tools` / `skills` services; the dsh web base profile provides all
three.

## Tools

### swb_list_cases

Lists the local cases (from the benchmark `manifest.json`): `instance_id`,
host repo path, base commit, derived eval image tag, whether that image is
present locally, and the repo's official test runner (`pytest` for Astropy,
`runtests` for Django).

### swb_run

`swb_run(instance_id, command, workdir?)` copies the current host repository
state (including files the agent just wrote or edited) into the container,
activates the case conda environment, and runs `command` in `workdir`
(default `/testbed`). Returns the complete `stdout`, `stderr`, and
`exit_code`. Use it to run the case's tests, a probe script, or any Python
or shell command against the real environment. It never touches the official
gold or test patch.

### swb_eval

`swb_eval(instance_id)` runs the official SWE-bench verification
black-box. Inside the container it fetches the instance's official
`test_patch` (curl, never leaving the container), applies it to the copied
repo with CRLF defense + `git apply --no-index`, and runs every
FAIL_TO_PASS and PASS_TO_PASS node through the repo's official runner.
Returns structured counts per group, the failing test node names, and a
`resolved` flag (all FAIL_TO_PASS passing, no PASS_TO_PASS regression).
Test source and assertion details are deliberately withheld to keep the
benchmark honest; debug your own scripts with `swb_run` instead.

## Skill: swe-bench

`skills/swe-bench/SKILL.md` describes the fix loop: read the issue, explore
and edit the host repo, repro and debug with `swb_run`, then verify with
`swb_eval` until `resolved: true`. The skill is an ordinary runtime skill; a
tracing agent loads it when it recognizes a SWE-bench case task.

## Configuration

```yaml
plugins:
  swebench:
    casesRoot: 'D:\PycharmProjects\CodeHarness\github_rep\swe-bench-lite-10'
```

`casesRoot` is the benchmark root holding `manifest.json`; it defaults to the
path above. The registry is rebuilt on every tool call, so a changed
`casesRoot` or an updated manifest takes effect without a plugin reload.

## Prerequisites

- Docker daemon reachable from the dsh web host, with the case eval images
  pulled. Image tags follow the official convention
  `swebench/sweb.eval.x86_64.<instance id with __ → _1776_>:latest`.
- The benchmark manifest at the configured `casesRoot`; each case repo is a
  Windows git detached worktree checked out at its `base_commit` with
  `core.autocrlf=true` (CRLF files). The plugin handles that layout in the
  container: the host repo is mounted read-only at `/host-testbed`, copied
  into `/testbed` excluding `.git`, and patches are applied with `git apply
  --no-index` after CRLF defense.
- `swb_eval` needs container-side network access to the SWE-bench dataset
  endpoint (the host may be offline); `swb_run` needs none.

## Model Experience

### System prompt / tools

The model sees the three tool schemas and can load the `swe-bench` skill.
There is no persona section; the agent keeps its own identity.

### Token effect

Fixed cost is the tool schemas. `swb_run` returns the full command output
(debug information is not truncated); `swb_eval` returns only counts and
failing test names, so a long official run adds little prompt text.

### KV Cache effect

No fixed prefix: the plugin appends no per-request text.

## Known Limitations and Deferred Work

- Each tool call starts one throwaway container: there is a fixed cold-start
  cost per call, and a `swb_eval` run with dozens of test nodes can still take
  minutes.
- `swb_eval` fetches only the 10-row Lite page (offset 0, length 10) of the
  dataset endpoint; cases outside that window are not resolvable.
- The eval verdict counts per node from the official runner's output: Astropy
  nodes are judged by a per-node `pytest -q <node>` exit code, Django nodes by
  parsing one batched `runtests.py` run; collection-wide flakiness (e.g.
  environment-dependent Django locale) is reported as failed nodes rather
  than retried.
- Astropy FAIL_TO_PASS / PASS_TO_PASS nodes run one by one (`pytest -q
  <node>`, one process each); Django nodes run as one batched
  `python tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1
  <module labels>` invocation per eval, mirroring the official eval script.
- The host repo is the source of truth: container edits are never written
  back (the container is read-only on the host mounts); edits must happen on
  the host side.