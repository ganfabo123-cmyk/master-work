# 选中完整、其余缩略：LNK1105 第三组提取实验

记录日期：2026-10-14。独立 gpt-5.6-luna 子代理已完成；主代理已核对全部四个文稿、输入处理规则及 Codex Session 成本记录。原始生成文稿未改写。

## 输入与策略

继续使用 `native-code-f3df951dc57a`（LNK1105）组的 5 个原始 Session。选择规则仍为 group-context，完整展示的切片 ID 与上一轮相同。

新增内容策略 `selected-full-rest-collapsed`，与选择策略分开：

- 9 个选中切片按字节原样复制。
- 11 个未选中切片保留全部事件、顺序和索引，仅隐藏 Thinking/Reasoning、Tool Result 正文。
- User、Assistant 正文、工具调用参数仍保留；不对这些文本另外截断，不调用 LLM 做摘要。
- 每个隐藏正文位置保留字段名、原始索引和原切片路径；本组提取证据范围仍限定为清单列出的 20 个导出文件，没有另行读取隐藏正文。

实际导出 20 个文件，总大小 4,407,814 字节；共缩起 502 个事件正文（含原有切片重叠）。测试共 17 项通过。真实产物核查确认 9 个完整文件未改变，其他切片事件数、顺序、角色和原始索引未改变。

本组使用与 A/B 完全相同的提取提示词，没有加入只提 LNK1105 的要求；因此依旧评估这些输入能提取哪些经验，而不是只评价一条错误 Skill。

## 生成结果与质量

输出 4 个 Skill 文稿，不能把 4 个都当作无需审查即可使用的成品。

| Skill | 质量判断 | 证据和问题 |
|---|---|---|
| Windows 大对象测试栈溢出 | 较好 | 479c5e9f 的崩溃、按值改引用、17/17 和全套通过均有直接证据。c99032e9 的未完成案例也被明确标为非成功证据。文稿比此前 A 的同主题来源表更准确。 |
| 独立、重复加载的字节码 | 较好，需删无依据的附加断言 | scratch runtime、独立 blob、owning loaded_fn 和执行前复制引用均写清；与 B 相比补回了关键句柄操作。Verification 把“空源码”与语法错误一同要求返回失败，但所引证据没有证明这一要求；不能把 NULL source 与空字符串混为一谈。 |
| C/Python/Odin 的 C ABI 封装 | 未达到已验证 Skill 要求 | 接口与包装代码确实存在，经验有潜力；但 144/144 是 indexing/stats/memo/solver/atoms/lexer/parser/terms/unifier/variables 十个原生套件，没有验证 FFI 调用、回调和目标语言消费。不能用这些通过数证明 C/Python/Odin 边界可用。 |
| Windows/Unix 批处理 CLI | 核心有价值，处理分支需修正 | 好文件不因坏文件被中断、缺失路径返回非零有实际证据。但 try/catch 并不是最终成功的退出码处理方法，文稿混入了失败尝试；Unix 入口的实际验收也没有对应直接证据。 |

本组约两项有较好的经验与操作依据，但仍应修正附加断言；批处理方向可保留，需修正文稿；FFI 方向当前不应作为已经验证的跨语言 Skill 消费。这是人工审查，不是打分模型或 confidence。

### 关键核查定位

以下均为零基 source_index，JSONL 原始行号为它加一。

- 479c5e9f：319/322/324/325/328/333 是栈溢出复现、读源码、定位、改引用、focused 和完整测试；333 的套件清单证实十个测试套件没有 FFI API 测试。127/130 是 FFI 头和实现写入，352 是最终摘要及 Python usage sketch，不能用摘要中的示例代替真实运行。
- 6a7964ed：485/507 为 parse/vm 实现，580 为直接三套件结果，581 为解释与总结。485 只判断 NULL source/out 的条件，不能由此推导空字符串应失败。
- 39082932：778 仍为 31 passed/1 failed，错误案例 exit=-1；783/786 明确诊断 try/catch 与重定向影响退出码；787 改为 cmd /c；之后完整套件通过。C 文稿却把 try/catch 写为推荐恢复方法，未正确区分尝试与最终方法。

## 与前两组对比

| 输入 | 生成文稿数 | 主要差异 |
|---|---:|---|
| A：5 条原始轨迹 | 5 | 原始组经验较细，包含分配器隔离、子系统依赖等；也有来源编号与验收条件问题。 |
| B：9 个完整正文切片 | 3 | 字节码与 Token 调试有价值，但构建包过宽，漏提了证据仍在的栈溢出成功案例。 |
| C：9 完整 + 11 缩略切片 | 4 | 提取了栈溢出成功案例，字节码操作细节更完整；新增 FFI 缺少关键验证，批处理文稿混入失败恢复方法。 |

更多上下文并没有使全部文稿可靠。C 恢复了 B 漏提的经验，也不再单独提取 B 的 Token 调试，仍未单独提取 A 的分配器隔离与子系统依赖。实际证据的保留和模型的取舍应分开评价。

针对 LNK1105 本身，C 只把文件锁作为前置处理或未完成任务中的背景，没有生成专门的错误处理 Skill。提示词仍允许所有主题；因此本实验没有证明新策略提高了目标错误的聚焦程度。

不能从 5/3/4 的文稿数量计算 Skill 损失率或质量提升率。

## Token 与时间成本

从本机三个对应 rollout JSONL 的 token_usage_record 与 task_complete 核算，单请求 usage 相加与最终 thread_token_usage 一致。A/B 为上次运行，C 为这次单独运行。

| 指标 | A 原始组 | B 仅选中 | C 完整+缩略 |
|---|---:|---:|---:|
| 输入 token（含缓存） | 1,641,657 | 1,564,314 | 967,265 |
| 缓存输入 | 1,541,888 | 1,477,120 | 885,504 |
| 非缓存输入 | 99,769 | 87,194 | 81,761 |
| 输出 token | 14,017 | 12,860 | 12,451 |
| 推理输出（包含在输出中） | 1,333 | 1,475 | 1,091 |
| 总 token | 1,655,674 | 1,577,174 | 979,716 |
| 模型请求次数 | 21 | 22 | 13 |
| 任务耗时 | 2m 18.432s | 3m 11.154s | 1m 52.176s |

C 相对 A：总 token 少约 40.8%，非缓存输入少约 18.0%，耗时少约 19.0%。相对 B：总 token 少约 37.9%，非缓存输入少约 6.2%，耗时少约 41.3%。

本次成本下降主要伴随模型请求次数从 21/22 降到 13：累计上下文重复输入减少，不能简单解释成每轮输入更小。C 输入文件反而比 B 大。单次运行不能证明新策略必然降低同样幅度的成本；也没有真实账单金额。这里只计子代理，未计主代理实现、准备、审查与统计。

## 本次结论与归档

新策略可作为一个可复现的实验版本：保留更多历史上下文，这次 token 与时间比前两次少，且找回了一个此前漏提的有价值经验。但文稿质量没有全面改善，仍需区分失败尝试、真实验证和范围过度泛化；不能声称已经同时解决低成本与可靠提取。

- [导出切片与缩略清单](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/group-slice-selection-native-code-lnk1105-context-collapsed-v3/selection.json)。
- [本组 Skill 原始生成全文](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-context-collapsed-v3/extraction.md)。
- [实际发给代理的任务](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-context-collapsed-v3/task.txt)。
- [共享提取提示词](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-context-collapsed-v3/prompt.txt)。
- [输入清单与文件哈希](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-context-collapsed-v3/input-manifest.json)。
- [三组真实成本记录](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-context-collapsed-v3/costs.json)。
- [机器可读结论](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-context-collapsed-v3/summary.json)。
