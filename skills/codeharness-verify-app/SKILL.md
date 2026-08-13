---
name: codeharness-verify-app
description: Verify a generated first-stage CodeHarness App against its approved APP_DESIGN.md and the bundled public acceptance contract. Use after generation to inspect only the target App, its focused tests, user materials, command results, State, ROOM, and Trace; do not inspect Core, Infra, other Apps, or unrelated tests.
---

# Verify a Generated CodeHarness App

Treat the approved design as expected behavior and the generated App as the implementation under test. Do not inspect forbidden platform or example source to diagnose failures.

## Procedure

1. Confirm the approved revision and target App ID.
2. Read repository-root `.env.example` as the public configuration contract; never read `.env` or print secrets. Run the Generate Skill's `scripts/validate_public_contract.py --repo <repository-root>` before importing the App.
3. Check changed-file scope and imports.
4. Map every acceptance scenario ID to at least one focused test.
5. Run compilation and focused deterministic tests. If `pytest` is unavailable, directly load and execute pure assertion functions only when they require no pytest fixtures/plugins; report pytest as NOT RUN and direct assertions separately. Do not install dependencies without authorization.
6. Run a deterministic Mock policy through the real SessionRuntime/SynchronousAppRuntime using temporary Trace/ROOM roots. Inspect State transition, validation reasons, ToolCall/ToolResult pairing, privacy, ROOM completeness, idempotency, terminal result, Trace status, and phase-boundary restore.
7. Run a real-provider workflow only when the user explicitly requests or authorizes it. Use `.env.example` variable names or explicit injected client/model values. Label Mock evidence and real-model evidence separately.
8. Repair only implementation defects inside the allowed generated scope. A missing product decision returns to design.
9. Produce `VERIFICATION_REPORT.md` or an equivalent concise report using `references/acceptance-contract.md`.

Return `PASS`, `IMPLEMENTATION_FAILED`, `BLUEPRINT_GAP`, or `NOT_VERIFIED`. Never claim end-to-end success from compilation or Mock-only evidence.

## Allowed reads

- approved `APP_DESIGN.md` and cited user materials;
- `src/coworker/apps/<app_id>/`;
- `tests/test_<app_id>_*.py`;
- this Skill's references;
- repository-root `.env.example` and the Generate Skill's public-contract probe;
- focused test output and runtime State/ROOM/Trace artifacts for the generated session.

Do not read Core, Infra, another App, or another App's tests.

Permitted source-free probes are public imports, `inspect.signature`, `dir`/documented attributes, runtime exceptions, focused command output, and generated session artifacts. Do not open platform implementation files to diagnose a contract mismatch; return `BLUEPRINT_GAP` or `IMPLEMENTATION_FAILED` with the failed probe instead.
