# dsh-cordis-sub-agent

English | [中文](README.zh.md)

`dsh-cordis-sub-agent` manages plugin development inside the DeepSeek Harness
monorepo. Each task owns one generated workspace package at
`packages/generated/<plugin-name>/`.

## Development flow

submit_plugin_metadata
  -> task_id
  -> prepare_plugin_reading(task_id)
  -> Read Agent returns a JSON reading plan
  -> Main Agent reads according to the plan, writes, builds/tests, and fixes the same pluginRoot
  -> document_development (Documentation Agent: README files only)
  -> verify_development (foreground engineering commands)
  -> start_acceptance (fresh DSH runtime with temporary acceptance config)
  -> send_acceptance_message
  -> stop_acceptance
  -> permanent integration

`packages/generated/<plugin-name>/` matches the repository's existing
`packages/*/*` workspace glob. The generated package can therefore use
`workspace:*` dependencies after the workspace install is refreshed. Normal
development never edits the root `pnpm-workspace.yaml`.

The canonical ordinary-plugin reference is
`packages/examples/plugin-reference/`. Read it for the standard plugin entry,
config, Tool, service, persistence, lifecycle, test, and documentation shape.
The other packages under `packages/examples/` are architecture references for
agent-spine, ACP, and JSON-RPC composition.

## Tools

- `submit_plugin_metadata`: submits requirement-stage plugin input/output schemas, block-and-arrow execution flow, and detailed plugin document; creates `packages/generated/<plugin-name>/` and returns its in-memory `task_id` and `plugin_root`.
- `prepare_plugin_reading`: accepts only that `task_id`, sends the stored metadata to the read-only Read Agent, and returns its reading plan.
- `get_development_task`: returns the in-process V3 metadata task, reading plan, documentation, verification, acceptance, evidence, and errors.
- `document_development`: invokes the Documentation Agent after Main Agent coding and local checks.
- `verify_development`: runs deterministic foreground typecheck/build/test/documentation checks and returns complete command output.
- `start_acceptance`, `send_acceptance_message`, `stop_acceptance`: run and control the fresh DSH acceptance runtime.
- `discard_development`: stops the acceptance runtime and removes the task-owned pluginRoot. A new task may only claim a plugin directory that did not already exist.

## Ownership and write boundaries

Before acceptance passes, ordinary task writes are limited to the pluginRoot and
Harness-managed temporary acceptance YAML. The Read Agent only investigates and
returns a JSON reading plan. The Main Agent uses that plan to inspect the repository and owns business source
and local build/test repair. The Documentation Agent may modify only
`README.md`, `README.zh.md`, and `README.i18n.yaml` inside the pluginRoot; it
must not modify business source, tests, package configuration, or root files.

Acceptance uses a temporary composition file. A failed acceptance leaves the
same pluginRoot available for Main Agent repair and another verification cycle.
Discard removes the pluginRoot and temporary acceptance resources. A passed
acceptance removes the temporary YAML and moves the task to permanent
integration, where root-level changes are allowed only when the actual DSH
integration requires them.

## Completion requirements

Engineering verification is evidence, not behavioral proof. Completion also
requires successful fresh-runtime acceptance and the required user acceptance
interactions. User acceptance input is forwarded unchanged.

## Model Experience

The Main Agent sees the submitted metadata, Read Agent JSON plan, task facts,
evidence, and tool catalog. It uses the plan to inspect the repository, then
performs implementation, local commands, and repairs directly. The Documentation Agent receives the implementation context
as a one-shot documentation subtask and is restricted to the README triad.

## Known Limitations and Deferred Work

Documentation checks validate structure and command results; they do not judge
translation quality. V3 task facts are process-local, so a DSH restart invalidates
the task id while leaving its generated directory in place.
