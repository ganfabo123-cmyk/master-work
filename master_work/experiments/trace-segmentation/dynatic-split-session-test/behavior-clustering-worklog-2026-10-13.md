# 2026-10-13 行为逻辑聚类与原始轨迹 Skill 提取工作记录

## 1. 今日目标

今天的目标是评估并改进行为聚类结果，使聚类的主要作用从“给每组命名”转为“减少 Skill 被拆散的概率”。允许组内存在一定混杂，也允许同一条切片出现在多个候选中；不能为了控制组大小而牺牲候选 Skill 的证据完整性。

今天的语义主线是：

```text
原始 Session / 切片
→ 细领域成员切片
→ 目标与执行逻辑表示
→ 候选 Skill 组
→ 人工或 LLM 依据原始证据判断可提取 Skill
```

其中，聚类结果是候选输入，Skill 是否真正成立必须回到来源轨迹和具体事件证据。

## 2. 固定输入

行为聚类使用的切片目录：

```text
C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices
```

细领域成员文件：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\unsupervised-domain-complete-v6\domains.json
```

领域特征卡片：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\domain-feature-cards-v2\domain-feature-cards.json
```

原始 30 条 Session 的清单和展开轨迹：

```text
C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\toolcall-report.json
C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\context-expanded-sessions
```

实际清单声明 30 个 Session，展开目录中与这 30 个 Session 对应的 JSON 分段共 118 个。

## 3. V5：全局多视图 Skill 空间

### 3.1 实现内容

V5 试图先为全部唯一切片建立全局稀疏特征空间，再在领域内生成候选。表示包括：

- problem：用户目标、问题、错误和约束；
- resolution：模型判断和工具动作；
- verification：构建、测试、运行和检查；
- order：角色、工具操作、阶段和 n-gram 顺序；
- 问题→动作、动作→验证等关系特征；
- 跨 Session 的操作序列模式；
- 标准库实现的确定性稀疏 NMF；
- cannot-link 关系和扰动稳定性。

V5 另外生成了 `route package`，用于控制一次交给下游模型的切片规模。后来审查发现这个层次偏离了当前目标，因此在最终 V6 中移除。

### 3.2 代码和测试

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior_logic_clustering_v5.py
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\test_behavior_logic_clustering_v5.py
```

### 3.3 V5 产物和结果

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v5-skill-space
```

主要结果：

| 指标 | V5 结果 |
|---|---:|
| 输入切片 | 97 |
| 细领域 | 8 |
| 表示行 | 314 |
| Route package | 88 |
| Skill candidate | 41 |
| Route 最大切片数 | 8 |
| 人工审查 strict candidate | 1 |
| 人工审查 partial candidate | 5 |
| 人工审查 not extractable | 35 |

V5 的人工审查文件：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v5-skill-space\manual-skill-audit.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v5-skill-space\manual-skill-audit.md
```

V5 暴露的主要问题是：候选数量和 Route 数量很多，但候选之间重叠明显，不能把 raw candidate 数量直接当作 Skill 数量；许多候选只有工具操作相似性，缺少可迁移的问题解决经验。

## 4. V6：从 Route 优先转为细领域质量优先

### 4.1 中间实验

V6 期间依次尝试了 Session-first、slice-first、无容量上限和领域本地特征等版本：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-session-first-recall
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-session-first-recall-v2
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-slice-first-recall
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-slice-first-recall-v2
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-v5-slice-unbounded
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-v5-slice-unbounded-v2
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-v2
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-v3
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final2
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final3
```

这些目录保留了参数和处理边界的演进记录。关键修正有三点：

1. 输入必须是一个细领域自己的切片集合，不能把 8 个领域混在同一次聚类里；
2. `run_domain` 对 8 个细领域分别调用，领域特征和候选发现只在当前领域内计算；
3. 删除 Route package 这层中间产物。容量参数只保留为连续的拆分压力，不再限制候选最大切片数，也不再把“降低模型负担”作为独立目标。

### 4.2 最终 V6 代码

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior_logic_clustering_v6.py
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\test_behavior_logic_clustering_v6.py
```

最终 V6 的处理约束：

- 每次只处理一个细领域的切片；
- 目标和执行逻辑仍然分别表示；
- 候选允许重叠和嵌套；
- 领域词自动派生并降权，不使用人工场景词典；
- 保留 cannot-link 和稀有度、顺序、关系特征；
- `target_capacity=8` 只用于连续 `split_pressure`；
- 不生成 Route package；
- 不调用 LLM 或 embedding。

### 4.3 最终 V6 产物

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final4
```

最终统计：

| 指标 | V6 final4 |
|---|---:|
| 输入切片 | 97 |
| 实际唯一领域成员切片 | 92 |
| 细领域 | 8 |
| Skill candidate | 75 |
| 候选成员引用总数 | 432 |
| 候选最大切片数 | 16 |
| Route package | 已移除 |
| 容量限制 | 无硬上限，仅保留拆分压力 |

最终产物中的主要文件：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final4\manifest.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final4\summary.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final4\manual-skill-audit.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\behavior-logic-clustering-v6-domain-local-quality-final4\manual-skill-audit.md
```

### 4.4 V6 全候选人工审查

审查实际读取了全部 75 个候选引用的 432 个源切片文件，共 120301 个原始事件，缺失文件数为 0。

| 标签 | 数量 | 比例 |
|---|---:|---:|
| high_quality | 3 | 4.00% |
| partial | 27 | 36.00% |
| not_extractable | 45 | 60.00% |

3 个 `high_quality` 记录是 `D002/skill-007`、`D002/skill-008`、`D002/skill-009`，实际是同一个低层启动/显示兼容 Skill 的重叠版本，不能计作 3 个独立 Skill。

## 5. 不受聚类约束的原始轨迹 LLM 提取

### 5.1 目的和提示边界

为了区分“聚类候选质量”与“原始轨迹本身能否产生 Skill”，今天又让 LLM 直接阅读原始 30 条 Session。提示中明确取消了以下限制：

- 不要求至少两个相似 Session；
- 不要求必须跨 Session；
- 不要求先满足某种聚类关系；
- 允许单条轨迹独立形成 Skill；
- 允许一条轨迹形成多个 Skill。

唯一保留的判断是：Skill 必须能从轨迹中还原出具体的决策、诊断方法或安全边界，不能凭空补写轨迹没有出现的事实。

### 5.2 LLM 提取产物

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\original-trace-llm-skill-audit-v1\analysis.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\original-trace-llm-skill-audit-v1\analysis.md
```

每条 Skill 均记录：

- `skill_id`；
- Skill 内容；
- 来源轨迹数量；
- 来源轨迹 ID；
- 来源分段文件路径；
- 事件索引和关键证据；
- 适用边界；
- 质量判断理由。

### 5.3 LLM 提取结果

| 指标 | 结果 |
|---|---:|
| 读取 Session | 30 |
| 读取分段文件 | 118 |
| 提取 Skill | 25 |
| 单来源 Skill | 19 |
| 双来源 Skill | 4 |
| 三来源 Skill | 2 |
| 去重后覆盖轨迹 | 18/30 |
| embedding 调用 | 0 |
| 聚类算法修改 | 0 |

这 25 条结果不是“25 个跨 Session 已确认的 Skill”。其中 19 条只有一个来源，这是本轮有意保留的结果，用来测量不加跨轨迹过滤时，原始轨迹自身能暴露多少可迁移经验。

## 6. 97 个切片的 LLM Skill 提取

### 6.1 目的和处理方式

在原始 30 条 Session 审计之后，又用同样的自由提取方式直接处理全部 97 个切片。这里仍然不要求跨 Session、不要求多个切片共现，也不要求切片先属于某个聚类。一个切片可以产生多个 Skill，一个 Skill 也可以只有一个来源切片。

输入目录：

```text
C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices
```

### 6.2 产物

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\slice-97-llm-skill-audit-v1\analysis.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\slice-97-llm-skill-audit-v1\analysis.md
```

每条记录包含 Skill 内容、来源切片 ID、来源 Session ID、来源绝对路径、事件证据、适用边界和质量理由；`rejected_or_weak` 单独记录不足以形成高质量 Skill 的切片。

### 6.3 结果

| 指标 | 97 切片 LLM 提取 |
|---|---:|
| 实际读取切片 | 97 |
| 实际读取 Session | 30 |
| 提取 Skill | 48 |
| 覆盖切片 | 41/97 |
| 覆盖 Session | 23/30 |
| 缺失文件 | 0 |
| rejected_or_weak 切片 | 2 |
| 单来源切片 Skill | 30 |

来源切片数量分布为：30 条 Skill 来自 1 个切片、16 条来自 2 个切片、2 条来自 3 个切片。来源 Session 数量分布为：41 条 Skill 来自 1 个 Session、6 条来自 2 个 Session、1 条来自 3 个 Session。

### 6.4 与原始 30 条 Session 提取的关系

上一轮直接读取 30 条 Session 得到 25 条 Skill，覆盖 18/30 个 Session；本轮直接读取 97 个切片得到 48 条 Skill，覆盖 41/97 个切片和 23/30 个 Session。两组结果的统计单位不同，不能直接把 48/25 当作算法提升率：前者允许模型在完整 Session 上跨分段归纳，后者要求 Skill 能回指到具体切片证据。

这次结果可以作为“切片级 Skill 保留率”的独立参考集，用于检查 V6 候选是否覆盖原始切片中已经被 LLM 识别出的具体经验。

## 7. 8 个细领域的独立 LLM Skill 提取

### 7.1 实验设置

本轮按上一轮确定的公平方案执行：使用同一个 `gpt-5.6-luna`，把 D001-D008 分成 8 个独立分析上下文。每个领域只读取 `domains.json` 指定的成员切片，不读取其他领域的切片正文、Skill 或分析结果。

仍然采用自由提取口径：不要求跨 Session、不要求多个切片共现、不使用现有聚类候选作为语义门槛；允许单来源 Skill，一个切片也可以产生多个 Skill。分析阶段不做跨领域去重。

### 7.2 产物路径

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\domain-8-llm-skill-audit-v1\summary.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\domain-8-llm-skill-audit-v1\summary.md
```

每个领域还有独立的：

```text
domain-8-llm-skill-audit-v1\D001\analysis.json
domain-8-llm-skill-audit-v1\D001\analysis.md
...
domain-8-llm-skill-audit-v1\D008\analysis.json
domain-8-llm-skill-audit-v1\D008\analysis.md
```

完整根路径为：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\domain-8-llm-skill-audit-v1
```

### 7.3 各领域结果

| 领域 | 实际读取切片 | 实际读取 Session | Skill | rejected_or_weak | 覆盖切片 | 覆盖 Session |
|---|---:|---:|---:|---:|---:|---:|
| D001 | 65 | 25 | 42 | 35 | 30 | 19 |
| D002 | 43 | 20 | 29 | 23 | 20 | 15 |
| D003 | 45 | 15 | 19 | 31 | 14 | 9 |
| D004 | 29 | 11 | 16 | 18 | 11 | 6 |
| D005 | 45 | 16 | 27 | 26 | 19 | 11 |
| D006 | 36 | 16 | 23 | 23 | 13 | 10 |
| D007 | 27 | 11 | 13 | 16 | 11 | 7 |
| D008 | 24 | 12 | 12 | 17 | 7 | 6 |

总计：

- Skill：181 条；
- 领域读取次数：314 次，来自领域成员重叠；
- 去重后覆盖切片：38 条；
- 去重后覆盖 Session：21 个；
- 缺失文件：0；
- 来源切片分布：1 来源 141 条、2 来源 37 条、3 来源 3 条；
- 来源 Session 分布：1 来源 161 条、2 来源 19 条、3 来源 1 条。

这里的 181 是 8 个领域内的原始提取总数，尚未跨领域合并，因此不能直接当作 181 个独立 Skill。

## 8. 三组 Skill 提取实验横向审查

### 8.1 审查范围

本次只横向比较三组 Skill 提取结果：

- A：原始 30 条 Session 直接提取；
- B：97 个切片直接提取；
- C：8 个细领域分别独立提取。

三组使用统一的质量标准：

- `high_value`：证据具体、解决链清楚、具有合理迁移性；
- `usable_narrow`：有真实价值，但适用范围较窄或证据不完整；
- `generic_or_weak`：主要是泛化流程、工具顺序或项目特例；
- `unsupported`：来源证据不足或无法复核。

单个 Session 或单个切片可以独立形成 Skill，不因来源数量少自动降级。

### 8.2 审查产物

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\skill-experiment-horizontal-comparison-v1\analysis.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\skill-experiment-horizontal-comparison-v1\analysis.md
```

### 8.3 横向结果

| 实验 | 原始 Skill | high_value | usable_narrow | generic_or_weak | unsupported | 去重家族 |
|---|---:|---:|---:|---:|---:|---:|
| A：30 条 Session | 25 | 18（72.0%） | 7（28.0%） | 0 | 0 | 25 |
| B：97 个切片 | 48 | 31（64.6%） | 14（29.2%） | 2（4.2%） | 1（2.1%） | 48 |
| C：8 个细领域 | 181 | 111（61.3%） | 43（23.8%） | 7（3.9%） | 20（11.1%） | 46 |

总计审查 254 条 Skill 记录。主要结论：

1. A 的质量纯度最高，但完整 Session 粒度较粗，容易漏掉切片内部的局部经验；
2. B 在质量、证据完整性和覆盖之间最均衡，保留了 A 的 25 个 Skill 家族并扩展出 23 个家族；
3. C 的原始 Skill 数最多，但 181 条记录去重后约为 46 个家族，存在明显的跨领域重复；
4. C 中有 20 条记录证据不足，因此更适合做领域候选召回，不宜直接作为 Skill 入库结果；
5. 当前更适合作为默认 Skill 提取输入的是 B：97 个切片直接提取。

本次比较的原始输入文件分别是：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\original-trace-llm-skill-audit-v1\analysis.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\slice-97-llm-skill-audit-v1\analysis.json
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test\domain-8-llm-skill-audit-v1\summary.json
```

## 9. 今日结论

今天得到的两个指标含义不同：

1. V6 的 75 个候选是算法生成的候选记录，其中只有 3 条被人工判为 high quality，且去重后约为 1 个独立 Skill 家族；
2. 原始轨迹 LLM 审计得到 25 条 Skill，说明单轨迹中存在不少局部但具体的可迁移经验，之前的跨 Session 或聚类一致性门槛会主动丢弃这些经验。

因此，后续比较算法时不能只比较候选数量，至少要同时比较：

- 原始轨迹 Skill 被候选覆盖的比例；
- 候选中的重复 Skill 数量；
- 候选是否保留了来源事件证据；
- 单来源高价值 Skill 是否被过滤；
- 多来源 Skill 是否被正确合并，而不是重复生成多个候选。

## 10. 验证记录

今天已完成的验证：

```text
python -m py_compile behavior_logic_clustering_v5.py behavior_logic_clustering_v6.py test_behavior_logic_clustering_v5.py test_behavior_logic_clustering_v6.py
python -m unittest discover -s master_work\experiments\trace-segmentation\dynatic-split-session-test -p "test_behavior_logic_clustering*.py" -q
```

已记录结果：测试通过，共 24 个测试；V6 final4 实验正常结束；三次 LLM 审计读取的源文件缺失数均为 0。97 切片审计的 48 条 Skill、8 个领域审计的 181 条 Skill 均通过必需字段检查；每条记录都包含来源切片、来源 Session、绝对文件路径和事件证据。三次 LLM 审计都只新增 JSON/Markdown 产物，没有修改代码或调用 embedding。

## 11. 当前工作区和提交状态

今天新增和生成的主要代码、测试及实验目录都位于：

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\trace-segmentation\dynatic-split-session-test
```

本记录只整理过程和产物路径，没有执行 Git commit 或 push。当前工作区中还存在其他历史实验目录和未提交文件；本记录中的最终可读结果以 V5 skill-space、V6 final4、三组 LLM Skill 提取产物和 `skill-experiment-horizontal-comparison-v1` 横向审查为准。
