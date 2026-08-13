---
name: codeharness-generate-app
description: Generate a new first-stage CodeHarness App from an explicitly approved APP_DESIGN.md using the bundled public contract and implementation recipe. Use when creating or modifying only the target App, its domain data, and its tests without reading Core, Infra, existing Apps, or their tests. Stop and return to design when the blueprint is incomplete.
---

# Generate a CodeHarness App

Create the approved App without inspecting `src/coworker/core`, `src/coworker/infra`, any other directory under `src/coworker/apps`, or tests for another App. Do not search those paths. The bundled contract is the complete allowed architecture input.

## Inputs

Require:

- `APP_DESIGN.md` with `design_status: APPROVED`, `review_status: PASS`, no unresolved decisions, and an approval revision;
- all user materials referenced by the design;
- target repository root and App ID.

Read `references/public-app-contract.md` completely before editing. Read `references/implementation-recipe.md` for file ownership and sequence.

Before planning code, read the repository-root `.env.example` as a public configuration contract. This file is an explicit exception to the source-read prohibition. Never read `.env`, print secret values, or copy credentials into code, tests, reports, or Trace.

## Allowed scope

- `src/coworker/apps/<app_id>/`
- `tests/test_<app_id>_*.py`
- App-owned data explicitly named in the blueprint
- `APP_DESIGN.md` only to record implementation status

Do not change Core, Infra, Web discovery, another App, or shared tests. Do not commit Git.

## Procedure

1. Check branch, worktree, target-path existence, and supplied inputs without reading forbidden source paths. Snapshot existing dirty paths with `scripts/check_generation_scope.py snapshot --app-id <app_id> --snapshot <temporary-json>`.
2. Run `scripts/validate_public_contract.py --repo <repository-root>`. It may import public types and inspect runtime signatures but does not read their source. If it fails, stop and report contract drift; do not repair by opening Core/Infra source.
3. Produce a file-level minimal plan derived only from the approved blueprint and contract.
4. Create domain State and pure serialization first.
5. Create closed Action Tools, payloads, Action envelope mapping, availability, and `(valid, reason)` validation.
6. Implement deterministic transitions before Prompts.
7. Create per-Agent Observation projections and visibility rules.
8. Create Policy, Agents, Session resources, Events, ROOM delivery, and runtime entrypoint using the exact construction sequence in the implementation recipe.
9. Generate tests directly from acceptance scenario IDs; each test cites its scenario ID.
10. Run `scripts/check_generation_scope.py check` with the same snapshot, compilation, focused tests, and diff checks. Repair implementation errors without changing approved behavior.
11. If the design cannot determine code behavior, stop. Record the missing decision and return to `$codeharness-discover-app` or `$codeharness-design-app`.

## Generation rules

- Preserve domain names from the blueprint; use Python-safe identifiers only where required.
- Never invent a fallback that changes product behavior.
- Never enforce a rule only through Prompt wording.
- Never let Action Tool functions write ROOM or State.
- Append the assistant Tool Call and its Tool Result to the same Agent context through the public Environment helpers.
- Copy State before transition; do not mutate the input State in place.
- Project complete auditable content to the correct ROOM.
- Keep generated code readable and domain-specific; do not create new generic frameworks.
- Use model variable names and aliases from `.env.example`; do not invent `OPENAI_*` or other configuration names unless that file declares them.
- Public-interface probing is limited to imports, `inspect.signature`, `dir`/documented attributes, and runtime errors. Opening implementation source remains forbidden.

Use `scripts/check_generation_scope.py` before handoff.
