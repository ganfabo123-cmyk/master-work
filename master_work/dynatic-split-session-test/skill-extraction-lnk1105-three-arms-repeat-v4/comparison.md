# 同输入三组独立重跑：质量、覆盖与成本

记录日期：2026-10-14。用户要求重新运行三组，以检查上一轮结果是否能重复出现。本次三个新 gpt-5.6-luna 子代理分别运行，主代理核查了全部 13 个生成文稿、对应原始证据及三个新的 Codex Session 日志。未修改生成文稿。

## 1. 控制条件

仍使用 LNK1105 组 `native-code-f3df951dc57a` 的相同 5 个 Session：

- A：相同 5 个原始 JSONL。
- B：相同 9 个选中完整正文切片。
- C：相同 20 个文件，9 个完整、11 个隐藏思考和 Tool Result 正文。

逐文件 SHA256 与上轮一致；共享提取提示词与上轮逐字节一致。沿用历史口径的规范化文本 SHA256（CRLF 转 LF 后的 UTF-8）为 `79432c1a1610a85b5a44c880d629078662d8d8c060552113a0d2062ca346ff14`；实际文件字节 SHA256 另记在 manifest.prompt_file_sha256。三个新代理独立读取自己的输入，互不读取其他实验输出。本次只运行提取和审查，不更改算法或策略。

提示词仍要求从轨迹提取可靠经验，没有限定“只提 LNK1105 经验”。这会影响目标错误聚焦程度，但本轮为保持对照没有调整。

## 2. 本轮结果

| 指标 | A 原始轨迹 | B 仅选中切片 | C 完整+缩略 |
|---|---:|---:|---:|
| 输入文件数 | 5 | 9 | 20 |
| Skill 文稿数 | 5 | 2 | 6 |
| 输入 token（含缓存） | 632,854 | 527,647 | 1,352,742 |
| 缓存输入 | 580,864 | 484,864 | 1,267,456 |
| 非缓存输入 | 51,990 | 42,783 | 85,286 |
| 输出 token | 13,857 | 8,702 | 15,528 |
| 推理输出（包含在输出中） | 1,109 | 911 | 1,585 |
| 总 token | 646,711 | 536,349 | 1,368,270 |
| 模型请求次数 | 11 | 10 | 17 |
| 任务耗时 | 1m 48.816s | 1m 16.081s | 2m 18.610s |

使用本轮对应 rollout 的 token_usage_record 累计值，与逐请求 usage 求和核对一致；任务耗时使用 task_complete.duration_ms。只计三个提取子代理，不计主代理准备、审查和统计，也没有实际账单金额。

C 本轮总 token 是 A 的约 2.12 倍、B 的约 2.55 倍；非缓存输入是 A 的约 1.64 倍、B 的约 1.99 倍。第三种策略的成本优势没有复现。

## 3. 全部文稿质量审查

这里判断可复用经验及证据，不把文稿数当作可消费 Skill 数，也不打主观 confidence。各文稿仍有引用、模板或适用边界需要修正的地方，未做实际迁移任务验证。

### A：5 个较具体的经验方向

| Skill | 判断 | 核查重点 |
|---|---|---|
| PowerShell 原生退出码 | 较好 | 正确区分失败的 try/catch+2>&1 与最终 cmd /c 路径，真实 fixture 31/32→32/32；来源表将提出方案与实际 Edit 的行号混用，需对齐。 |
| 两遍首参数索引 | 较好 | 交错 a/b/a 输入暴露桶区间重叠，先计数/分配再填充是具体可迁移经验；有索引与完整 suite 结果。 |
| 大对象栈溢出 | 较好，需保持范围 | 有大小估算、最小链接、值改引用、全套通过；静态存储方案必须保留非重入约束，不应扩大到未经验证的并发修复。 |
| 分配器与嵌入隔离 | 较好，部分约束过强 | allocator thunk、userdata、create/destroy、隔离及计数有直接依据；要求上游构建文件始终不改不能直接从轨迹得出，轨迹曾修改 root Makefile 后转入独立构建。 |
| 裸 eval 与可选注册 | 较好 | 清楚区分内部 eval hook 和可见标准库，并提取 C 参数求值顺序导致错误指针观察不稳定的具体经验；有最终 135 passed/0 failed。 |

比上一轮 A，同样为 5 个文稿，但内容已经变化：新增交错索引、细化退出码和裸 eval；没有单独提取字节码 Skill。数量相同不表示覆盖稳定。

### B：2 个方向较窄，唯一专门提取 LNK1105

| Skill | 判断 | 核查重点 |
|---|---|---|
| Windows PowerShell/Makefile 入口兼容 | 有价值，需收窄因果和范围 | 有语法、shell 分派和回归结果，但不能把同批次 em dash/语法修改的作用逐项写成已独立证明的原因，也未证明所有 Unix 运行情况。 |
| 测试二进制占用导致链接失败 | 有价值，较贴合目标错误 | FrostCore 575 报错、577 taskkill+重建、580 直接套件通过形成实际处理链。文稿例子声称进程列表显示占用实例，但该 Session 只有 taskkill 命令，没有实际 tasklist/Get-Process 证据；这一句须删除或改为执行前检查。固定 1246/135/101 也不能成为通用验收条件。 |

B 本轮没有展开栈溢出、字节码、分配器隔离等经验，它们的关键证据仍在相同 9 个文件中。不能把漏提直接归因于切片损失。

若目标严格限定为这类 LNK1105 的解决经验，B 本轮比 A/C 更直接；A/C 都没有单独输出该错误 Skill。

### C：6 个方向，覆盖更广但来源表有明显问题

| Skill | 判断 | 核查重点 |
|---|---|---|
| 既有序列化 API 的阶段边界适配 | 较好，偏架构取舍 | 没有把 monolithic parser/VM 的物理拆分误报为完成；有 scratch runtime、序列化独立 blob 和实际 101 项测试。比上一轮具体字节码 Skill 更偏“选已有 API”的决策。 |
| 子系统注册与依赖反馈 | 有价值，需修来源 | 提取内部 eval 和参数求值顺序的具体故障，并保留依赖反馈；早期部分结果被隐藏，来源表却指向并不存在相应 source_index 的 segment-02/03。后续完整 135 项回归在 source_index 580，属于可见完整切片，应该引用这一实际结果。 |
| 分配器、生命周期、隔离 | 较好，需修验证来源 | 包含 thunk、3 runtime、sentinel、计数；早期 cited smoke 正文被缩起，不能当作本次读取到的工具结果。514 的源码读取和 580 的重复 smoke 实际输出仍完整可见，可支持该经验。 |
| Shell/退出码兼容 | 较好，需选用可见验证引用 | 已避免上一轮 C 推荐失败 try/catch 的问题；来源表的 segment-03 source_index 780-791 位于重叠区，事件引用存在，但其中工具结果在该缩略文件中被隐藏。同一批事件也在完整保留的 segment-02，应从完整文件引用验证正文。 |
| 两遍索引与回溯 | 较好，需修文件定位 | 关键 bug、两遍范围、变量候选和回溯都有实际代码与验证；来源表把 Epilog 207-334 引到 segment-02，实际在完整 segment-03。 |
| 大对象栈溢出 | 较好，需修文件定位 | 正确描述最小复现、值复制及静态测试存储边界；来源表同样将多个已在完整 segment-03 的事件写到 segment-02。 |

C 的六个经验主题大体有真实依据，涵盖 A 本轮的五个主题，并增加字节码边界。但这只是主题覆盖，不是经过迁移执行验证的 Skill 召回率，不能声称 6/6 文稿可直接用。

本轮 C 没有再生成缺少跨语言验证的 FFI Skill，也没有推荐失败的 try/catch 路径，语义质量比上轮 C 有改善。与此同时，多处来源文件名错误、将隐藏正文当作验证引用，以及预先打勾的 Verification，需要修正文稿。

## 4. 与上一轮对比

| 方案 | 上轮文稿数 | 本轮文稿数 | 上轮总 token | 本轮总 token | 上轮耗时 | 本轮耗时 |
|---|---:|---:|---:|---:|---|---|
| A 原始 | 5 | 5 | 1,655,674 | 646,711 | 2m18.432s | 1m48.816s |
| B 仅选中 | 3 | 2 | 1,577,174 | 536,349 | 3m11.154s | 1m16.081s |
| C 完整+缩略 | 4 | 6 | 979,716 | 1,368,270 | 1m52.176s | 2m18.610s |

同一输入重复运行，模型读取方式、请求次数和候选取舍都有明显变化。上轮 C 是成本最低，本轮 C 最高。不能将一次 token 优势归因于输入策略并认为它稳定存在。

仅作描述性统计的两次均值：

| 方案 | 平均总 token | 平均非缓存输入 | 平均耗时 |
|---|---:|---:|---|
| A | 1,151,192.5 | 75,879.5 | 2m03.624s |
| B | 1,056,761.5 | 64,988.5 | 2m13.618s |
| C | 1,173,993 | 83,523.5 | 2m05.393s |

样本只有同一个错误组的两次运行，这些均值不是总体性能估计。A/B 上轮并行、C 上轮单独，本轮三组并行，耗时也受到执行环境和调度影响。

## 5. 修正当前判断

需要修正上一轮“C 是最合适的暂定综合基线”中对成本的判断：C 是信息保留更多、可覆盖更多经验的候选，但成本优势没有复现，不能称为已证明稳定最优的综合策略。

本轮可以分别判断：

- 泛化经验的主题覆盖：C 更广，A 也产生细致经验；B 更窄。
- 本次 token 与耗时：B 最低，A 次之，C 最高。
- 专门复用 LNK1105 解决经验：B 的专门文稿更对题，但仍需修证据与验收条件。
- 生成文稿的可靠性：三组都需核对，尚未达到每个文稿都无需修订即可使用。

保留三个实验模式，不修改算法、提示词或生成文稿；不从本次文稿数量推算质量提升率或 Skill 损失率。后续 Harness 需要约束证据定位、成功方案筛选和读取过程，才能更公平地测输入策略本身的贡献。

## 6. 产物路径

- [A 原始组新提取全文](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/A-original/extraction.md)。
- [B 仅选中组新提取全文](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/B-selected/extraction.md)。
- [C 完整+缩略组新提取全文](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/C-context-collapsed/extraction.md)。
- [新三代理成本记录](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/costs.json)。
- [输入、模型、提示词及代理身份](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/manifest.json)。
- [C 来源表端点定位核查](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/source-reference-audit.json)。
- [机器可读汇总](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-three-arms-repeat-v4/summary.json)。
