---
name: codeharness-discover-app
description: Turn a user's vague multi-Agent application idea and supplied domain materials into explicit, reviewable requirements. Use when interviewing a user, reading scripts or rule documents, identifying missing product decisions, and preparing the Requirements section of APP_DESIGN.md before architecture design or coding. Do not use to generate code.
---

# Discover a CodeHarness App

Produce or update `APP_DESIGN.md` from conversation and user-provided materials. Do not inspect repository implementation code and do not write App code.

## Workflow

1. Read every supplied source sufficiently to identify roles, facts, rules, private information, actions, outcomes, and contradictions. Keep source locations for important conclusions.
2. Restate the current understanding in plain domain language. Do not introduce State, Action, Environment, or implementation terminology yet.
3. Separate findings into confirmed facts, proposed defaults, contradictions, and unresolved decisions.
4. Ask only questions whose answers change observable behavior, privacy, completion, or compatibility. Ask a small coherent batch. For each question, recommend one answer and state its consequence.
5. Update the document after every answer. Never silently convert an assumption into a confirmed fact.
6. Finish only when no unresolved decision blocks a deterministic first-stage workflow. Hand off to `$codeharness-design-app`.

## Output

Copy `assets/APP_DESIGN.template.md` to the task workspace if no design document exists. Complete sections 1 through 6 and the source index. Leave architecture sections marked `NOT_DESIGNED`.

Use stable IDs: `AGENT-*`, `PHASE-*`, `ACTION-*`, `INFO-*`, `RULE-*`, `Q-*`, and `AC-*`. Refer to IDs instead of relying on prose names.

For long inputs, read `references/material-analysis.md`. Preserve the user's wording where it defines product behavior.

## Guardrails

- Do not ask the user to translate the domain into framework concepts.
- Do not invent missing rules to make the design look complete.
- Do not expose private source material in a public-information requirement.
- Do not propose code, files, classes, or imports.
- If the requested runtime needs interruption, external waiting, Human approval, nested responses, or realtime ticks, record it explicitly instead of simplifying it without consent.
