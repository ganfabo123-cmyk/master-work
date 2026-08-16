# Agent Note: Chinese-thinking system-prompt section

Status: implemented

English | [中文](2026-08-15-think-zh-section.zh.md)

## Problem

For a Chinese/English A/B experiment on how system-prompt and intermediate-output language affect user-visible replies, a caller wants a single toggleable section that directs intermediate reasoning and drafting to Chinese without replacing the persona, harness identity, or the English tool guidance.

## Decision

A new opt-in package [`@deepseek-ai/dsh-think-zh`](../../../../packages/preset/think-zh) registers one **non-complete** `systemPrompt` section (`i18n:think-zh`, order `50`). Because it is not `complete`, it never suppresses other sections: the persona, identity, and tool guidance remain exactly as the composition mounted them. Its only effect is Chinese guidance for non-final model output, which leaves final-answer language to the user's own language.

Mounted inside an agent preset, the section lands in that agent's scope layer and affects only agents joined to the preset. Mounted unscoped, it applies globally.

## Alternatives considered

- **Use `dsh-persona` with `complete: true`** — rejected: complete mode replaces the entire system prompt, removing tool guidance that the experiment wants to keep.
- **Translate the whole prompt and replace it** — rejected as out of scope for this package; that requires covering the identity, web-surface, and deployment-persona sections separately and was deliberately deferred.
- **A global (host-plane) mount** — rejected for the experiment use case, which needs per-preset toggling for clean control groups.

## Consequences

- The section is present only where mounted; it contributes a fixed short Chinese section on every request of an agent whose preset mounts it.
- The A/B control is a filled `standard`-style preset without the row; the treatment adds it. Whether the model obeys the intermediate-language instruction is model-dependent and is exactly what the experiment measures.
- No tool, prompt-variable, or catalog impact: the package registers no tool and no generated-catalog surface.
