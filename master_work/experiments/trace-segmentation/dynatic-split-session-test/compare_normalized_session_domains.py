#!/usr/bin/env python3
"""Compare normalized complete-session domains with slice domains by session sets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def domain_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    return payload.get("domains", [])


def to_session_id(member: str) -> str:
    value = str(member).removeprefix("segments__")
    if value.endswith("__segment-01"):
        return value.removesuffix("__segment-01")
    if "__segment-" in value:
        return value.rsplit("__segment-", 1)[0]
    return value


def members(domain: dict[str, Any]) -> set[str]:
    values = domain.get("member_slice_ids", domain.get("members", []))
    return {to_session_id(value) for value in values}


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def compare(left_path: Path, right_path: Path) -> dict[str, Any]:
    left = domain_list(read(left_path))
    right = domain_list(read(right_path))
    rows = []
    for source in left:
        source_members = members(source)
        candidates = []
        for target in right:
            target_members = members(target)
            intersection = source_members & target_members
            candidates.append({
                "source_domain_id": source.get("domain_id"),
                "source_name": source.get("name", source.get("domain_id")),
                "target_domain_id": target.get("domain_id"),
                "target_name": target.get("name", target.get("domain_id")),
                "source_session_count": len(source_members),
                "target_session_count": len(target_members),
                "intersection_count": len(intersection),
                "source_to_target_coverage": round(len(intersection) / len(source_members), 6) if source_members else 0.0,
                "target_to_source_coverage": round(len(intersection) / len(target_members), 6) if target_members else 0.0,
                "jaccard": round(jaccard(source_members, target_members), 6),
            })
        rows.append(max(candidates, key=lambda row: (row["jaccard"], row["intersection_count"])))
    return {"source_domain_count": len(left), "target_domain_count": len(right), "best_matches": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-session-domains", type=Path, required=True)
    parser.add_argument("--slice-fine-domains", type=Path, required=True)
    parser.add_argument("--slice-broad-domains", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = {
        "normalized_session_to_slice_fine": compare(args.normalized_session_domains, args.slice_fine_domains),
        "normalized_session_to_slice_broad": compare(args.normalized_session_domains, args.slice_broad_domains),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "normalized-session-consistency.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# LLM 归一化后的原始 session 与切片领域一致性", ""]
    for mode, data in result.items():
        lines.extend(["## " + mode, "", "| 原始归一化领域 | 最佳切片领域 | 原始 session 数 | 切片 session 数 | 交集 | 原始→切片 | 切片→原始 | Jaccard |", "|---|---|---:|---:|---:|---:|---:|---:|"])
        for row in data["best_matches"]:
            lines.append(f"| {row['source_domain_id']} {row['source_name']} | {row['target_domain_id']} {row['target_name']} | {row['source_session_count']} | {row['target_session_count']} | {row['intersection_count']} | {row['source_to_target_coverage']:.3f} | {row['target_to_source_coverage']:.3f} | {row['jaccard']:.3f} |")
        lines.append("")
    (args.output / "normalized-session-consistency.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: value["best_matches"] for key, value in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
