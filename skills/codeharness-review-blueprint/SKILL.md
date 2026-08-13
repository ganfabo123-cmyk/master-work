---
name: codeharness-review-blueprint
description: Audit APP_DESIGN.md before implementation for requirement traceability, complete State/Observation/Action/Environment semantics, privacy, ROOM projection, deterministic first-stage execution, recovery, and acceptance coverage. Use to return PASS, NEEDS_REVISION, or OUT_OF_STAGE_ONE and obtain explicit user approval. Do not generate code.
---

# Review a CodeHarness App Blueprint

Review only the design document and its cited user materials. Do not inspect repository implementation code and do not write code.

## Audit

Apply every item in `references/review-checklist.md`. Trace each finding to a document heading, ID, or missing required row.

Return exactly one result:

- `PASS`: complete, internally consistent, first-stage compatible, and ready for user approval.
- `NEEDS_REVISION`: fixable missing or contradictory design information.
- `OUT_OF_STAGE_ONE`: faithful behavior requires waiting, interruption, nesting, or realtime scheduling.

For each failure, provide the smallest correction and identify whether the user must decide or the designer can repair it from confirmed facts. Do not silently edit a product decision.

When the result is `PASS`, show a concise approval card covering participants, phases, privacy, Actions, terminal result, explicit simplifications, and acceptance scope. Ask the user to approve this exact revision. Only after explicit approval update:

```yaml
design_status: APPROVED
review_status: PASS
requirements_confirmed: true
blueprint_approved: true
approved_revision: <stable revision identifier>
```

Hand the approved document to `$codeharness-generate-app`.

Run `scripts/validate_app_design.py APP_DESIGN.md --approved` after recording approval. This structural check complements, but does not replace, the semantic audit.
