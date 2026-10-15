# Skill Extraction v3 — Independent Conservative Runs

三组实验由三个独立子代理分别执行，提取期间不共享其他实验结果。统一原则是“宁缺毋滥”：缺少直接证据、具体动作或可验证结果的候选直接丢弃。

| 组别 | 输入 | 保留 Skill | discarded |
|---|---|---:|---:|
| A-session | 30 个完整 Session / 117 个 segment | 6 | 24 |
| B-slice | 97 个切片 | 7 | 17 |
| C-domain | 8 个细领域 / 314 次领域成员读取 | 7 | 16 |

总保留记录：20；总 discarded：57。

## 输出

- A：`C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v3-independent-conservative\A-session\analysis.json`
- B：`C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v3-independent-conservative\B-slice\analysis.json`
- C 汇总：`C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v3-independent-conservative\C-domain\summary.json`

## 机器核验

- 三组 JSON 均可解析。
- 所有保留 Skill 都有非空直接来源证据。
- 所有来源文件存在。
- 未修改算法代码。

## C 各领域

| 领域 | 读取切片 | 保留 | discarded |
|---|---:|---:|---:|
| D001 | 65 | 1 | 2 |
| D002 | 43 | 1 | 2 |
| D003 | 45 | 1 | 2 |
| D004 | 29 | 0 | 2 |
| D005 | 45 | 1 | 2 |
| D006 | 36 | 1 | 2 |
| D007 | 27 | 1 | 2 |
| D008 | 24 | 1 | 2 |

## Codex 代理资源消耗

统计来源是本机 Codex rollout 原始记录：`C:\Users\35153\.codex\sessions\2026\10\13\rollout-*.jsonl`。这里记录每个代理初始提取任务结束前的 `thread_token_usage` 累计值；之后为查询统计而发送的 follow-up 不计入本次实验。

| 代理 | 输入 token | 缓存输入 | 输出 token | 推理输出 | 总 token | 耗时 |
|---|---:|---:|---:|---:|---:|---:|
| A-session | 1,935,623 | 1,811,712 | 11,383 | 2,298 | 1,947,006 | 2m 11.352s |
| B-slice | 2,607,141 | 2,512,128 | 16,506 | 3,763 | 2,623,647 | 2m 49.288s |
| C-domain | 1,614,599 | 1,517,312 | 13,093 | 2,838 | 1,627,692 | 2m 10.453s |
| **合计** | **6,157,363** | **5,841,152** | **40,982** | **8,899** | **6,198,345** | **7m 11.093s（代理耗时相加）** |

三个代理是并行运行的，从最早启动到最后完成的墙钟跨度约为 **3m 03.690s**。`total_tokens` 为输入 token 与输出 token 的总和；`reasoning_output_tokens` 已包含在输出 token 中，不应再次加到总 token。
