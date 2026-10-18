"""Generate reproducible, overlapping clusters from cheap slice signals."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


CONFIG = {
    "version": "v0.2",
    "task_top_k": 20,
    "candidate_posting_limit": 1000,
    "candidate_posting_fraction": 0.25,
    "weights": {"task": 0.50, "action_object": 0.15, "operation_file": 0.25, "operation_type": 0.10},
    "minimum_joint_similarity": 0.18,
    "minimum_task_similarity_same_session": 0.23,
    "minimum_task_similarity_cross_session": 0.10,
    "secondary_minima": {"action_object": 0.10, "operation_file": 0.05, "operation_type": 0.25},
    "cross_session_secondary_minima": {"action_object": 0.20, "operation_file": 0.25},
    "minimum_cluster_size": 2,
    "minimum_distinct_sessions": 2,
    "cluster_rule": "maximal clique of accepted pair edges; slice may belong to multiple clusters",
    "evidence_score": {
        "task_weight": 0.35,
        "concrete_operation_weight": 0.35,
        "joint_weight": 0.20,
        "cross_session_weight": 0.10,
        "task_saturation": 0.30,
        "operation_file_saturation": 0.30,
        "action_object_saturation": 0.25,
        "joint_saturation": 0.30,
        "aggregation": "minimum pair score within cluster",
        "threshold": 0.75,
        "interpretation": "heuristic evidence gate, not a calibrated probability",
    },
}
VIEWS = ("task", "action_object", "operation_file", "operation_type")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def session_key(slice_id: str) -> str:
    return slice_id.rsplit("__segment-", 1)[0]


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    if dot == 0:
        return 0.0
    return dot / math.sqrt(sum(value * value for value in left.values()) * sum(value * value for value in right.values()))


def with_slice_idf(vectors: list[dict[str, float]]) -> list[dict[str, float]]:
    frequency = Counter()
    for vector in vectors:
        frequency.update(vector)
    count = len(vectors)
    return [
        {key: value * (1 + math.log((count + 1) / (frequency[key] + 1))) for key, value in vector.items()}
        for vector in vectors
    ]


def vectors_for(text_rows: list[dict], tool_rows: list[dict]) -> dict[str, list[dict[str, float]]]:
    task = [{item["token"]: item["score"] for item in row["task_signals"][:CONFIG["task_top_k"]]} for row in text_rows]
    action = [{item["action"] + "+" + item["object"]: item["score"] for item in row["action_object_pairs"]} for row in text_rows]
    operation_file = [
        {item["operation"] + "+" + item["target"]: math.log1p(item["event_count"]) for item in row["operation_target_events"]}
        for row in tool_rows
    ]
    operation_type = [
        {item["operation"] + "+" + item["file_type"]: math.log1p(item["event_count"]) for item in row["operation_file_type_events"]}
        for row in tool_rows
    ]
    return {"task": task, "action_object": with_slice_idf(action), "operation_file": with_slice_idf(operation_file), "operation_type": with_slice_idf(operation_type)}


def candidate_pairs(task_vectors: list[dict[str, float]]) -> set[tuple[int, int]]:
    postings = defaultdict(list)
    for index, vector in enumerate(task_vectors):
        for token in vector:
            postings[token].append(index)
    count = len(task_vectors)
    limit = min(CONFIG["candidate_posting_limit"], max(24, int(count * CONFIG["candidate_posting_fraction"])))
    candidates = set()
    for members in postings.values():
        if len(members) > limit:
            continue
        for position, left in enumerate(members):
            for right in members[position + 1:]:
                candidates.add((left, right))
    return candidates


def accepted_pair(left: int, right: int, rows: list[dict], vectors: dict[str, list[dict[str, float]]]) -> dict | None:
    scores = {view: cosine(vectors[view][left], vectors[view][right]) for view in VIEWS}
    joint = sum(CONFIG["weights"][view] * scores[view] for view in VIEWS)
    same_session = session_key(rows[left]["slice_id"]) == session_key(rows[right]["slice_id"])
    task_minimum = CONFIG["minimum_task_similarity_same_session"] if same_session else CONFIG["minimum_task_similarity_cross_session"]
    if joint < CONFIG["minimum_joint_similarity"] or scores["task"] < task_minimum:
        return None
    secondary = CONFIG["secondary_minima"] if same_session else CONFIG["cross_session_secondary_minima"]
    if not any(scores[view] >= minimum for view, minimum in secondary.items()):
        return None
    shared = {
        view: sorted(set(vectors[view][left]) & set(vectors[view][right]), key=lambda key: (-min(vectors[view][left][key], vectors[view][right][key]), key))[:8]
        for view in VIEWS
    }
    return {
        "left": rows[left]["slice_id"], "right": rows[right]["slice_id"],
        "joint_similarity": round(joint, 4),
        "view_similarities": {view: round(scores[view], 4) for view in VIEWS},
        "same_session": same_session,
        "shared_features": shared,
    }


def maximal_cliques(adjacency: list[set[int]]) -> list[list[int]]:
    result = []

    def visit(members: set[int], pending: set[int], used: set[int]) -> None:
        if not pending and not used:
            if len(members) >= CONFIG["minimum_cluster_size"]:
                result.append(sorted(members))
            return
        pivot = max(pending | used, key=lambda index: (len(adjacency[index] & pending), -index), default=None)
        choices = pending - (adjacency[pivot] if pivot is not None else set())
        for vertex in sorted(choices):
            visit(members | {vertex}, pending & adjacency[vertex], used & adjacency[vertex])
            pending.remove(vertex)
            used.add(vertex)

    visit(set(), set(range(len(adjacency))), set())
    return sorted(result, key=lambda group: (-len(group), group))


def cluster_evidence(members: list[int], vectors: dict[str, list[dict[str, float]]]) -> dict[str, list[str]]:
    result = {}
    for view in VIEWS:
        support = Counter()
        strength = Counter()
        for index in members:
            support.update(vectors[view][index].keys())
            strength.update(vectors[view][index])
        result[view] = [key for key, count in sorted(support.items(), key=lambda item: (-item[1], -strength[item[0]], item[0])) if count >= 2][:8]
    return result


def pair_evidence_score(edge: dict) -> float:
    settings = CONFIG["evidence_score"]
    views = edge["view_similarities"]
    task = min(1.0, views["task"] / settings["task_saturation"])
    concrete = max(
        min(1.0, views["operation_file"] / settings["operation_file_saturation"]),
        min(1.0, views["action_object"] / settings["action_object_saturation"]),
    )
    joint = min(1.0, edge["joint_similarity"] / settings["joint_saturation"])
    return (
        settings["task_weight"] * task
        + settings["concrete_operation_weight"] * concrete
        + settings["joint_weight"] * joint
        + settings["cross_session_weight"] * (not edge["same_session"])
    )


def run(text_path: Path, tool_path: Path, output: Path) -> dict:
    text_rows = read_jsonl(text_path)
    tool_rows = read_jsonl(tool_path)
    if [row["slice_id"] for row in text_rows] != [row["slice_id"] for row in tool_rows]:
        raise ValueError("Signal files have different slice ordering or IDs")
    if len({row["slice_id"] for row in text_rows}) != len(text_rows):
        raise ValueError("Duplicate slice IDs")
    vectors = vectors_for(text_rows, tool_rows)
    candidates = candidate_pairs(vectors["task"])
    adjacency = [set() for _ in text_rows]
    pair_rows = []
    accepted = {}
    for left, right in sorted(candidates):
        edge = accepted_pair(left, right, text_rows, vectors)
        if edge is None:
            continue
        adjacency[left].add(right)
        adjacency[right].add(left)
        pair_rows.append(edge)
        accepted[(left, right)] = edge
    groups = maximal_cliques(adjacency)
    candidate_clusters = []
    for number, members in enumerate(groups, 1):
        member_ids = [text_rows[index]["slice_id"] for index in members]
        edges = [accepted[(left, right)] for position, left in enumerate(members) for right in members[position + 1:]]
        evidence = cluster_evidence(members, vectors)
        candidate_clusters.append({
            "candidate_id": f"P{number:03d}",
            "evidence_score": round(min(pair_evidence_score(edge) for edge in edges), 4),
            "suggested_name_terms": evidence["task"][:3],
            "member_count": len(members),
            "session_count": len({session_key(slice_id) for slice_id in member_ids}),
            "members": member_ids,
            "minimum_pair_similarity": min(edge["joint_similarity"] for edge in edges),
            "mean_pair_similarity": round(sum(edge["joint_similarity"] for edge in edges) / len(edges), 4),
            "shared_features": evidence,
            "pair_edges": edges,
        })
    clusters = []
    deferred = []
    assignments = {row["slice_id"]: [] for row in text_rows}
    threshold = CONFIG["evidence_score"]["threshold"]
    for candidate in candidate_clusters:
        reasons = []
        if candidate["evidence_score"] < threshold:
            reasons.append("evidence_score_below_threshold")
        if candidate["session_count"] < CONFIG["minimum_distinct_sessions"]:
            reasons.append("insufficient_distinct_sessions")
        if reasons:
            deferred.append({**candidate, "defer_reasons": reasons})
            continue
        cluster = {"cluster_id": f"C{len(clusters) + 1:03d}", **candidate}
        clusters.append(cluster)
        for slice_id in cluster["members"]:
            assignments[slice_id].append(cluster["cluster_id"])
    unclustered = [slice_id for slice_id, memberships in assignments.items() if not memberships]
    summary = {
        "algorithm_version": CONFIG["version"],
        "slice_count": len(text_rows),
        "candidate_pair_count": len(candidates),
        "accepted_pair_count": len(pair_rows),
        "candidate_cluster_count": len(candidate_clusters),
        "evidence_score_threshold": threshold,
        "minimum_distinct_sessions": CONFIG["minimum_distinct_sessions"],
        "cluster_count": len(clusters),
        "deferred_candidate_count": len(deferred),
        "deferred_by_score_count": sum("evidence_score_below_threshold" in candidate["defer_reasons"] for candidate in deferred),
        "deferred_by_sessions_count": sum("insufficient_distinct_sessions" in candidate["defer_reasons"] for candidate in deferred),
        "cross_session_cluster_count": sum(cluster["session_count"] > 1 for cluster in clusters),
        "cross_session_skill_sampling_candidate_count": sum(cluster["session_count"] > 1 for cluster in clusters),
        "clustered_slice_count": len(text_rows) - len(unclustered),
        "unclustered_slice_count": len(unclustered),
        "multiple_membership_slice_count": sum(len(memberships) > 1 for memberships in assignments.values()),
        "input_sha256": {
            "event_behavior_signals": hashlib.sha256(text_path.read_bytes()).hexdigest(),
            "tool_operation_signals": hashlib.sha256(tool_path.read_bytes()).hexdigest(),
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "config.json", CONFIG)
    write_json(output / "summary.json", summary)
    write_json(output / "clusters.json", clusters)
    write_json(output / "candidate-clusters.json", candidate_clusters)
    write_json(output / "deferred-candidates.json", deferred)
    write_json(output / "assignments.json", assignments)
    write_json(output / "unclustered.json", unclustered)
    with (output / "accepted-pairs.jsonl").open("w", encoding="utf-8") as stream:
        for edge in pair_rows:
            stream.write(json.dumps(edge, ensure_ascii=False) + "\n")
    lines = [
        "# 切片聚类 v0.2", "",
        f"{summary['slice_count']} 个切片；{summary['candidate_cluster_count']} 个初始候选；证据分门槛 {threshold:.2f}、不同会话至少 {CONFIG['minimum_distinct_sessions']} 个；{summary['cluster_count']} 个簇过线；{summary['clustered_slice_count']} 个切片入簇；{summary['unclustered_slice_count']} 个暂未归簇。", "",
        "证据分是透明规则分，不是校准概率。过线簇是待核查的 skill 抽样候选，不等于已证实可抽象出 skill。共同证据表示至少两个成员包含该项。", "",
        "| 簇 | 证据分 | 成员 | 会话 | 至少两成员共有的任务词 | 共同操作证据 |", "|---|---:|---:|---:|---|---|",
    ]
    for cluster in clusters:
        terms = ", ".join(cluster["shared_features"]["task"][:5]) or "—"
        files = ", ".join(cluster["shared_features"]["operation_file"][:4] or cluster["shared_features"]["operation_type"][:4]) or "—"
        lines.append(f"| [{cluster['cluster_id']}](#{cluster['cluster_id'].lower()}) | {cluster['evidence_score']:.3f} | {cluster['member_count']} | {cluster['session_count']} | {terms} | {files} |")
    for cluster in clusters:
        lines.extend(["", f"## {cluster['cluster_id']}", "", f"证据分 {cluster['evidence_score']:.3f}；最低两两综合相似度 {cluster['minimum_pair_similarity']:.3f}。共同任务词：{', '.join(cluster['shared_features']['task']) or '无'}。共同文件操作：{', '.join(cluster['shared_features']['operation_file']) or '无'}。共同操作+文件类型：{', '.join(cluster['shared_features']['operation_type']) or '无'}。", "", "成员：", ""])
        lines.extend(f"- `{slice_id}`" for slice_id in cluster["members"])
        lines.extend(["", "两两连接：", ""])
        lines.extend(f"- `{edge['left']}` ↔ `{edge['right']}`，综合 {edge['joint_similarity']:.3f}；任务词 {edge['view_similarities']['task']:.3f}，具体文件操作 {edge['view_similarities']['operation_file']:.3f}。" for edge in cluster["pair_edges"])
    lines.extend(["", "## 暂缓的候选", "", "证据分不足或仅来自同一会话的组合暂缓；同项目不同任务容易产生虚高分。", "", "| 候选 | 证据分 | 会话 | 暂缓原因 | 成员 | 共同任务词 |", "|---|---:|---:|---|---|---|"])
    for candidate in deferred:
        terms = ", ".join(candidate["shared_features"]["task"][:5]) or "—"
        members = ", ".join(f"`{slice_id}`" for slice_id in candidate["members"])
        lines.append(f"| {candidate['candidate_id']} | {candidate['evidence_score']:.3f} | {candidate['session_count']} | {', '.join(candidate['defer_reasons'])} | {members} | {terms} |")
    lines.extend(["", "## 暂未归簇", ""])
    lines.extend(f"- `{slice_id}`" for slice_id in unclustered)
    (output / "clusters.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# 聚类 v0.2\n\n"
        "完全本地、确定性。先用共享任务词倒排表生成候选切片对，再对任务词、动作邻近词、操作+文件名、操作+文件类型分别计算余弦相似度。"
        "固定权重和阈值见 config.json。只有任务词与至少一个操作视角同时达标才连边；同会话要求更高的任务词相似度，跨会话要求更强的具体操作证据。"
        "每个最大完全子图形成一个初始候选，避免仅靠 A-B-C 链条把不相似的 A 与 C 合并。"
        "候选证据分取簇内最弱一对，结合任务词、具体操作和综合相似度；跨会话有少量奖励。"
        "只把证据分达到 config.json 门槛、且至少由两个不同会话支持的候选写入 clusters.json 和 assignments.json；其余保留在 deferred-candidates.json，并记录暂缓原因。"
        "一个切片可属于多个簇；未入正式簇的切片列入 unclustered.json。"
        "证据分未经人工标注校准，不是准确率；跨会话也可能是同一项目，过线簇仍需检查是否含有多任务切片。相同会话的连续切片，即使分数高，也只能当作候选。\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-signals", required=True, type=Path)
    parser.add_argument("--tool-signals", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary = run(args.event_signals, args.tool_signals, args.output)
    print(json.dumps({key: summary[key] for key in ("slice_count", "cluster_count", "cross_session_cluster_count", "clustered_slice_count", "unclustered_slice_count", "multiple_membership_slice_count")}))


if __name__ == "__main__":
    main()
