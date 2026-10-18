# Behavior logic clustering package

- `positive/`: 正向目标聚类和执行逻辑聚类。
- `reverse/`: 反向 anti-clustering 多样性包；`target-reverse-clusters.json` 和 `logic-reverse-clusters.json` 主动压入低相似轨迹，保证成员覆盖。
- `sessions/raw-slices/`: 每个成员切片的完整原始 JSON，始终作为可回溯来源。
- `sessions/context-expanded/`: 可获得的 context-expanded session JSON。
- `sessions/relaxed/`: 可获得的 relaxed sliced-session 摘要。
- `PACKAGE_MANIFEST.json`: 输入路径、数量和缺失文件记录。

正向和反向结果均按 D001-D008 保留成员 ID；同一切片可能属于多个细领域，因此按领域查看时允许重复。
