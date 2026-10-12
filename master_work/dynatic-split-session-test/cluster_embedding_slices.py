"""Cluster materialized slices using rarity-weighted message embeddings.

The event representation is the original 1024-dimensional embedding. No
category-to-scalar mapping is used. Token document frequency across slices
controls a nonlinear rarity weight; record and tool-result events remain
eligible but receive a lower source prior.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def session_key(slice_id: str) -> str:
    return slice_id.rsplit("__segment-", 1)[0].split("__", 1)[-1]


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def cosine_distance(left: list[float], right: list[float]) -> float:
    return max(0.0, min(2.0, 1.0 - sum(a * b for a, b in zip(left, right))))


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.-]{1,}|[\u3400-\u9fff]{2,}")
PROTOCOL_TOKENS = {
    "category", "part_type", "role", "metadata", "record", "tool_result", "assistant",
    "user", "system", "source_index", "source_part_index", "event_index", "session_id",
    "harness", "input_text", "tool_name", "arguments", "present", "payload", "type",
}


def tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in TOKEN_RE.finditer(text)}


def token_quality(token: str) -> float:
    if token in PROTOCOL_TOKENS or len(token) < 3:
        return 0.12
    if token.isdigit() or re.fullmatch(r"[0-9a-f]{8,}", token):
        return 0.15
    if any(symbol in token for symbol in ("##", "++", "...")) or token[0] in ".-_" or token[-1] in ".-_":
        return 0.15
    if re.search(r"[a-z]", token) and re.search(r"\d", token) and "_" not in token and len(token) <= 8:
        return 0.25
    return 1.0


def nonlinear_rarity(document_frequency: int, slice_count: int) -> float:
    proportion = document_frequency / max(slice_count, 1)
    left = 1.0 - proportion
    return (left * left) / max(left * left + proportion * proportion, 1e-12)


def slice_intervals(slices: list[dict]) -> dict[str, list[tuple[int, int, int]]]:
    intervals: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for index, item in enumerate(slices):
        intervals[session_key(item["slice_id"])].append(
            (int(item["core_start_event"]), int(item["core_end_event"]), index)
        )
    return intervals


def collect_token_document_frequency(embedding_path: Path, slices: list[dict], intervals: dict[str, list[tuple[int, int, int]]]) -> dict[str, int]:
    slice_tokens = [set() for _ in slices]
    with embedding_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            event_session = row["session_id"]
            event_index = int(row["event_index"])
            event_tokens = tokens(row.get("input_text", ""))
            for start, end, slice_index in intervals.get(event_session, ()):
                if start <= event_index <= end:
                    slice_tokens[slice_index].update(event_tokens)
    frequencies: dict[str, int] = defaultdict(int)
    for token_set in slice_tokens:
        for token in token_set:
            frequencies[token] += 1
    return dict(frequencies)


def event_weight(row: dict, token_df: dict[str, int], slice_count: int) -> float:
    event_tokens = tokens(row.get("input_text", ""))
    if event_tokens:
        scores = sorted(
            (nonlinear_rarity(token_df.get(token, 0), slice_count) * token_quality(token) for token in event_tokens),
            reverse=True,
        )
        content_weight = sum(scores[:8]) / min(8, len(scores))
    else:
        content_weight = 0.0
    category = str(row.get("category", ""))
    source_weight = 0.15 if category.startswith("record:") else 0.45 if category == "tool_result" else 1.0
    return max(0.01, source_weight * content_weight)


def pool_slice_vectors(embedding_path: Path, slices: list[dict]) -> tuple[list[list[float]], dict[str, int], dict[str, float], dict[str, int]]:
    intervals = slice_intervals(slices)
    token_df = collect_token_document_frequency(embedding_path, slices, intervals)
    sums: list[list[float] | None] = [None] * len(slices)
    counts = [0] * len(slices)
    weight_sums = [0.0] * len(slices)
    dimension = None
    with embedding_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            event_session = row["session_id"]
            event_index = int(row["event_index"])
            vector = row["embedding"]
            if dimension is None:
                dimension = len(vector)
            norm = math.sqrt(sum(float(value) * float(value) for value in vector))
            unit_vector = [float(value) / norm for value in vector] if norm else [float(value) for value in vector]
            weight = event_weight(row, token_df, len(slices))
            for start, end, slice_index in intervals.get(event_session, ()):
                if start <= event_index <= end:
                    if sums[slice_index] is None:
                        sums[slice_index] = [0.0] * dimension
                    target = sums[slice_index]
                    for position, value in enumerate(unit_vector):
                        target[position] += weight * value
                    counts[slice_index] += 1
                    weight_sums[slice_index] += weight
    missing = {slices[index]["slice_id"]: counts[index] for index in range(len(slices)) if not counts[index]}
    if missing:
        raise ValueError(f"missing embeddings for {len(missing)} slices: {list(missing)[:3]}")
    vectors = [normalize([value / max(weight_sums[index], 1e-12) for value in sums[index]]) for index in range(len(slices))]
    return (
        vectors,
        {slices[index]["slice_id"]: counts[index] for index in range(len(slices))},
        {slices[index]["slice_id"]: weight_sums[index] for index in range(len(slices))},
        token_df,
    )


def complete_linkage(vectors: list[list[float]]) -> tuple[list[list[int]], list[float], dict[int, list[list[int]]]]:
    clusters = [[index] for index in range(len(vectors))]
    distances: list[float] = []
    partitions = {len(clusters): [cluster[:] for cluster in clusters]}
    while len(clusters) > 1:
        best = None
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                distance = max(
                    cosine_distance(vectors[a], vectors[b])
                    for a in clusters[left]
                    for b in clusters[right]
                )
                candidate = (distance, clusters[left][0], clusters[right][0], left, right)
                if best is None or candidate < best:
                    best = candidate
        distance, _left_id, _right_id, left, right = best
        merged = sorted(clusters[left] + clusters[right])
        clusters = [cluster for index, cluster in enumerate(clusters) if index not in (left, right)]
        clusters.append(merged)
        distances.append(distance)
        partitions[len(clusters)] = [cluster[:] for cluster in clusters]
    return clusters, distances, partitions


def silhouette(vectors: list[list[float]], groups: list[list[int]]) -> float:
    distances = [[cosine_distance(left, right) for right in vectors] for left in vectors]
    labels = {index: group for group, members in enumerate(groups) for index in members}
    scores = []
    for index in range(len(vectors)):
        own = [other for other in groups[labels[index]] if other != index]
        if not own:
            continue
        within = sum(distances[index][other] for other in own) / len(own)
        between = min(
            sum(distances[index][other] for other in members) / len(members)
            for group, members in enumerate(groups) if group != labels[index]
        )
        scores.append((between - within) / max(within, between, 1e-12))
    return sum(scores) / len(scores) if scores else -1.0


def cluster_at_cut(vectors: list[list[float]], cut: float) -> list[list[int]]:
    clusters = [[index] for index in range(len(vectors))]
    while True:
        best = None
        for left in range(len(clusters)):
            for right in range(left + 1, len(clusters)):
                distance = max(cosine_distance(vectors[a], vectors[b]) for a in clusters[left] for b in clusters[right])
                candidate = (distance, left, right)
                if best is None or candidate < best:
                    best = candidate
        if best is None or best[0] > cut:
            return sorted(clusters, key=lambda group: (-len(group), group))
        _distance, left, right = best
        merged = sorted(clusters[left] + clusters[right])
        clusters = [cluster for index, cluster in enumerate(clusters) if index not in (left, right)]
        clusters.append(merged)


def run(embedding_path: Path, slices_path: Path, output: Path) -> dict:
    slices = read_json(slices_path)
    vectors, event_counts, weight_sums, token_df = pool_slice_vectors(embedding_path, slices)
    _final, distances, partitions = complete_linkage(vectors)
    max_k = min(12, len(vectors) // 2)
    scored_partitions = [
        (silhouette(vectors, partitions[k]), k)
        for k in range(2, max_k + 1)
        if sum(len(group) == 1 for group in partitions[k]) <= max(1, len(vectors) // 50)
    ]
    if not scored_partitions:
        raise ValueError("no candidate partition has at least two members per cluster")
    best_silhouette, selected_k = max(scored_partitions, key=lambda item: (item[0], -item[1]))
    groups = partitions[selected_k]
    cut = distances[len(vectors) - selected_k - 1] if selected_k < len(vectors) else 0.0
    accepted = [group for group in groups if len(group) >= 2]
    assignments = {item["slice_id"]: [] for item in slices}
    clusters = []
    for number, members in enumerate(accepted, 1):
        member_ids = [slices[index]["slice_id"] for index in members]
        pair_distances = [cosine_distance(vectors[left], vectors[right]) for position, left in enumerate(members) for right in members[position + 1:]]
        cluster = {
            "cluster_id": f"E{number:03d}",
            "member_count": len(members),
            "session_count": len({session_key(item) for item in member_ids}),
            "members": member_ids,
            "minimum_pair_cosine": round(1.0 - max(pair_distances), 6),
            "mean_pair_cosine": round(1.0 - sum(pair_distances) / len(pair_distances), 6),
            "embedding_event_counts": {item: event_counts[item] for item in member_ids},
            "effective_weight_sums": {item: round(weight_sums[item], 6) for item in member_ids},
        }
        clusters.append(cluster)
        for item in member_ids:
            assignments[item].append(cluster["cluster_id"])
    summary = {
        "algorithm_version": "embedding-slice-v1",
        "representation": "weighted mean of per-event unit 1024-dimensional embeddings; token rarity and source quality weights",
        "no_category_to_scalar_mapping": True,
        "slice_count": len(slices),
        "embedding_event_count": sum(event_counts.values()),
        "effective_weight_sum": round(sum(weight_sums.values()), 6),
        "token_vocabulary_size": len(token_df),
        "rarity_weight_formula": "((1-p)^2)/((1-p)^2+p^2), p=document_frequency/slice_count",
        "source_priors": {"record:*": 0.15, "tool_result": 0.45, "other": 1.0},
        "embedding_dimension": len(vectors[0]),
        "complete_linkage_merge_count": len(distances),
        "selected_cluster_count_by_silhouette": selected_k,
        "selected_average_silhouette": round(best_silhouette, 6),
        "automatic_distance_cut": round(cut, 6),
        "cluster_count": len(clusters),
        "clustered_slice_count": sum(len(group) for group in accepted),
        "unclustered_slice_count": sum(len(group) == 1 for group in groups),
        "input_sha256": {
            "embeddings": hashlib.sha256(embedding_path.read_bytes()).hexdigest(),
            "slices": hashlib.sha256(slices_path.read_bytes()).hexdigest(),
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "summary.json", summary)
    write_json(output / "clusters.json", clusters)
    write_json(output / "assignments.json", assignments)
    write_json(output / "token-document-frequency.json", dict(sorted(token_df.items(), key=lambda item: (item[1], item[0]))))
    write_json(output / "slice-vectors.json", [{"slice_id": item["slice_id"], "event_count": event_counts[item["slice_id"]], "vector": vectors[index]} for index, item in enumerate(slices)])
    write_json(output / "linkage-distances.json", distances)
    lines = [
        "# Embedding 切片聚类 v1", "",
        f"{summary['slice_count']} 个切片；原始 {summary['embedding_dimension']} 维事件 embedding；silhouette 选择 {selected_k} 个簇（平均 {best_silhouette:.4f}）；{summary['cluster_count']} 个簇含至少 2 个切片；{summary['clustered_slice_count']} 个切片入簇。", "",
        "切片向量是核心事件 embedding 的稀有词加权均值；record:* 和 tool_result 仍参与，但协议词和来源先验会降权。没有使用 category-to-number 映射。簇是数学候选，仍需检查任务混杂和跨会话复现。", "",
        "| 簇 | 成员 | 会话 | 最弱两两余弦 | 平均两两余弦 |", "|---|---:|---:|---:|---:|",
    ]
    for cluster in clusters:
        lines.append(f"| {cluster['cluster_id']} | {cluster['member_count']} | {cluster['session_count']} | {cluster['minimum_pair_cosine']:.4f} | {cluster['mean_pair_cosine']:.4f} |")
        lines.extend(["", f"## {cluster['cluster_id']}", ""])
        lines.extend(f"- `{item}`" for item in cluster["members"])
    (output / "clusters.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# Embedding 切片聚类 v1\n\n"
        "读取 message-embeddings.jsonl 中的原始 1024 维事件向量，按词在切片中的文档频率计算非线性稀有度，再对核心事件做加权池化并 L2 归一化。record:* 和 tool_result 不删除，只通过来源先验与协议词质量降权。"
        "使用 complete-linkage 层次聚类，在 2–12 个簇中选择平均 silhouette 最高的切分。该选择是数据驱动的探索性规则，不是监督校准阈值。"
        "没有使用 message-vector-map.json 或 tool-vector-map.json 的人工标量映射。\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--slices", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.embeddings, args.slices, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
