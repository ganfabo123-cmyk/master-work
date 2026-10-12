"""Apply an LLM behavior normalization to candidate cards and backfill slices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidates = load(args.candidates)
    normalization = load(args.normalization)
    cards = {card["candidate_cluster_id"]: card for card in candidates.get("cards", [])}
    known_ids = set(cards)

    behaviors: list[dict[str, Any]] = []
    assigned: dict[str, list[str]] = {}
    invalid_source_clusters: list[str] = []
    for item in normalization.get("behavior_patterns", []):
        source_ids = list(dict.fromkeys(item.get("source_clusters", [])))
        valid_ids = [source_id for source_id in source_ids if source_id in known_ids]
        invalid_source_clusters.extend(source_id for source_id in source_ids if source_id not in known_ids)
        members = sorted({slice_id for source_id in valid_ids for slice_id in cards[source_id].get("member_slice_ids", [])})
        for source_id in valid_ids:
            assigned.setdefault(source_id, []).append(item.get("behavior_id", ""))
        behaviors.append({
            "behavior_id": item.get("behavior_id", ""),
            "name": item.get("name", ""),
            "description": item.get("description", ""),
            "relation": item.get("relation", "keep"),
            "parent_behavior_id": item.get("parent_behavior_id"),
            "source_clusters": valid_ids,
            "member_slice_ids": members,
            "support": len(members),
            "evidence": item.get("evidence", []),
            "uncertainty": item.get("uncertainty", ""),
        })

    mixed_ids = [item.get("cluster_id") for item in normalization.get("mixed_clusters", [])]
    unresolved_ids = [item.get("cluster_id") for item in normalization.get("unresolved_clusters", [])]
    mixed_ids = [cluster_id for cluster_id in mixed_ids if cluster_id in known_ids]
    unresolved_ids = [cluster_id for cluster_id in unresolved_ids if cluster_id in known_ids]
    represented = set(assigned) | set(mixed_ids) | set(unresolved_ids)
    unrepresented = sorted(known_ids - represented)
    overlap = {cluster_id: behavior_ids for cluster_id, behavior_ids in assigned.items() if len(set(behavior_ids)) > 1}

    output = {
        "algorithm_version": "llm-assisted-behavior-normalization-v1",
        "candidate_algorithm_version": candidates.get("algorithm_version"),
        "candidate_cluster_count": len(cards),
        "behavior_count": len(behaviors),
        "behaviors": behaviors,
        "mixed_clusters": [
            item for item in normalization.get("mixed_clusters", []) if item.get("cluster_id") in known_ids
        ],
        "unresolved_clusters": [
            item for item in normalization.get("unresolved_clusters", []) if item.get("cluster_id") in known_ids
        ],
        "merge_relations": normalization.get("merge_relations", []),
        "audit": {
            "invalid_source_clusters": sorted(set(invalid_source_clusters)),
            "overlapping_source_clusters": overlap,
            "unrepresented_source_clusters": unrepresented,
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "behavior-clusters.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "README.md").write_text(
        "# LLM 归一化行为簇\n\n"
        "候选簇由通用可观察特征生成；本目录保存 LLM 给出的行为语义、候选簇关系和程序回填的 slice 成员。\n"
        "`audit` 用于检查候选簇是否不存在、重复归属或未被处理。\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "candidate_cluster_count": len(cards),
        "behavior_count": len(behaviors),
        "mixed_cluster_count": len(mixed_ids),
        "unresolved_cluster_count": len(unresolved_ids),
        "unrepresented_cluster_count": len(unrepresented),
        "overlap_cluster_count": len(overlap),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
