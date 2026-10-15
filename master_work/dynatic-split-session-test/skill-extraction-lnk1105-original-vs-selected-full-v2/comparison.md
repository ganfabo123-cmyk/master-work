# LNK1105 原始轨迹与完整正文切片：独立提取对照

记录日期：2026-10-14。两组已完成，本报告由主代理核查生成的全部 8 个 Skill 文稿及对应原始证据后编写，没有修改子代理的提取结果。

## 1. 实验设置

使用昨日错误码组 `native-code-f3df951dc57a`，分组键 `ms-linker:LNK1105`，包含同一组的全部 5 个原始 Session。

| 项目 | A：原始轨迹 | B：选中切片 |
|---|---|---|
| 模型 | gpt-5.6-luna，独立子代理 | gpt-5.6-luna，独立子代理 |
| 输入 | 5 条完整原始轨迹文件 | 当前 group-context 策略选出的 9 个切片 |
| 提示词 | 今天归档的宁缺毋滥提示词 | 同一份提示词 |
| 读取范围 | 仅本组输入清单 | 仅本组输入清单 |
| 输出 Skill 数 | 5 | 3 |
| 文件字节数 | 13,295,678 | 2,901,353 |

两组采用新代理分别运行，未沿用上次已停止实验的输出。提取提示词全文未添加“只提 LNK1105 Skill”的语义限制，因此结果可以包含这些 Session 中的其他经验。

切片来自补回 Tool Result 和 Thinking 正文后的新目录；选中 ID 与上次相同，没有在提取前另加筛选。17 次 LNK1105 原始报错全部保留，保留事件的文本和工具参数均与原始文件一致。去除重叠后保留 955 个 Tool Result，其中 950 个有正文，另 5 个原始结果本来为空。

文件字节数减少约 78.2%，但原始 JSONL 和切片 JSON 的格式、元数据不同，不能将这个百分比当作 token 或模型调用成本下降。

## 2. 全部文稿质量审查

“较好”表示经验有价值且关键机制有真实依据，不等于文稿无需修改即可直接消费。

| 组别 | Skill | 判断 | 具体理由或不足 |
|---|---|---|---|
| A1 | 分配器可注入的多 runtime 隔离 | 较好 | 每实例 allocator/userdata、回调适配、sentinel 隔离与销毁计数形成具体经验；把三 runtime 和 1246 次分配固定成通用验收条件不合适。 |
| A2 | 子系统选择性注册、依赖与幂等 | 中等偏好 | per-runtime bitmask、先检查依赖再安装、重复注册无副作用有实际行为证据；应区分测试覆盖的拒绝情形与真实发生过的故障，不扩写假想失败。 |
| A3 | 可移植字节码 parse-once-run-many | 较好 | scratch runtime、序列化后独立持有 blob、load/eval、执行前复制函数句柄，机制清楚且有直接回归结果。 |
| A4 | 大型测试 fixture 按值复制导致栈溢出 | 较好，但来源表须修正 | 明确解释“工厂返回引用，但局部变量按值声明仍复制大对象”，改为引用后有 17/17 与全套结果。文稿却引用 1204、1208，实际该 Session 仅 378 行，引用无效。 |
| A5 | 批处理 CLI 失败隔离与测试器误报 | 较好 | 非法输入不阻断好文件、缺失路径不应返回零，以及 PowerShell stderr/断言误报，具有可执行的诊断与验证逻辑。 |
| B1 | 跨平台构建与测试环境排障 | 一般 | 混合 IDE、PowerShell 语法、Makefile shell、DLL 和文件锁，多个有效案例被包进过宽主题。对一次字符改写的作用也写得过于绝对，缺少独立因果证明。 |
| B2 | Token 流与增量 fixture 调试 lexer/parser | 较好 | `/>` 拆错、JSX mode、brace depth、Token 正确后再查 parser branch，能指导具体排障；PowerShell runner 分支可进一步整理，避免干扰主题。 |
| B3 | 序列化编译与执行边界 | 较好 | 与 A3 属于同一经验，强调 compile-only、blob 所有权与多 runtime 验证；没有像 A3 一样明确写出保存句柄与执行前复制句柄的细节。 |

两组共同的问题：部分 Verification 直接要求本次轨迹的固定通过计数，应该在实际使用时按当前测试集检查全部关键测试通过；具体计数适合留在示例或证据中。B 组没有按提示词附逐 Skill 来源证据表，虽然正文有索引引用，格式仍不完整。

原始文稿保留不改。本报告指出质量问题，不把它们自动修成另一次模型输出。

## 3. 是否丢失了 Skill 信息

不能用 `(5-3)/5=40%` 表示 Skill 损失率。A 不是金标；B 额外提取了 A 没有单独输出的 Token 调试经验；B1 还把多个问题合并成一个标题。标题数量不能直接一一对应。

逐项回查发现：

| A 组经验 | B 组输出情况 | 选中切片中的证据情况 |
|---|---|---|
| 分配器、多 runtime 隔离 | 未单独输出 | FrostCore 的后续完整源码读取和直接 smoke 测试仍在；早期实现过程被删减。 |
| 子系统依赖与幂等 | 未单独输出，仅作 B3 的回归背景 | bitmask 源码、上下文与直接 subsystem 回归仍在；早期注册实现过程被删减。 |
| 字节码边界 | B3 对应 | 实现写入、load/eval 和 101 项测试均在。 |
| 大对象按值复制栈溢出 | 未输出这一成功案例 | Epilog 479c5e9f 的报错、读取、按值改引用和最终成功全部保留。B 排除段谈的是另一个 c99032e9 Session 的候选，不能当成该成功案例缺失。 |
| 批处理失败隔离/测试器误报 | B1 部分覆盖，没有独立展开 | harness 修改、缺失路径错误计数修改及后续验证在选中切片中。 |

核查定位均使用零基 `source_index`；JSONL 文件行号为它加一：

- FrostCore：493（用户续接上下文）、514（完整 runtime 源码读取）、580（真实工具输出）。580 明确包含 sentinel 隔离、allocs/frees、135 个 subsystem 测试及 101 个 bytecode 测试，不只是 Assistant 的成功声明。
- Epilog 479c5e9f：319 报错，322 源码读取，324 定位按值复制，325 修改，328 focused 通过，333 全套通过。全部在选中的 segment-03。
- Yggdrasil：1389、1392、1400、1419、1427 等诊断、修改与验证事件，全部在选中的 segment-04。

所以，本次确实删掉了部分历史事件，但没有证据证明 A 中那些未单独输出的经验已经因选择切片而无法提取。部分关键证据已保留而仍被 B 漏提，说明模型选择、注意力和拆分粒度对结果也有影响。

这不等于证明信息损失为零：早期过程被删减是客观事实；本次只核查 A 输出的候选，无法穷尽这 5 条原始轨迹中全部可提取经验；单次独立生成也不能隔离模型波动。

## 4. 本次结论

原始组输出更细，整体文稿质量优于切片组那个宽泛的构建排障包。切片组仍提取了有价值的 Token 排障和字节码边界经验，且当前关键证据的保留情况比旧切片完整。

本次支持的结论是：完整正文切片选择具有可行性，显著减少了输入文件规模；当前输出差异不能直接归因于不可恢复的 Skill 信息丢失。尚不能给出可靠 Skill 损失率，也未证明切片提取质量与原始提取完全等价。

本轮不修改聚类、切片选择算法或提取提示词。

## 5. 产物

- [A 原始轨迹提取全文](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/A-original/extraction.md)。
- [B 完整正文切片提取全文](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/B-selected/extraction.md)。
- [共享提示词](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/prompt.txt)。
- [实验输入、模型及文件哈希](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/manifest.json)。
- [新切片选择清单](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/group-slice-selection-native-code-lnk1105-full-content-v2/selection.json)。
- [逐 Session 输入正文核查](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/input-evidence-audit.json)。
- [五个原始组经验的切片证据定位](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/candidate-evidence-coverage.json)。
- [机器可读汇总](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-lnk1105-original-vs-selected-full-v2/summary.json)。
