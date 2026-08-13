# Acceptance contract

Report each item as PASS, FAIL, or NOT RUN with evidence.

| Area | Required evidence |
|---|---|
| Scope | changed paths are limited to approved App/data/tests |
| Public contract | runtime signature probe passes; configuration names match `.env.example`; no secrets are printed or persisted |
| Imports | target modules compile and public imports resolve |
| State | initial, round-trip, transition, terminal, consumed IDs |
| Observation | included information and explicit private exclusions per Agent |
| Action | parsing, availability, valid case, each designed rejection reason |
| Transition | every phase contract and collection rule |
| Pairing | assistant Tool Call followed by matching Tool Result in same context |
| ROOM | complete content, correct room/recipient/release time |
| Idempotency | repeated Action or recovery does not duplicate domain effect |
| Recovery | persisted phase resumes and reaches expected result |
| Trace | actual messages and lifecycle status are recorded |
| Real model | provider, session ID, final State, only if actually run |

Evidence labels:

- `STATIC`: compilation/import/signature evidence only.
- `DIRECT_ASSERTION`: focused pure assertions executed without pytest collection.
- `MOCK_RUNTIME`: deterministic policy exercised through real session/runtime/ROOM/Trace/storage components.
- `REAL_MODEL`: an authorized provider call with recorded provider, model, session ID, State, ROOM, Trace, and Tool pairing.

`MOCK_RUNTIME` may support overall PASS when all approved deterministic behavior is covered and real-model execution was not required. It must never be described as real-provider or full live-model success. If pytest is missing, report both `pytest: NOT RUN` and the exact direct-assertion evidence; do not silently call them pytest results.

Final report:

```text
Result: PASS | IMPLEMENTATION_FAILED | BLUEPRINT_GAP | NOT_VERIFIED
Blueprint revision:
Files inspected:
Commands run:
Scenario results:
Mock verification:
Real-model verification:
Known limits:
```
