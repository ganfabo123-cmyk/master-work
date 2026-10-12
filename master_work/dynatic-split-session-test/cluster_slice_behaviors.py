#!/usr/bin/env python3
"""Cluster all unique slice profiles by observable behavior only.

This experiment deliberately does not read domain assignments.  It uses the
materialized slice profiles and compares canonical action sequences, normalized
operation types, and coarse trace-size bins with weighted Jaccard similarity.
File types are reported as context but are not used as clustering features.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TOOL_RE = re.compile(r"^tool_call:(.+)$")


def read_profiles(path: Path) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_id[str(row["slice_id"])] = row
    return [by_id[key] for key in sorted(by_id)]


def action_label(label: str) -> str | None:
    match = TOOL_RE.match(label)
    if not match:
        return None
    name = match.group(1).lower()
    if name in {"read", "cat", "view", "open"}:
        return "inspect"
    if name in {"edit", "patch", "replace"}:
        return "modify"
    if name in {"write", "create"}:
        return "create"
    if name in {"bash", "powershell", "shell", "python", "run", "exec"}:
        return "execute"
    if name in {"grep", "glob", "find", "search", "toolsearch", "ls"}:
        return "search"
    if name in {"todowrite", "todo", "plan"}:
        return "plan"
    if name in {"browser", "computer", "screenshot", "viewimage"}:
        return "observe"
    return "tool"


def canonical_actions(profile: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    for label in profile.get("sequence", []):
        action = action_label(str(label))
        if action and (not actions or actions[-1] != action):
            actions.append(action)
    return actions


def normalized_operation(operation: str) -> str:
    name = operation.lower().split(":", 1)[0]
    if name in {"read", "inspect", "cat", "view"}:
        return "inspect"
    if name in {"edit", "modify", "patch", "replace"}:
        return "modify"
    if name in {"write", "create", "generate"}:
        return "create"
    if name in {"run", "exec", "execute", "shell", "powershell", "python", "bash"}:
        return "execute"
    if name in {"build", "compile", "test", "check", "lint"}:
        return "verify"
    if name in {"search", "grep", "glob", "find", "list", "ls"}:
        return "search"
    if name in {"fetch", "download", "install", "copy", "move", "remove", "delete"}:
        return "manage"
    if name in {"git", "commit", "push", "pull", "branch"}:
        return "version_control"
    return "other"


def feature_weights(profile: dict[str, Any]) -> dict[str, float]:
    actions = canonical_actions(profile)
    features: Counter[str] = Counter()
    for action in actions:
        features[f"action:{action}"] += 1.0
    for left, right in zip(actions, actions[1:]):
        features[f"transition:{left}>{right}"] += 2.0
    for left, middle, right in zip(actions, actions[1:], actions[2:]):
        features[f"trigram:{left}>{middle}>{right}"] += 2.5
    normalized_operations = Counter(normalized_operation(str(operation)) for operation in profile.get("operations", {}))
    for operation, count in normalized_operations.items():
        features[f"operation:{operation}"] += 1.0 + min(count, 4) * 0.15
    event_count = int(profile.get("event_count", 0))
    features[f"event_bin:{min(event_count // 100, 10)}"] += 0.4
    features[f"action_count_bin:{min(len(actions) // 5, 10)}"] += 0.4
    return dict(features)


def weighted_jaccard(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    numerator = sum(min(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)
    denominator = sum(max(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)
    return numerator / denominator if denominator else 1.0


def cluster_profiles(
    profiles: list[dict[str, Any]],
    features: dict[str, dict[str, float]],
    similarity_threshold: float,
) -> list[list[int]]:
    clusters: list[list[int]] = [[index] for index in range(len(profiles))]
    similarities: dict[tuple[int, int], float] = {}

    def similarity(left: int, right: int) -> float:
        key = (left, right) if left < right else (right, left)
        if key not in similarities:
            similarities[key] = weighted_jaccard(features[profiles[left]["slice_id"]], features[profiles[right]["slice_id"]])
        return similarities[key]

    while True:
        best: tuple[float, int, int] | None = None
        for left_index in range(len(clusters)):
            for right_index in range(left_index + 1, len(clusters)):
                pair_scores = [
                    similarity(left, right)
                    for left in clusters[left_index]
                    for right in clusters[right_index]
                ]
                score = min(pair_scores)
                if score >= similarity_threshold and (best is None or score > best[0]):
                    best = (score, left_index, right_index)
        if best is None:
            break
        _, left_index, right_index = best
        clusters[left_index].extend(clusters[right_index])
        del clusters[right_index]
    return [sorted(cluster) for cluster in clusters]


def sequence_similarity_summary(profiles: list[dict[str, Any]]) -> list[str]:
    counts = Counter(tuple(canonical_actions(profile)) for profile in profiles)
    return [" > ".join(sequence) for sequence, _ in counts.most_common(5)]


def aggregate_cluster(cluster_id: str, indices: list[int], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    members = [profiles[index] for index in indices]
    action_counts = Counter(action for profile in members for action in canonical_actions(profile))
    transition_counts = Counter()
    operation_counts = Counter()
    file_counts = Counter()
    session_ids: set[str] = set()
    for profile in members:
        actions = canonical_actions(profile)
        transition_counts.update(zip(actions, actions[1:]))
        operation_counts.update(profile.get("operations", {}))
        file_counts.update(profile.get("file_types", {}))
        parts = str(profile["slice_id"]).split("__")
        session_ids.add("__".join(parts[:-1]) if parts[-1].startswith("segment-") else str(profile["slice_id"]))
    representative = max(members, key=lambda row: (len(canonical_actions(row)), row.get("event_count", 0)))
    return {
        "behavior_cluster_id": cluster_id,
        "slice_count": len(members),
        "session_count": len(session_ids),
        "member_slice_ids": sorted(profile["slice_id"] for profile in members),
        "representative_slice_id": representative["slice_id"],
        "common_action_sequence_examples": sequence_similarity_summary(members),
        "common_actions": action_counts.most_common(),
        "common_transitions": [[left, right, count] for (left, right), count in transition_counts.most_common(12)],
        "common_operations": operation_counts.most_common(12),
        "common_file_types": file_counts.most_common(12),
        "event_count_range": [min(int(p.get("event_count", 0)) for p in members), max(int(p.get("event_count", 0)) for p in members)],
    }


def session_key(slice_id: str) -> str:
    parts = slice_id.split("__")
    return "__".join(parts[:-1]) if parts[-1].startswith("segment-") else slice_id


def relationship_report(clusters: list[dict[str, Any]]) -> dict[str, Any]:
    session_to_clusters: dict[str, set[str]] = defaultdict(set)
    cluster_to_sessions: dict[str, set[str]] = {}
    for cluster in clusters:
        sessions = {session_key(slice_id) for slice_id in cluster["member_slice_ids"]}
        cluster_to_sessions[cluster["behavior_cluster_id"]] = sessions
        for session in sessions:
            session_to_clusters[session].add(cluster["behavior_cluster_id"])
    split_sessions = {
        session: sorted(cluster_ids)
        for session, cluster_ids in session_to_clusters.items()
        if len(cluster_ids) > 1
    }
    cross_session_clusters = {
        cluster_id: sorted(sessions)
        for cluster_id, sessions in cluster_to_sessions.items()
        if len(sessions) > 1
    }
    return {
        "session_count": len(session_to_clusters),
        "split_session_count": len(split_sessions),
        "split_sessions": split_sessions,
        "cross_session_cluster_count": len(cross_session_clusters),
        "cross_session_clusters": cross_session_clusters,
    }


def write_report(output: Path, result: dict[str, Any]) -> None:
    lines = [
        "# 全局切片行为聚类 v1",
        "",
        "本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。",
        "",
        f"- 输入 slice 数：{result['input_slice_count']}",
        f"- 行为簇数：{result['cluster_count']}",
        f"- 相似度阈值：{result['similarity_threshold']}",
        f"- 原始 session 数：{result['relationships']['session_count']}",
        f"- 被拆成多个行为簇的 session 数：{result['relationships']['split_session_count']}",
        f"- 跨 session 行为簇数：{result['relationships']['cross_session_cluster_count']}",
        "",
        "## 行为簇概览",
        "",
        "| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |",
        "|---|---:|---:|---|---|---|",
    ]
    for cluster in result["clusters"]:
        sequence = cluster["common_action_sequence_examples"][0] if cluster["common_action_sequence_examples"] else ""
        operations = ", ".join(name for name, _ in cluster["common_operations"][:5])
        file_types = ", ".join(name for name, _ in cluster["common_file_types"][:5])
        lines.append(f"| {cluster['behavior_cluster_id']} | {cluster['slice_count']} | {cluster['session_count']} | {sequence} | {operations} | {file_types} |")
    lines.extend([
        "",
        "## 解释",
        "",
        "行为簇只根据规范化动作序列、动作转移、归一化操作类型和轨迹规模形成。文件类型只作为聚类后的上下文统计，不参与距离计算；实验不使用领域 token，也不使用已有 D001～D008 标签。",
        "",
        "`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。",
        "",
        "## 代表动作序列",
        "",
    ])
    for cluster in result["clusters"]:
        lines.append(f"### {cluster['behavior_cluster_id']}")
        lines.append("")
        lines.append("; ".join(cluster["common_action_sequence_examples"]) or "（无重复序列）")
        lines.append("")
        lines.append(f"常见转移：{cluster['common_transitions'][:6]}")
        lines.append("")
    (output / "behavior-clustering-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--similarity-threshold", type=float, default=0.42)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    profiles = read_profiles(args.profiles)
    feature_map = {profile["slice_id"]: feature_weights(profile) for profile in profiles}
    clusters_indices = cluster_profiles(profiles, feature_map, args.similarity_threshold)
    clusters = [
        aggregate_cluster(f"B{index:03d}", indices, profiles)
        for index, indices in enumerate(sorted(clusters_indices, key=lambda group: (-len(group), group[0])), 1)
    ]
    relationships = relationship_report(clusters)
    result = {
        "algorithm_version": "global-slice-behavior-v1",
        "input_profile_file": str(args.profiles),
        "input_slice_count": len(profiles),
        "cluster_count": len(clusters),
        "similarity": "weighted Jaccard over canonical action sequence, transitions, operations, file types, and size bins",
        "similarity_threshold": args.similarity_threshold,
        "clusters": clusters,
        "relationships": relationships,
    }
    (args.output / "behavior-clusters.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "behavior-clusters.md").write_text("# 全局切片行为聚类 v1\n\n详见 `behavior-clustering-report.md`。\n", encoding="utf-8")
    write_report(args.output, result)
    print(json.dumps({
        "input_slice_count": len(profiles),
        "cluster_count": len(clusters),
        "relationships": relationships | {"split_sessions": f"see {args.output / 'behavior-clusters.json'}"},
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
