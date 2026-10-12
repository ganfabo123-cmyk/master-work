"""Compress slice profiles into a small set of cheap behavior prototypes."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


BASE = Path("master_work/dynatic-split-session-test")
GRAPH_DIR = BASE / "trajectory-behavior-graphs-v1"


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def features(profile: dict) -> set[str]:
    result = {f"seq:{x}" for x in profile.get("sequence", [])}
    result.update(f"op:{x}" for x in profile.get("operations", {}))
    result.update(f"file:{x}" for x in profile.get("file_types", {}))
    # Coarse structural bins make long and short traces comparable.
    result.add(f"events:{min(profile.get('event_count', 0) // 50, 10)}")
    result.add(f"tools:{min(profile.get('tool_events', 0) // 10, 10)}")
    return result


def aggregate(profiles: list[dict]) -> dict:
    op = Counter(); files = Counter(); nodes = Counter();
    for profile in profiles:
        op.update(profile.get("operations", {})); files.update(profile.get("file_types", {})); nodes.update(profile.get("sequence", []))
    return {
        "slice_count": len(profiles),
        "member_slice_ids": sorted(p["slice_id"] for p in profiles),
        "representative_slice_id": max(profiles, key=lambda p: (p.get("event_count", 0), p.get("tool_events", 0)))["slice_id"],
        "common_sequence_nodes": nodes.most_common(12),
        "operation_counts": op.most_common(12),
        "file_type_counts": files.most_common(12),
        "event_count_range": [min(p.get("event_count", 0) for p in profiles), max(p.get("event_count", 0) for p in profiles)],
    }


def main() -> None:
    threshold = 0.42
    max_prototypes = 8
    output = BASE / "behavior-prototypes-v1"
    output.mkdir(parents=True, exist_ok=True)
    results = []
    total = 0
    for graph_path in sorted(GRAPH_DIR.glob("D*.json")):
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        profiles = graph.get("representative_profiles", [])
        # The full profiles are stored separately to keep graph JSON compact.
        by_id = {}
        profile_path = GRAPH_DIR / "slice-profiles.jsonl"
        for line in profile_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            by_id[row["slice_id"]] = row
        member_ids = set()
        domain_path = BASE / "unsupervised-domain-complete-v6/domains.json"
        domains = json.loads(domain_path.read_text(encoding="utf-8"))
        domain = next(d for d in domains if d["domain_id"] == graph["domain_id"])
        member_ids = {sid.removeprefix("segments__") for sid in domain.get("members", [])}
        profiles = [by_id[sid] for sid in member_ids if sid in by_id]
        profiles.sort(key=lambda p: p.get("event_count", 0), reverse=True)
        proto_groups: list[list[dict]] = []
        proto_features: list[set[str]] = []
        for profile in profiles:
            fs = features(profile)
            best = max(((jaccard(fs, other), i) for i, other in enumerate(proto_features)), default=(0.0, -1))
            if best[0] >= threshold:
                proto_groups[best[1]].append(profile)
                # Keep a union so later members can match the prototype family.
                proto_features[best[1]] |= fs
            else:
                proto_groups.append([profile]); proto_features.append(set(fs))
        # Keep the largest prototypes. Small groups are assigned to the closest retained prototype.
        proto_groups.sort(key=len, reverse=True)
        if len(proto_groups) > max_prototypes:
            retained = proto_groups[:max_prototypes]
            for group in proto_groups[max_prototypes:]:
                target = max(range(len(retained)), key=lambda i: jaccard(features(group[0]), features(retained[i][0])))
                retained[target].extend(group)
            proto_groups = retained
        prototypes = [aggregate(group) for group in proto_groups]
        total += len(profiles)
        result = {
            "domain_id": graph["domain_id"],
            "input_slice_count": len(profiles),
            "prototype_count": len(prototypes),
            "compression_ratio": round(len(profiles) / len(prototypes), 3) if prototypes else 0,
            "similarity_threshold": threshold,
            "max_prototypes": max_prototypes,
            "prototypes": prototypes,
        }
        (output / f"{graph['domain_id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append({k: result[k] for k in ("domain_id", "input_slice_count", "prototype_count", "compression_ratio")})
    summary = {"algorithm_version": "behavior-prototypes-v1", "domain_count": len(results), "input_slice_count": total, "domains": results, "similarity": "Jaccard over ordered event labels, operation types, file types, and coarse size bins"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text("# 行为原型压缩\n\n每个领域最多保留 8 个无模型行为原型。原型只聚合可观察事件序列、操作类型、文件类型和轨迹规模，不给行为预设语义名称。\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
