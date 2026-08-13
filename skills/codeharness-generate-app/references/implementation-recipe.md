# Implementation recipe

Create only files needed by the approved design. The normal layout is:

```text
src/coworker/apps/<app_id>/
  __init__.py
  state.py
  action.py
  observation.py
  policy.py
  agent.py
  environment.py
  data_loader.py        # only when blueprint names source data
  example.py            # optional programmatic entry
tests/
  test_<app_id>_rules.py
  test_<app_id>_workflow.py
```

Implementation order:

1. Run the public-contract probe and read `.env.example`; record declared model variables without reading secret values.
2. Domain enums/value objects and State round-trip, including consumed Action IDs, emitted Event IDs, and explicit terminal phase/result.
3. Action Tools with `agent_name`, payload envelope, parsing, availability, validation, aggregation, and exact Environment feedback-helper calls.
4. Pure copy-on-transition functions, automatic phases, score/settlement, and terminal paths.
5. Observation projections with explicit exclusions.
6. Events and deliveries for every blueprint mapping, including initial private material, private clue delivery, complete public content, and persisted idempotency.
7. Prompt, Policy, Agent composition with distinct Policy and Action tool ownership.
8. Session open/restore in the exact public-contract order; inject `llm`/`model` for tests and use `.env.example` names for normal startup.
9. Synchronous runtime entrypoint using `SessionRuntime.run(environment, ...)` and `SynchronousAppRuntime().run(environment, app_session)`.
10. Tests named after acceptance IDs.

Keep source materials outside Python when large. Store stable IDs/references in State and load only authorized content into an Observation.

Before handoff, exercise one deterministic Mock policy through the real SessionRuntime and SynchronousAppRuntime with temporary Trace/ROOM roots. This is stronger than pure transition tests but is still Mock evidence. Assert terminal State, public/private ROOM content, same-context ToolCall/ToolResult pairing, Trace completion, phase-boundary restore, and stable-event replay prevention.
