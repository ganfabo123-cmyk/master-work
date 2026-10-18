"""Build cheap, LLM-facing feature cards for discovered domain clusters."""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    base = Path("master_work/experiments/trace-segmentation/dynatic-split-session-test")
    domain_path = base / "unsupervised-domain-complete-v6/domains.json"
    segment_dir = base / "token-frequency-banded-v3-exclusive-no-symbols/segments"
    opening_rows = read(base / "slice-opening-analysis/slice-opening-analysis.json")
    openings = {
        row["slice_file"].split("\\")[-1].removesuffix(".json"): row
        for row in opening_rows
    }
    domains = read(domain_path)
    output = base / "domain-feature-cards-v1"
    output.mkdir(parents=True, exist_ok=True)
    cards = []
    for domain in domains:
        member_ids = [member.removeprefix("segments__") for member in domain["members"]]
        term_counts = Counter()
        term_support = Counter()
        for slice_id in member_ids:
            path = segment_dir / f"{slice_id}.json"
            if not path.exists():
                continue
            counts = read(path).get("token_frequencies", {})
            term_counts.update({str(k): int(v) for k, v in counts.items()})
            term_support.update(str(k) for k, v in counts.items() if int(v) > 0)
        top_terms = [term for term, _count in term_counts.most_common(100)]
        ranked_members = []
        core_terms = set(domain["terms"])
        for slice_id in member_ids:
            path = segment_dir / f"{slice_id}.json"
            counts = read(path).get("token_frequencies", {}) if path.exists() else {}
            evidence = {term: int(counts.get(term, 0)) for term in core_terms if int(counts.get(term, 0)) > 0}
            ranked_members.append((sum(evidence.values()), slice_id, evidence))
        representatives = []
        for _score, slice_id, evidence in sorted(ranked_members, reverse=True)[:10]:
            opening = openings.get(slice_id)
            if opening and opening.get("first_sentence"):
                representatives.append({
                    "slice_id": slice_id,
                    "first_sentence": opening["first_sentence"][:300],
                    "matched_core_terms": sorted(evidence, key=evidence.get, reverse=True),
                })
        sessions = {slice_id.rsplit("__segment-", 1)[0] for slice_id in member_ids}
        cards.append({
            "domain_id": domain["domain_id"],
            "support": domain["support"],
            "session_count": len(sessions),
            "average_information_coverage": domain["average_information_coverage"],
            "core_terms": domain["terms"],
            "top_terms_by_frequency": top_terms,
            "term_support_count": dict(term_support.most_common(200)),
            "term_frequency_profile": dict(term_counts.most_common()),
            "representative_first_user_inputs": representatives,
            "member_slice_ids": member_ids,
            "llm_hint": "; ".join(domain["terms"][:12]),
        })
    summary = {
        "algorithm_version": "domain-feature-cards-v1",
        "domain_count": len(cards),
        "purpose": "cheap cluster summaries before LLM expansion",
        "fields": ["core_terms", "top_terms_by_frequency", "support", "session_count", "representative_first_user_inputs", "member_slice_ids"],
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "domain-feature-cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Domain feature cards", "", "每个簇先用这些低成本特征交给 LLM 判断，只有需要时再展开完整切片。", ""]
    for card in cards:
        lines.extend([
            f"## {card['domain_id']}",
            f"- 轨迹数：{card['support']}；session 数：{card['session_count']}；信息完整度：{card['average_information_coverage']:.4f}",
            f"- 核心词：{', '.join(card['core_terms'][:20])}",
            f"- 高频词（前 60）：{', '.join(card['top_terms_by_frequency'][:60])}",
            "- 代表首句：",
        ])
        for item in card["representative_first_user_inputs"][:10]:
            lines.append(f"  - {item['first_sentence']}")
        lines.append("")
    (output / "domain-feature-cards.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
