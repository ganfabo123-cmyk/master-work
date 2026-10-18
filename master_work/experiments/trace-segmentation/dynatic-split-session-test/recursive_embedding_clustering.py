"""Recursively refine embedding clusters under an explicit cohesion gate."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cosine_distance(left: list[float], right: list[float]) -> float:
    return max(0.0, min(2.0, 1.0 - sum(a * b for a, b in zip(left, right))))


def cohesion(vectors: list[list[float]], members: list[int]) -> float:
    distances = [
        cosine_distance(vectors[left], vectors[right])
        for position, left in enumerate(members)
        for right in members[position + 1:]
    ]
    return 1.0 - sum(distances) / len(distances) if distances else 1.0


def complete_linkage_partitions(vectors: list[list[float]], members: list[int]) -> dict[int, list[list[int]]]:
    groups = [[member] for member in members]
    partitions = {len(groups): [group[:] for group in groups]}
    while len(groups) > 1:
        best = None
        for left in range(len(groups)):
            for right in range(left + 1, len(groups)):
                distance = max(
                    cosine_distance(vectors[a], vectors[b])
                    for a in groups[left]
                    for b in groups[right]
                )
                candidate = (distance, groups[left][0], groups[right][0], left, right)
                if best is None or candidate < best:
                    best = candidate
        _distance, _left_id, _right_id, left, right = best
        merged = sorted(groups[left] + groups[right])
        groups = [group for index, group in enumerate(groups) if index not in (left, right)]
        groups.append(merged)
        partitions[len(groups)] = [group[:] for group in groups]
    return partitions


def silhouette(vectors: list[list[float]], groups: list[list[int]]) -> float:
    labels = {member: index for index, group in enumerate(groups) for member in group}
    scores = []
    for member in labels:
        own = [other for other in groups[labels[member]] if other != member]
        if not own:
            continue
        within = sum(cosine_distance(vectors[member], vectors[other]) for other in own) / len(own)
        between = min(
            sum(cosine_distance(vectors[member], vectors[other]) for other in group) / len(group)
            for index, group in enumerate(groups) if index != labels[member]
        )
        scores.append((between - within) / max(within, between, 1e-12))
    return sum(scores) / len(scores) if scores else -1.0


def best_split(vectors: list[list[float]], members: list[int], max_children: int) -> tuple[list[list[int]], float] | None:
    if len(members) < 2 * 2:
        return None
    partitions = complete_linkage_partitions(vectors, members)
    candidates = []
    for child_count in range(2, min(max_children, len(members) // 2) + 1):
        groups = partitions[child_count]
        if sum(len(group) == 1 for group in groups) > 1:
            continue
        candidates.append((silhouette(vectors, groups), groups))
    if not candidates:
        return None
    score, groups = max(candidates, key=lambda item: (item[0], -len(item[1])))
    return groups, score


def size_penalty(member_count: int, alpha: float) -> float:
    """Lower the retain-confidence of large clusters smoothly."""
    if alpha <= 0.0 or member_count <= 1:
        return 1.0
    return 1.0 / (1.0 + alpha * math.log2(member_count))


def run(
    vectors_path: Path,
    initial_clusters_path: Path,
    output: Path,
    threshold: float,
    max_depth: int,
    min_split_size: int,
    size_penalty_alpha: float,
) -> dict:
    vector_rows = read_json(vectors_path)
    initial = read_json(initial_clusters_path)
    vectors = [row["vector"] for row in vector_rows]
    index_by_id = {row["slice_id"]: index for index, row in enumerate(vector_rows)}
    tree_nodes = []
    leaves = []
    assignments = {row["slice_id"]: [] for row in vector_rows}

    def visit(node_id: str, members: list[int], depth: int, parent: str | None) -> None:
        raw_score = cohesion(vectors, members)
        penalty = size_penalty(len(members), size_penalty_alpha)
        score = raw_score * penalty
        node = {
            "node_id": node_id,
            "parent_id": parent,
            "depth": depth,
            "member_count": len(members),
            "raw_execution_degree": round(raw_score, 6),
            "size_penalty": round(penalty, 6),
            "execution_degree": round(score, 6),
            "members": [vector_rows[index]["slice_id"] for index in members],
        }
        # The adjusted execution degree is retain-confidence.  Large or
        # heterogeneous groups fall below the gate and are refined further.
        should_split = score < threshold and len(members) >= min_split_size and depth < max_depth
        split = best_split(vectors, members, max_children=8) if should_split else None
        if split is None:
            node["is_leaf"] = True
            node["stop_reason"] = "below_threshold" if score >= threshold else "no_valid_split"
            leaves.append(node)
            for member in node["members"]:
                assignments[member].append(node_id)
        else:
            groups, split_score = split
            node["is_leaf"] = False
            node["split_silhouette"] = round(split_score, 6)
            node["children"] = []
            tree_nodes.append(node)
            for number, group in enumerate(groups, 1):
                child_id = f"{node_id}.{number}"
                node["children"].append(child_id)
                visit(child_id, group, depth + 1, node_id)
        if node not in tree_nodes and node not in leaves:
            leaves.append(node)

    for root in initial:
        members = [index_by_id[item] for item in root["members"]]
        visit(root["cluster_id"], members, 0, None)

    summary = {
        "algorithm_version": "recursive-embedding-cluster-v2-size-penalty",
        "threshold": threshold,
        "size_penalty_alpha": size_penalty_alpha,
        "size_penalty_formula": "1 / (1 + alpha * log2(member_count))",
        "max_depth": max_depth,
        "min_split_size": min_split_size,
        "root_cluster_count": len(initial),
        "leaf_cluster_count": len(leaves),
        "clustered_slice_count": sum(len(leaf["members"]) for leaf in leaves),
        "leaf_sizes": [len(leaf["members"]) for leaf in leaves],
        "input_vector_count": len(vector_rows),
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "summary.json", summary)
    write_json(output / "tree.json", tree_nodes + leaves)
    write_json(output / "leaves.json", leaves)
    write_json(output / "assignments.json", assignments)
    lines = [
        "# 递归 embedding 聚类 v2（规模惩罚）", "",
        f"执行度阈值 {threshold:.2f}；根簇 {len(initial)} 个；叶簇 {len(leaves)} 个；最大深度 {max_depth}。", "",
        f"原始执行度为簇内成员两两余弦相似度平均值；保留执行度 = 原始执行度 × 1/(1 + {size_penalty_alpha:g} × log2(轨迹数))。保留执行度低于阈值的簇继续细分，高于阈值的簇作为叶簇。", "",
        "| 节点 | 深度 | 成员 | 执行度 | 状态 |", "|---|---:|---:|---:|---|",
    ]
    for node in tree_nodes + leaves:
        lines.append(f"| {node['node_id']} | {node['depth']} | {node['member_count']} | {node['execution_degree']:.4f} | {'leaf' if node['is_leaf'] else 'split'} |")
    (output / "clusters.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--initial-clusters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--min-split-size", type=int, default=8)
    parser.add_argument("--size-penalty-alpha", type=float, default=0.08)
    args = parser.parse_args()
    print(json.dumps(run(args.vectors, args.initial_clusters, args.output, args.threshold, args.max_depth, args.min_split_size, args.size_penalty_alpha), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
