"""Merge discovered domain clusters using data-derived cross-domain IDF."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    common = set(left) & set(right)
    dot = sum(left[t] * right[t] for t in common)
    nl = math.sqrt(sum(v * v for v in left.values()))
    nr = math.sqrt(sum(v * v for v in right.values()))
    return dot / (nl * nr) if nl and nr else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--merge-threshold", type=float, default=0.55)
    args = parser.parse_args()
    cards = json.loads(args.cards.read_text(encoding="utf-8"))
    domain_count = len(cards)
    domain_df = Counter()
    raw_vectors = []
    for card in cards:
        frequencies = {str(k): float(v) for k, v in card.get("term_frequency_profile", {}).items()}
        raw_vectors.append(frequencies)
        domain_df.update(frequencies.keys())
    vectors = []
    for frequencies in raw_vectors:
        vectors.append({
            term: value * math.log((domain_count + 1) / (domain_df[term] + 1))
            for term, value in frequencies.items()
            if domain_df[term] <= max(2, domain_count // 2)
        })

    parent = list(range(domain_count))
    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    similarities = []
    for left in range(domain_count):
        for right in range(left + 1, domain_count):
            score = cosine(vectors[left], vectors[right])
            similarities.append({"left": cards[left]["domain_id"], "right": cards[right]["domain_id"], "cosine": round(score, 6)})
            if score >= args.merge_threshold:
                union(left, right)
    merged = defaultdict(list)
    for index in range(domain_count):
        merged[find(index)].append(index)
    refined = []
    for number, indexes in enumerate(merged.values(), 1):
        terms = Counter()
        members = []
        sources = []
        coverage = []
        sessions = set()
        for index in indexes:
            card = cards[index]
            sources.append(card["domain_id"])
            core = set(card.get("core_terms", []))
            terms.update({term: int(value) for term, value in card.get("term_frequency_profile", {}).items() if term in core})
            members.extend(card.get("member_slice_ids", []))
            sessions.update(card.get("session_count", []) if isinstance(card.get("session_count"), list) else [])
            coverage.append(float(card.get("average_information_coverage", 0.0)))
        refined.append({
            "domain_id": f"R{number:03d}",
            "source_domain_ids": sources,
            "support": len(set(members)),
            "core_terms": [term for term, _ in terms.most_common(40)],
            "term_frequency_profile": dict(terms.most_common()),
            "average_information_coverage": round(sum(coverage) / len(coverage), 6),
            "member_slice_ids": sorted(set(members)),
        })
    refined.sort(key=lambda item: (-item["support"], item["domain_id"]))
    for index, domain in enumerate(refined, 1):
        domain["domain_id"] = f"R{index:03d}"
    summary = {
        "algorithm_version": "domain-cluster-refinement-v1",
        "input_domain_count": domain_count,
        "refined_domain_count": len(refined),
        "merge_threshold": args.merge_threshold,
        "cross_domain_idf": True,
        "similarities": similarities,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "domains.json").write_text(json.dumps(refined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "similarities"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
