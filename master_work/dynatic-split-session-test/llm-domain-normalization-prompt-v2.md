# 领域归一化任务

你正在处理一组由无监督算法产生的粗领域簇。你的任务不是重新阅读轨迹，也不是分析行为，而是根据每个簇的低成本特征卡片，整理出一个尽可能少但信息完整的领域层。

请严格遵守：

1. 只能使用输入卡片中的 `core_terms`、`top_terms_by_frequency`、`term_support_count`、`representative_first_user_inputs`、`matched_core_terms` 和簇统计信息。
2. 不要引入卡片中没有出现的技术名、项目名或领域名作为证据。
3. `page`、`file`、`server`、`session`、`index`、`project`、`build` 等跨多个簇出现的词只能作为背景词，不能单独定义领域。
4. 区分三种关系：
   - `parent_of`：一个簇是另一个领域的上位领域；
   - `merge`：多个粗簇实际上属于同一个领域；
   - `keep`：簇应当保持独立。
5. 如果一个簇同时包含多个明显不同的领域，不要强行命名；将它放入 `mixed_clusters`，并说明需要依据哪些词进一步拆分。
6. 如果证据不足，使用 `unresolved_clusters`。不要猜测。
7. 不要输出 confidence、概率、分数、排名或任何没有统计校准依据的字段。
8. 不要逐条复述轨迹，只输出领域层整理结果和必要的证据词。

请输出严格 JSON，字段只能是：

```json
{
  "domains": [
    {
      "domain_id": "新领域 ID",
      "name": "简洁领域名",
      "relation": "keep 或 merge 或 parent_of",
      "source_clusters": ["D001"],
      "core_terms": ["来自卡片的词"],
      "evidence": ["来自代表首句或词项的短证据"],
      "split_hints": ["如果需要继续拆分，说明拆分维度"]
    }
  ],
  "mixed_clusters": [
    {
      "cluster_id": "D001",
      "evidence": ["导致混合判断的词"],
      "split_hints": ["建议的数学或领域拆分维度"]
    }
  ],
  "unresolved_clusters": ["D002"],
  "merge_relations": [
    {"source_clusters": ["D003", "D004"], "parent_domain": "领域名"}
  ]
}
```

`core_terms` 必须从输入卡片已有词项中选择。`evidence` 必须引用输入卡片中出现过的词或首句中的短语。领域名可以是这些证据词的简洁归纳，但不能添加没有证据支持的新技术。
