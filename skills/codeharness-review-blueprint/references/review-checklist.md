# Review checklist

## Requirements

- Every participant, phase, Action, privacy rule, edge case, and terminal result is explicit.
- No unresolved item changes observable behavior.
- Proposed defaults are user-confirmed.

## Semantic closure

- Every nonterminal phase selects known Agents or declares deterministic automatic handling.
- Every selected Agent has one Observation projection and at least one available Action.
- Every Action has structured parameters, availability, validation failures, and payload mapping.
- Every phase defines collection, resolution, transition, and next phase.
- Every terminal path stores a final result.

## Boundaries

- Agents read only Observation.
- Action Tools express intent and do not change State or ROOM.
- `validate_action` returns validity plus actionable reason.
- Environment performs all domain effects.
- No Human/external wait, response window, nested Action, or realtime tick is hidden inside `step()`.

## Audit and privacy

- Every meaningful Action/artifact/result has a complete ROOM projection.
- Every projection names recipients and release time.
- Private material is excluded from unauthorized Observations and ROOMs.
- State, Event, delivery, and display roles are not conflated.

## Acceptance

- Normal completion, invalid Action, privacy, duplicate Action, terminal condition, and phase-boundary recovery have scenarios.
