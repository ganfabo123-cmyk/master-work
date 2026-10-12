#!/usr/bin/env python3
"""Discover domain-free behavior candidate clusters from observable slices.

The candidate stage deliberately keeps the observed event sequence and generic
structural statistics only.  It does not use a tool-to-action dictionary,
derived operation taxonomy, fixed n-grams, domain vocabulary, or behavior
names.  Candidate cards additionally expose domain-free observable context
such as sequence shape, tool counts, targets, and file types.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


def read_profiles(path: Path) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            by_id[str(row["slice_id"])] = row
    return [by_id[key] for key in sorted(by_id)]


def primitive_counts(profile: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for label in profile.get("sequence", []):
        counts[f"event:{label}"] += 1
    counts["structure:event_count"] = min(int(profile.get("event_count", 0)) // 50, 20)
    counts["structure:user_event_count"] = min(int(profile.get("user_events", 0)) // 5, 20)
    counts["structure:assistant_event_count"] = min(int(profile.get("assistant_events", 0)) // 10, 20)
    return counts


def weighted_vectors(profiles: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    raw = {profile["slice_id"]: primitive_counts(profile) for profile in profiles}
    document_frequency = Counter()
    for counts in raw.values():
        document_frequency.update(counts)
    total = len(profiles)
    vectors: dict[str, dict[str, float]] = {}
    for slice_id, counts in raw.items():
        vectors[slice_id] = {
            key: (1.0 + math.log(value)) * (math.log((total + 1) / (document_frequency[key] + 1)) + 1.0)
            for key, value in counts.items()
            if value > 0
        }
    return vectors


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    numerator = sum(left.get(key, 0.0) * right.get(key, 0.0) for key in keys)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def size_penalty(member_count: int, alpha: float) -> float:
    if alpha <= 0.0 or member_count <= 1:
        return 1.0
    return 1.0 / (1.0 + alpha * math.log2(member_count))


def cluster(
    profiles: list[dict[str, Any]],
    vectors: dict[str, dict[str, float]],
    threshold: float,
    size_penalty_alpha: float,
) -> list[list[int]]:
    clusters: list[list[int]] = [[index] for index in range(len(profiles))]
    cache: dict[tuple[int, int], float] = {}

    def similarity(left: int, right: int) -> float:
        key = (left, right) if left < right else (right, left)
        if key not in cache:
            cache[key] = cosine(vectors[profiles[left]["slice_id"]], vectors[profiles[right]["slice_id"]])
        return cache[key]

    while True:
        best: tuple[float, int, int] | None = None
        for left_index in range(len(clusters)):
            for right_index in range(left_index + 1, len(clusters)):
                raw_score = min(
                    similarity(left, right)
                    for left in clusters[left_index]
                    for right in clusters[right_index]
                )
                score = raw_score * size_penalty(
                    len(clusters[left_index]) + len(clusters[right_index]),
                    size_penalty_alpha,
                )
                if score >= threshold and (best is None or score > best[0]):
                    best = (score, left_index, right_index)
        if best is None:
            return [sorted(value) for value in clusters]
        _, left_index, right_index = best
        clusters[left_index].extend(clusters[right_index])
        del clusters[right_index]


def session_id(slice_id: str) -> str:
    parts = slice_id.split("__")
    return "__".join(parts[:-1]) if parts[-1].startswith("segment-") else slice_id


def read_signal_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    result: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[str(row["slice_id"])] = row
    return result


def card(cluster_id: str, indices: list[int], profiles: list[dict[str, Any]], signals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    members = [profiles[index] for index in indices]
    file_counts = Counter()
    sequences = Counter()
    tool_counts = Counter()
    target_counts = Counter()
    transition_counts = Counter()
    for profile in members:
        file_counts.update(profile.get("file_types", {}))
        sequence = profile.get("sequence", [])
        sequences[" > ".join(sequence[:20])] += 1
        tool_counts.update(label.split(":", 1)[1] for label in sequence if label.startswith("tool_call:"))
        transition_counts.update(zip(sequence, sequence[1:]))
        for item in signals.get(profile["slice_id"], {}).get("operation_target_events", []):
            target = item.get("target")
            if target:
                target_counts[str(target)] += int(item.get("event_count", 1))
    top_transitions = [f"{left} -> {right}" for (left, right), _ in transition_counts.most_common(6)]
    return {
        "candidate_cluster_id": cluster_id,
        "support": len(members),
        "session_count": len({session_id(profile["slice_id"]) for profile in members}),
        "observed_tool_counts": dict(tool_counts.most_common(12)),
        "representative_sequences": [sequence for sequence, _ in sequences.most_common(3)],
        "common_transitions": top_transitions,
        "target_examples": [name for name, _ in target_counts.most_common(8)],
        "file_types": [name for name, _ in file_counts.most_common(8)],
        "member_slice_ids": sorted(profile["slice_id"] for profile in members),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signals", type=Path)
    parser.add_argument("--similarity-threshold", type=float, default=0.55)
    parser.add_argument("--size-penalty-alpha", type=float, default=0.02)
    args = parser.parse_args()

    profiles = read_profiles(args.profiles)
    signals = read_signal_index(args.signals)
    vectors = weighted_vectors(profiles)
    groups = cluster(profiles, vectors, args.similarity_threshold, args.size_penalty_alpha)
    groups.sort(key=lambda group: (-len(group), group[0]))
    cards = [card(f"C{index:03d}", group, profiles, signals) for index, group in enumerate(groups, 1)]
    args.output.mkdir(parents=True, exist_ok=True)
    result = {
        "algorithm_version": "domain-free-behavior-candidates-v4-size-penalty",
        "input_profile_file": str(args.profiles),
        "input_slice_count": len(profiles),
        "candidate_cluster_count": len(cards),
        "similarity": "IDF-weighted cosine over exact observed event labels and structural counts, multiplied by a merge-size penalty; enriched card evidence is descriptive only",
        "similarity_threshold": args.similarity_threshold,
        "size_penalty_alpha": args.size_penalty_alpha,
        "size_penalty_formula": "1 / (1 + alpha * log2(merged_member_count))",
        "semantic_priors": [],
        "clustering_inputs": [
        "exact observed event labels",
            "generic event-count bins",
            "generic user-event-count bins",
            "generic assistant-event-count bins",
        ],
        "cards": cards,
    }
    (args.output / "behavior-candidate-cards.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "README.md").write_text(
        "# Domain-free behavior candidate cards\n\n"
        "候选阶段只使用原始事件/工具序列和通用结构统计，不使用派生操作语义，不定义行为名称；行为语义由后续 LLM 归一化。\n",
        encoding="utf-8",
    )
    print(json.dumps({"input_slice_count": len(profiles), "candidate_cluster_count": len(cards), "output": str(args.output), "signals_loaded": bool(signals)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
