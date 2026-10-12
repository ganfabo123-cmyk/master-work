# Embedding 切片聚类 v1

读取 message-embeddings.jsonl 中的原始 1024 维事件向量，排除 record:* 和 tool_result 后按切片核心事件区间做均值池化并 L2 归一化。使用 complete-linkage 层次聚类，在 2–12 个簇中选择平均 silhouette 最高的切分。该选择是数据驱动的探索性规则，不是监督校准阈值。没有使用 message-vector-map.json 或 tool-vector-map.json 的人工标量映射。
