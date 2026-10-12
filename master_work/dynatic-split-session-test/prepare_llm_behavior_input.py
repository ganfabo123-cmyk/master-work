"""Prepare compact candidate cards for the behavior-normalization LLM call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


KEEP_FIELDS = (
    "candidate_cluster_id",
    "support",
    "session_count",
    "observed_tool_counts",
    "representative_sequences",
    "common_transitions",
    "target_examples",
    "file_types",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--token-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.candidates.read_text(encoding="utf-8"))
    token_evidence = {}
    if args.token_evidence:
        token_source = json.loads(args.token_evidence.read_text(encoding="utf-8"))
        token_evidence = {
            item["candidate_cluster_id"]: [
                token["token"] for token in item.get("top_tokens", [])
            ]
            for item in token_source.get("clusters", [])
        }
    cards: list[dict[str, Any]] = []
    for card in source.get("cards", []):
        compact = {field: card.get(field, []) for field in KEEP_FIELDS}
        compact["top_tokens"] = token_evidence.get(card["candidate_cluster_id"], [])
        cards.append(compact)

    result = {
        "input_type": "compact_behavior_candidate_cards",
        "source_algorithm_version": source.get("algorithm_version"),
        "candidate_cluster_count": len(cards),
        "evidence_policy": "Only compact observed sequence, weighted corpus-filtered top tokens, transition, target, and file-type context; no derived behavior taxonomy",
        "cards": cards,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "behavior-normalization-input.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "README.md").write_text(
        "# 行为归一化 LLM 输入\n\n"
        "该文件只保留候选簇的短语义证据和统计摘要，不包含 slice 成员 ID；"
        "LLM 输出应按照 `llm-behavior-normalization-prompt-v1.md` 的 JSON 格式保存，"
        "再交给 `apply_llm_behavior_normalization.py` 回填成员。\n",
        encoding="utf-8",
    )
    print(json.dumps({"candidate_cluster_count": len(cards), "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
