# 正向聚类与反向策略融合结果包

本包的主结果在 `results/forward/`。正向分组仍以高相似轨迹共同覆盖为主要目标；反向多样性分组保存在 `results/reverse/`，只作为正向评分中的小权重策略证据，不作为独立主结果追加给下游 LLM。

- `results/forward/`：最终正向目标/逻辑分组。
- `results/reverse/`：内部反向多样性策略分组及审计证据。
- `results/shared/`：事件表示、相似度矩阵和领域特征配置。
- `sessions/`：全部 97 个原始切片 JSON。
- `session-index.jsonl`：session 文件与正向/反向归属索引。
- `algorithm/`：本轮脚本和测试。
- `comparison.md`：与 V3 正向基线和较强反向权重实验的对比。
