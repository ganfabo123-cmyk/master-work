# Embedding 切片聚类 v1

读取 message-embeddings.jsonl 中的原始 1024 维事件向量，按词在切片中的文档频率计算非线性稀有度，再对核心事件做加权池化并 L2 归一化。record:* 和 tool_result 不删除，只通过来源先验与协议词质量降权。使用 complete-linkage 层次聚类，在 2–12 个簇中选择平均 silhouette 最高的切分。该选择是数据驱动的探索性规则，不是监督校准阈值。没有使用 message-vector-map.json 或 tool-vector-map.json 的人工标量映射。
