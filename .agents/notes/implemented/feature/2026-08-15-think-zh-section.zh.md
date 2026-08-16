# Agent Note: Chinese-thinking system-prompt section

Status: implemented

[English](2026-08-15-think-zh-section.md) | 中文

## Problem

为了一次「中英系统提示 / 中间输出语言如何影响面向用户回复」的 A/B 实验，调用方需要一个可独立开关的段落，让中间推理与草拟使用中文，同时**不替换**人设、harness 身份或英文工具指引。

## Decision

新增可选包 [`@deepseek-ai/dsh-think-zh`](../../../../packages/preset/think-zh)，注册一条 **非 complete** 的 `systemPrompt` section（`i18n:think-zh`，order `50`）。因为它不是 `complete`，因此绝不会抑制其它段落：人设、身份与工具指引保持组合所挂载的样子。它的唯一作用，是针对非最终模型输出的中文引导，而最终答复的语言仍遵循用户所使用语言。

挂进 agent preset 时，段落落在该 agent 的 scope 层，只影响加入该 preset 的 agent；无 scope 挂载则全局生效。

## Alternatives considered

- **用 `dsh-persona` + `complete: true`** — 拒绝：complete 模式会用整段中文提示替换整个系统提示词，从而移除本实验希望保留的工具指引。
- **翻译整段提示词并整体替换** — 拒绝：本包范围之外的刻意延后，需要分别覆盖身份、web 表层与人设段落。
- **host（全局）挂载** — 拒绝：实验需要按 preset 开关以获得干净对照组。

## Consequences

- 段落只在其被挂载处存在；挂载本行的 preset 中，agent 每次请求都会获得一段固定的中文短段落。
- A/B 对照组是不带该行的一个 `standard` 式 preset，处理组加上它。模型是否遵守中间语言指令取决于模型本身，这恰是本实验要度量的内容。
- 无工具、提示词变量或生成目录影响：本包不注册任何工具，也没有任何生成目录表面。
