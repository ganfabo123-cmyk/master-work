---
name: dsh-plugin-development
description: Guide a Main Agent to develop and verify a DeepSeek Harness plugin using Cordis task tools when a plugin request requires auditable repository work.
---

# DSH Plugin Development

This skill is only for the Main Agent. Cordis provides tools that record
auditable facts about one generated-plugin task; the Main Agent decides what
ordinary repository reading, writing, repair, and foreground commands are
needed. Do not treat the tools as a mandatory state machine.

## Why use this skill instead of writing the plugin directly?

Directly writing a plugin from the first user message is often locally fast but
globally unreliable: the requirement may be incomplete, repository knowledge
may be missing, and a passing local command may not describe the user's real
experience. This skill tells the Main Agent when Cordis can turn those unknowns
into explicit, reviewable facts without taking away the Main Agent's judgment.

- A user may describe an incomplete or ambiguous need. Before implementation,
  `submit_plugin_metadata` makes the plugin contract, input/output fields, and
  intended execution flow explicit, so requirement drift becomes visible
  before it turns into source changes. For a complex or unclear need, the Main
  Agent should use `ask user` to resolve material ambiguity before submitting
  that contract.
- An Agent may not know every task-relevant file, nearby convention, dependency,
  or project constraint. Start with
  `docs/dsh-develop-cordis-map.md` to learn the repository map and the available
  development tutorials. Then select the relevant documentation, existing
  plugin, package, or example from that map and read only the files needed for
  the current plugin. Before using `read`, it is recommended to call
  `what i want to know` to list the information the Agent wants to learn and
  why it matters. Use that list to guide repository exploration and avoid
  getting trapped in a local-reading illusion. Do not replace this targeted
  repository reading with a generic whole-repository scan.
- Plugin documentation is routine but consumes context and is easy to make
  inconsistent across its required README files. `document_development`
  delegates that narrow, bounded work while leaving implementation ownership
  with the Main Agent. Run it for the first complete implementation and after
  repaired behavior passes acceptance; do not put it inside every code-repair
  loop.
- A single local command or one-sided static analysis can miss interactions and
  lead to a repair loop that fixes one symptom while breaking another.
  `verify_development` runs the complete deterministic engineering gate after
  implementation, producing one evidence set for structure, typecheck, build,
  optional tests, and documentation rather than scattered guesses.
- Passing engineering checks does not prove that a user can use the plugin in a
  real DSH host. `start_acceptance` and `send_acceptance_message` exercise the
  verified artifact in a fresh DSH runtime; `stop_acceptance` records whether
  the acceptance evidence actually supports the final claim.

The goal is not to prevent direct coding. The Main Agent still reads, writes,
repairs, and chooses the next action. The goal is to require the right tool
when it reduces a known source of requirement, repository, documentation,
engineering, or user-experience error.

## When to use each tool

| When | Cordis provides | Main Agent guidance |
| --- | --- | --- |
| The user has confirmed a plugin's purpose, input/output fields, execution blocks and arrows, and detailed document | `submit_plugin_metadata` creates a V3 task and its task-owned `packages/generated/<plugin-name>/` directory | **Must** call it before asking Cordis to generate documentation, verify, accept, query, or discard this plugin. Repository navigation is performed by the Main Agent through `docs/dsh-develop-cordis-map.md` and ordinary targeted reading. Keep its returned `task_id` and `plugin_root`. Every schema field, block, and arrow needs a non-empty description. For a complex or unclear request, **strongly recommend** using `ask user` for multi-turn clarification, then showing the proposed purpose, inputs, outputs, and brief flow to the user; submit only after the user confirms that metadata. |
| You need task-specific repository facts before deciding what to implement | The repository map, selected documentation, and selected existing plugin or example files provide the reading path | **Need** to read `docs/dsh-develop-cordis-map.md` first. Use its document links to learn the relevant Cordis and Harness concepts, then use its `packages/` and `examples/` branches to choose comparable implementations. Read exact files, manifests, prompts, tools, tests, and configuration only when they are relevant to the current plugin. |
| Context is incomplete, a tool failed, the user asks for progress, or you need evidence before deciding the next action | `get_development_task(task_id)` returns V3 metadata, documentation, verification, acceptance, evidence, errors, and `plugin_root` | **Recommend** calling it to recover task facts instead of guessing. It is read-only and does not advance development. |
| The first complete implementation and English README are ready, or repaired behavior has passed acceptance and its final documentation now needs synchronization | `document_development(task_id)` runs `translate_readme_agent`, then generates the i18n sidecar | **Need** to call it before the first formal engineering verification, then call it once more after a repair cycle only when the accepted behavior requires README updates. Do not call it between each code repair and verification attempt. The translator reads only `README.md` and writes only `README.zh.md`; the parent tool runs `pnpm run verify-translation-pairing --write <pluginRoot-relative>/README.md` to generate `README.i18n.yaml`. The Main Agent remains responsible for source, the English README, tests, package configuration, and repairs. |
| You need deterministic evidence that the plugin builds and satisfies its contract | `verify_development(task_id)` performs structure, typecheck, build, optional test, and documentation checks | **Need** to call it after the first implementation and documentation are ready. Inspect every returned check and command result. If verification or acceptance exposes a bug, repair the same `plugin_root` with ordinary tools and call `verify_development` immediately, without first revising README files or rerunning `document_development`. |
| You need real fresh-DSH behavior after successful engineering verification | `start_acceptance(patch)` starts an isolated runtime from the Cordis patch selecting the plugin | **Must** call it before acceptance messaging. Provide the patch path, keep the returned `acceptance_id`, and use that id with `send_acceptance_message` and `stop_acceptance`. |
| You need to exercise a running acceptance runtime | `send_acceptance_message(acceptance_id, actor, message)` sends an input directly to fresh DSH | **Strongly recommend** using realistic acceptance inputs. For `actor="user"`, forward the user's input unchanged. This tool accepts `acceptance_id`, not `task_id`. |
| Acceptance is complete, failed, or must be stopped | `stop_acceptance(acceptance_id, final_status)` closes the runtime and records its conclusion | **Must** call it to close a started acceptance runtime. Mark `passed` only when both required automated and user-originated completed interactions exist; otherwise use `failed` or `stopped`. |
| The user explicitly abandons the plugin task | `discard_development(task_id)` stops its active runtime and removes the task-owned generated directory | **Must** call it instead of deleting the directory manually. Do not use it for an ordinary repair cycle. |

### Initial development and later repair order

Use the full documentation-first sequence for the first complete candidate:

1. Implement the source, tests, package configuration, and initial English
   README.
2. Call `document_development(task_id)` to complete the translated README and
   i18n sidecar.
3. Call `verify_development(task_id)`.
4. After verification succeeds, run the `start_acceptance` interaction and
   close it with `stop_acceptance`.

After verification or acceptance reveals a bug, switch to a focused repair
loop:

1. Repair the code, tests, or package configuration needed for that bug.
2. Call `verify_development(task_id)` directly. Do not update README files or
   call `document_development` before this verification attempt.
3. After verification succeeds, run acceptance again.
4. If verification or acceptance still fails, repeat this repair loop without
   documentation work.
5. Only after acceptance passes, update the English README to match the final
   accepted behavior and call `document_development(task_id)` once to
   synchronize `README.zh.md` and `README.i18n.yaml`.

Documentation synchronization after successful acceptance does not by itself
require another engineering-verification or acceptance cycle. Start another
cycle only if that final documentation work also changes source, tests, package
configuration, or runtime behavior.

## Main Agent boundaries

- Preserve the original `task_id` and `acceptance_id`; never invent, transform,
  or substitute identifiers.
- Use ordinary read/write tools and finite foreground commands for source
  development and repair. Cordis does not provide a separate Coding Agent or a
  mandatory implementation wrapper.
- Before repository investigation, read
  `docs/dsh-develop-cordis-map.md`. Follow its links to the documentation that
  matches the plugin's capability, then inspect the corresponding existing
  package or example. Prefer a small set of directly relevant files over a
  broad recursive read; record the selected paths and the reason each path is
  relevant in the development trace or task notes.
- Keep ordinary task writes inside `plugin_root` unless the user explicitly
  authorizes a wider repository change. Generated-plugin work does not imply
  permission to edit root workspace configuration.
- During plugin development, use `user_powershell` for commands that must run
  in the DSH project's PowerShell environment, especially dependency
  installation or mutation (`pnpm install`, `pnpm add`, `npm install`), build
  commands, and starting or inspecting child processes. Always provide the
  exact `command` and a specific `reason`; the user-facing permission prompt
  must show both before anything runs. Do not use the ordinary `pwsh`/`bash`
  tool for these commands, do not background them, and do not retry a denied
  command through another tool. The `user_powershell` tool runs with cwd set to
  the current DSH project root and returns stdout, stderr, and the exit code.
- Treat verification and acceptance as separate evidence: a successful build
  is not fresh-runtime proof, and an acceptance runtime cannot start without a
  successful V3 verification result.
- V3 tasks are process-local. After DSH restarts, their ids and acceptance
  runtimes are unavailable while generated directories remain on disk; do not
  claim that a previous task can be resumed without a current task record.
