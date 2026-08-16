# dsh-think-zh

English | [中文](README.zh.md)

A single system-prompt section directing intermediate reasoning and drafting to Chinese. It contributes one non-complete section and leaves every other section — the harness identity, the persona, and the English tool guidance — untouched. It is the lightweight companion for an A/B language experiment, not a prompt replacement.

## Focused scope

The section is deliberately `not` complete. It is the opposite of a persona override: it does not shadow `deployment:persona`, does not suppress `harness:identity`, and does not remove tool guidance. Its only effect is one Chinese instruction about the language of intermediate, non-final model output. Mount it inside an agent preset so it lands in that agent's scope layer; mounting in an unscoped context still adds the section globally, which is fine but widens the effect to every agent.

## The section

| Field | Value |
|---|---|
| name | `i18n:think-zh` |
| order | `50` (after the persona at `0`, before tool guidance at `100+`) |
| complete | `false` |

The Chinese text asks that step-by-step reasoning, drafting, and intermediate notes be written in Chinese, while the final user-facing reply keeps following the user's own language.

## Model Experience

### The think-zh section

#### What the model sees

One Chinese prose section instructing that intermediate reasoning and drafting use Chinese. It constrains the language of non-final model output only; it does not change the persona, identity, or tool guidance language.

#### Token effect

Fixed for an agent whose preset mounts this row: one short section's tokens on every request that agent makes, and none for any other agent.

#### KV Cache effect

Prefix-stable for the life of an agent — the row mounts once before the agent's first request, and its text never changes while the agent runs.

## Known Limitations and Deferred Work

- **No effect on final-answer language** — the instruction distinguishes intermediate output from the user-facing reply; whether the model obeys is model-dependent and best measured by the A/B experiment this package exists to enable.
