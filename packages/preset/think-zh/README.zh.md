# dsh-think-zh

[English](README.md) | 中文

一条引导中间推理与草拟使用中文的系统提示词段落。它只贡献一段非 complete 的部分，完全不动其它段落——包括 harness 身份、人设以及英文工具指引。它是为中英对照实验准备的轻量配套，而不是提示词替换。

## 聚焦的范围

这段刻意设置为 **not** complete。它与人设覆盖相反：既不遮蔽 `deployment:persona`，也不抑制 `harness:identity`，更不删除工具指引。它的唯一作用是一条关于"非最终模型输出语言使用中文"的中文指令。把它挂进 agent preset，使其落在该 agent 的 scope 层；在无 scope 上下文挂载则会全局生效，虽可行但会扩大到每个 agent。

## Section

| 字段 | 值 |
|---|---|
| name | `i18n:think-zh` |
| order | `50`（在人设 `0` 之后、工具指引 `100+` 之前） |
| complete | `false` |

中文文本要求逐步推演、草拟与中间笔记使用中文，而面向用户的最终答复继续遵循用户使用的语言。

## 模型体验（Model Experience）

### think-zh 段落

#### 模型看到的内容

一段中文散文，指示中间推理与草拟使用中文。它只约束非最终的模型输出语言，不改变人设、身份或工具指引的语言。

#### Token 影响

对挂载本行的 preset 中的 agent 而言恒定：该 agent 的每个请求都携带一小段 token，其它 agent 无。

#### KV Cache 影响

对 agent 生命周期前缀稳定——该行在 agent 首次请求之前挂载一次，运行期间文本不变。

## 已知限制与待办事项（Known Limitations and Deferred Work）

- **不影响最终答复语言** — 指令区分中间输出与面向用户的答复，模型是否遵守取决于模型本身，最好用本包为之存在的 A/B 实验来度量。
