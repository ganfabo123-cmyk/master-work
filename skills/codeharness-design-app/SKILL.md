---
name: codeharness-design-app
description: Convert confirmed multi-Agent domain requirements in APP_DESIGN.md into a complete first-stage CodeHarness architecture blueprint covering State, Observation, Policy, Action, validation, Environment transitions, Events, ROOM visibility, recovery, and acceptance. Use after requirements discovery and before code generation. Do not write application code.
---

# Design a CodeHarness App

Read `APP_DESIGN.md` and user materials referenced by it. Do not inspect Core, Infra, existing Apps, or tests. Do not generate code.

## Required semantic mainline

```text
State -> select_agents -> Observation -> Policy -> Action
-> ready_to_step -> resolve_actions -> Environment.step
-> Event/ROOM -> New State
```

## Procedure

1. Reject design work if requirements are not confirmed or blocking questions remain.
2. For every phase, complete one phase contract using `references/blueprint-contract.md`.
3. Derive State by asking what facts must survive process termination to resume at a phase boundary. Store large source bodies by reference, not duplicated text.
4. Derive Observation as an explicit per-Agent projection. Full State is never an Observation.
5. Derive Action only from participant intent. Automatic phase progression, counting, dealing, truth checks, and settlement belong to Environment.
6. Specify `available_actions` and every rejection reason. Validation success and reason are one result.
7. Specify atomic deterministic transitions and action-collection completion.
8. Map every meaningful Action, artifact, and state result to complete ROOM content with visibility.
9. Add normal, invalid-action, privacy, idempotency, terminal, and recovery acceptance scenarios.
10. Update `APP_DESIGN.md` sections 7 through 10. Set `design_status: READY_FOR_REVIEW`; do not approve it.

Use the exact tables from `references/blueprint-contract.md`. IDs must point back to requirements IDs.

## First-stage boundary

The design fits only when selected LLM Agents act synchronously, Actions are finite and structured, all required Actions can be collected, and one `step()` immediately produces New State without external waiting.

If a requirement needs Human waiting, an external job, action interruption, nested response windows, or realtime ticks, mark `OUT_OF_STAGE_ONE` and present a faithful first-stage simplification only as an option requiring user approval.

## Guardrails

- Keep roles, phases, prompts, rules, domain tools, and outcomes inside the App design.
- Never use Prompt text as the only enforcement of permission or transition rules.
- Action Tools describe intent and have no ROOM or State side effects.
- Environment alone changes domain State and projects domain effects.
- Do not change confirmed product behavior while mapping it to architecture.
