# 错误码类的三组 Skill 提取入口

本轮范围是 **14 个原始轨迹错误码类**，不是异常类型或标准消息类。每类重新执行 A/B/C 三组，共 42 个独立实验，包括此前已经跑过的 `ms-linker:LNK1105`。不同实验没有共享对话，也不读取历史 Skill 输出。默认按错误类、A/B/C 顺序执行，便于复现和记录。

## 填配置并运行

文件路径均相对于仓库 `dynamic-trace-segmentation-clustering`。只需要 Python 标准库，不需要安装 SDK。

已创建待填写的 [本地配置](./error_skill_extraction.local.json)，三个字段留空：

```json
{
  "api_key": "",
  "base_url": "",
  "model": "",
  "sessionHeader": "x-opencode-session",
  "userAgent": "skill-extraction/1.0",
  "timeout_seconds": 600,
  "max_requests": 100,
  "max_output_tokens": 16000,
  "output_token_parameter": "max_tokens",
  "temperature": null,
  "extra_body": {}
}
```

本地配置文件已加入 Git 忽略规则；可共享的空白模板是 [config.example.json](./error_skill_extraction.config.example.json)。接口协议是 OpenAI 兼容的 Chat Completions，`base_url` 填服务商提供的 API 根地址（例如包含 `/v1`），脚本追加 `/chat/completions`。也可直接填完整 `/chat/completions` 地址。服务必须支持 `tools`、`tool_calls`、`role=tool` 和 `tool_choice=auto`；不把正文 JSON 当作工具调用退路。

`sessionHeader` 指定请求头名称：配置为 `x-opencode-session` 时，脚本会为每个“错误类 × 输入方案”的提取尝试生成独立 UUID，并通过该 HTTP 头发送；同组各轮请求使用同一个值，各组之间隔离。名称和值记录在 `api-session.json` 和组摘要中，不放进请求 JSON body。续跑失败实验会归档原 Session 记录，新尝试生成新 ID。服务不需要该头时可以删除字段或设为 `""`；不会影响没有此字段的旧配置。

正式提取请求默认发送 `User-Agent: skill-extraction/1.0`；配置中没有 `userAgent` 时也自动使用该值，无需修改现有配置。可用该字段指定自己的客户端名称。服务端 HTTP 错误会打印到终端并保存在失败摘要中，正文最多 4096 字节、经过 key/Bearer 脱敏，不再只显示 `failed`。

填写后，在仓库根目录执行：

```powershell
python -X utf8 master_work/experiments/trace-segmentation/dynatic-split-session-test/error_skill_extraction.py
```

默认输出是外层工作目录 `C:/Users/35153/PycharmProjects/master-work/skill-runs/<本地时间戳>/`，使用较短路径避免 Windows 文件名长度限制。每次正常运行创建新目录，全部 14 类重新提取，既有实验不覆盖。

也可以指定输出：

```powershell
python -X utf8 master_work/experiments/trace-segmentation/dynatic-split-session-test/error_skill_extraction.py `
  --output C:/Users/35153/PycharmProjects/master-work/skill-runs/error-code-run1
```

续跑同一个目录：

```powershell
python -X utf8 master_work/experiments/trace-segmentation/dynatic-split-session-test/error_skill_extraction.py `
  --resume `
  --output C:/Users/35153/PycharmProjects/master-work/skill-runs/error-code-run1
```

完成的实验跳过；失败实验的请求、响应、成本归档到 `attempts/attempt-NNN/` 后重跑，消耗仍计入总成本。输入快照、提示词、工具定义、模型和 API 设置变化时拒绝续跑，应另建输出目录。API key 可以更新而不改变实验配置。进程被强制终止后可能只有部分请求日志，续跑会保留已知 usage，未收到 usage 的请求记为未知。没有自动网络重试，避免隐形重复请求。

纯本地准备，不填 key、不联网：

```powershell
python -X utf8 master_work/experiments/trace-segmentation/dynatic-split-session-test/error_skill_extraction.py `
  --prepare-only `
  --output C:/Users/35153/PycharmProjects/master-work/skill-runs/error-code-prepare1
```

在该准备目录调用 API，需要 `--resume --output <同一目录>`。

## 输入到输出

```text
14 个原始错误码类的 groups.json
→ 每类取 member_session_ids
→ A：无损复制对应原始 Session
→ B：group-context 选择完整切片
→ C：选中切片保持完整，其余切片隐藏 Thinking/Tool Result 正文
→ 每组独立的本地文件读取工具 + 同一提取提示词
→ response 工具提交全部 Skill 和放弃原因
→ 结构、原始坐标、引用原文与可见验证结果检查
→ skills.json + 每 Skill 的 SKILL.md/skill.json + 全局索引 + token/时间日志
```

上游聚类主入口是同目录的 `strategy_clustering.py`；错误码只是当前用于 Skill 提取的典型分组策略。

默认输入：

- 分组：`master_work/experiments/trace-segmentation/dynatic-split-session-test/error-clustering-v1/sessions-30/native-code/groups.json`。
- 原始：`C:/Users/35153/PycharmProjects/master-work/sessions/`。
- 完整恢复切片：`C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-full-content-slices/`。

默认路径由脚本位置推导，不依赖终端当前目录；可用 `--groups`、`--sessions-dir`、`--slices-dir` 修改。入口接受完整轨迹上的策略分组（例如 `native-code-*`、`stack-site-*`），不能误用切片分组。单会话类全部保留，允许零 Skill，不设两 Session 门槛。

复用 [select_group_slices.py](./select_group_slices.py) 的 `group-context`，根据原始 source_index/source_part_index 和分组已保存的附近上下文选择切片。本轮没有改切片或分组算法，不重新 embedding。若恢复清单存在，核对原始文件哈希与切片来源哈希；若核心错误事件无法映射，准备阶段报错，不悄悄丢掉某一类。没有匹配到的附近上下文记录在清单中。

C 的缩略规则沿用之前实现：未选中切片只隐藏思考、工具结果正文；User/Assistant 正文和工具参数仍保留，包括长 Write/Edit 参数。原始 97 切片不是本轮重新切分。输入快照避免续跑时源文件变化；快照中的完整 B 与 C 选中切片字节一致。

## 提示词与工具

[提取提示词](./error-skill-extraction-prompt.txt) 保留已有“宁缺毋滥”、对应问题—操作—验证、失败方法剔除、参数化和不编造因果的原则，改为结构化提交。错误码是输入筛选入口，**没有新增只允许该错误主题的要求**；可以提取输入中其他可靠经验。没有自动给实验结果打质量分。

工具定义在 [脚本的 TOOLS / RESPONSE_SCHEMA](./error_skill_extraction.py)；准备目录的 `tools.json` 是实际送模型的完整定义。

| 工具 | 作用 |
|---|---|
| `read_trace(file_id, offset, max_chars)` | 按 Unicode 字符分页读取允许文件的完整文本；可续页 |
| `search_trace(file_id, pattern, regex, start_match, limit)` | 在当前文件可见事件字符串中查找，返回原始坐标和片段；可续页 |
| `read_event(file_id, source_index, source_part_index, offset, max_chars)` | 精确读取可见原始事件/part；长事件可续页 |
| `response(skills, excluded_candidates)` | 最终一次提交完整结果；成功后结束该实验 |

模型只能使用本实验输入清单内的 `file_id`，没有终端或任意文件访问。C 中 `collapsed_content` 里的源文件路径只是定位元数据，不能补读隐藏正文。各组使用同一套读取工具，没有跨组补全。

每文件必须至少被读取或搜索一次才能提交；这不等于全文审查。读取范围、每次搜索及工具返回都记录下来。长文件没有静默截断，工具显式返回 `next_offset` 或 `next_match`。模型应从搜索片段进一步读取关键事件。没有自动摘要/压缩已读消息；服务的上下文不足时会明确失败，不悄悄改输入。`max_requests` 是运行保护上限，不是切片容量或分组参数；每次请求可以含多个读取调用。

`response.skills[]` 包含以下全部模板结构，详细子字段以 `tools.json` 为准：

```text
title, name, description {use_when, helps, requires, do_not_use_when}
goal, scope {in_scope, out_of_scope}, inputs[], outputs
preconditions[], procedure[], decision_rules[], invariants[]
common_failures[], verification[], examples[], evidence[]
```

每条 `evidence` 必须包含 `kind`（problem/action/verification）、`file_id`、零基 `source_index`、零基或 null `source_part_index`、精确 `quote`、`supports`。零 Skill 是合法成功，不会被当作失败重试。模型漏章节、引用不存在/隐藏内容、把 Assistant 文本当工具验证等，工具返回错误让其修正；达到请求上限仍未提交就标记失败。每个 Skill 至少有三种证据，脚本核对引用原文存在以及验证引用来自可见工具输出。

**校验不证明因果、可迁移性或每个步骤都有效。** 所有导出均标记 `candidate_needs_review`。为未来管理和检索保留标题、触发场景、完整步骤、组/输入方案、Session/事件来源、模型、提示词哈希和文件哈希；不跨类/跨方案合并或去重，Skill 数量不是独立可用经验数。

## 产物

```text
<output>/
  manifest.json                   输入版本、提示词/工具哈希、无 key 的模型/API 参数
  preflight.json                  14 类三组的文件数、字节数、映射诊断
  prompt.txt, tools.json, groups.json
  inputs/originals/...            原始轨迹快照（多类复用同一源快照）
  skill-index.jsonl               所有完成实验的结构化候选，供管理/检索读取
  summary.json                    按组/方案统计候选、token、耗时和失败
  native-code-.../
    selection-B/selection.json, slices/...
    selection-C/selection.json, slices/...
    A-original/                   B-selected/、C-context-collapsed/结构相同
      input-manifest.json
      api-session.json            使用 sessionHeader 时记录该组请求头名和 Session ID
      requests/0001/request.json  实际发送的 body，不含 Authorization
      requests/0001/response.json 服务返回原文（含 usage）
      messages.json, tool-log.json
      request-costs.json, summary.json
      response-arguments.json     校验通过的 response 参数
      skills.json
      skills/skill-.../SKILL.md    按模板完整渲染，Verification 为未勾选清单
      skills/skill-.../skill.json  含来源的结构化候选
      attempts/attempt-NNN/...    续跑保留旧失败成本
```

目录名由脚本哈希生成，不把模型给出的名称当文件路径。既有用户产物不覆盖。API key 只用于 HTTP Authorization，不写入产物，HTTP 错误正文经脱敏和限长后写入失败摘要。

## token 和时间口径

每次请求及每组、全部实验都记录：输入 token、缓存输入、非缓存输入、输出 token、推理 token、总 token、请求数、请求发出/结束 UTC 时间、API 等待秒数、组墙钟秒数。推理 token 通常是输出 token 的子集，不重复加到总数。累计 token 是各次 usage 求和，包含历史消息重复发送及失败后的再次尝试。

服务不返回缓存或推理细项时保留 null；汇总提供 `known_sum`、`missing_request_count`、`complete`，不得把缺失当零或估算成确切 token。没有 provider usage 的网络失败，其花费未知；不自动重试。强制结束进程导致时间未知时记录 null，并记录未知计数。这里是非流式传输，首 token 耗时不可得，`ttft_seconds=null`；API 耗时和墙钟耗时仍正常记录。没有单价配置，不推算金额。

`max_output_tokens` 默认 16000，`output_token_parameter` 可在 `max_tokens` / `max_completion_tokens` 中选择。`temperature=null` 不发送温度参数；若服务需要可在本地配置填写。`extra_body` 可设置服务支持的推理参数等，但不允许覆盖 messages/tools/model/stream/数量/输出上限。修改模型设置应开新实验目录。

## 本地验证

```powershell
cd master_work/experiments/trace-segmentation/dynatic-split-session-test
python -X utf8 -m unittest test_error_skill_extraction test_select_group_slices test_calibrated_slice_payloads
```

本轮 31 项测试通过：模拟 API 三组完整链路、模板章节、来源校验、工具隔离、空结果、token 缺失、截断失败、失败/强制结束续跑成本保留和不重复调用。使用模拟传输，没有付费 API 调用；真实服务工具支持与模型质量待用户填写配置后验证。

真实数据准备成功：
[14 类 / 42 实验的输入清单](C:/Users/35153/PycharmProjects/master-work/skill-runs/error-code-preflight-v2/manifest.json)。包含此前 LNK1105 的 5/9/20 文件三组。该目录只准备输入，尚未生成真实模型 Skill。

协议依据：[OpenAI Chat Completions 官方文档](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。实际第三方接口兼容程度由用户服务决定。

## 单独探活（不运行提取实验）

[probe_skill_api.py](./probe_skill_api.py) 读取同一本地配置，默认用 `skill-extraction-probe/1.0` 标识客户端、保留 Session 请求头，只发送“Reply exactly OK.”，输出上限 128 token。保存 HTTP 状态、经过 key 脱敏的错误正文/正常响应、usage 和耗时；不发送轨迹，不自动重试，不改业务提取程序或用户配置。

```powershell
python -X utf8 master_work/experiments/trace-segmentation/dynatic-split-session-test/probe_skill_api.py
python -X utf8 master_work/experiments/trace-segmentation/dynatic-split-session-test/probe_skill_api.py --list-models
```

第二条仅 GET `/models`，不会请求模型生成。`--user-agent` 可明确指定客户端标识用于对照；`--timeout`、`--max-output-tokens`、`--config`、`--output` 可设置单次探活参数。

2026-10-14 实测：Python 默认标识返回 HTTP 403 / Cloudflare 1010；自有探活客户端标识返回 HTTP 400 / `Model is unavailable`；模型列表 GET 返回 HTTP 200，其中没有配置的 `mimo-v2.6`，有 `mimo-v2.6-flash` 与 `mimo-v2.6-pro`。没有替用户更换模型，也没有重新运行三组提取。OpenCode Go [官方说明](https://opencode.ai/v2/docs/console/go/) 要求客户端发送自己的 User-Agent 和稳定 Session ID。

探活记录：

- [默认 urllib 失败](C:/Users/35153/PycharmProjects/master-work/skill-runs/api-probe-urllib-v1.json)。
- [自有客户端标识，模型不可用](C:/Users/35153/PycharmProjects/master-work/skill-runs/api-probe-client-agent-v1.json)。
- [接口返回的模型列表](C:/Users/35153/PycharmProjects/master-work/skill-runs/api-probe-model-list-v1.json)。

随后用户将模型改为 `mimo-v2.6-flash`，正式程序仍因未发送自有 User-Agent 而返回 403。已补全正式请求默认客户端标识，并让探活器复用正式请求头构造函数。使用当前配置及 `skill-extraction/1.0` 再探活，HTTP 200，正文 `OK`，输入 11 / 输出 14 / 总 25 token，耗时约 2.21 秒。18 项提取器本地测试通过；没有启动 42 个实验。记录：[正式请求头的最小成功请求](C:/Users/35153/PycharmProjects/master-work/skill-runs/api-probe-formal-headers-v1.json)。
