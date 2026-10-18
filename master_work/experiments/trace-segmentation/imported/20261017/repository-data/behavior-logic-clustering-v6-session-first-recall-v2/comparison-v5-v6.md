# V5 与 V6 Skill 召回对比

本次比较使用原始 30 个 Session Trace 审计得到的 Skill inventory。V6 的覆盖统计只判断某个原始 Skill 的全部 trace 是否共同出现在至少一个 family 中，因此是结构覆盖上界，不等同于人工确认后的 Skill 提取率。

| 指标 | V5 | V6 |
|---|---:|---:|
| 唯一切片 | 97 | 97 |
| 原始 Session | 30 | 30 |
| Skill family / candidate | 41 | 120 |
| Session 级表示 | 否 | 是 |
| 容量硬拆分 | 是 | 否 |
| 严格 Skill 家族覆盖 | 1/4（人工确认 1 个） | 4/4（结构覆盖上界） |
| 宽松 Skill 家族覆盖 | 6/8（人工确认 6 个可利用） | 6/8（结构覆盖上界） |

V6 的严格 4/4 不能直接写成严格 Skill 召回率 100%。其中 S1 包含多个独立 Session，V6 确实把它们放进了共同 family；S2、S3、S4 各只有一个原始 Trace，共同出现的覆盖证据较弱。要得到 V6 的语义 Skill 损失率，还需要沿用 V5 的人工审查标准逐个审查 V6 family。

V6 的主要变化是先把切片聚合到原始 Session，再用多个视图的局部邻居并集生成重叠 family。family 不受 8 条容量限制，容量只保留为下游批处理提示。V6 最终生成 120 个 family，跨领域累计只有 2 个 residual Session；候选数量增加是为了降低 Skill 被拆散的风险。
