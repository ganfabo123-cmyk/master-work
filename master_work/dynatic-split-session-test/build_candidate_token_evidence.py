#!/usr/bin/env python3
"""Build compact, weighted token evidence for behavior candidate clusters.

This is an extractive, domain-free summary.  It uses event text/argument
tokens, weights them by observed event category, removes corpus-wide noise,
and returns the ten highest-scoring tokens for each candidate cluster.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from token_frequency import tokenize


EVENT_WEIGHTS = {
    "user_text": 4.0,
    "assistant_text": 3.0,
    "assistant_reasoning": 2.0,
    "tool_result": 1.5,
}
TOOL_CALL_WEIGHT = 0.8
MAX_CORPUS_RATE = 0.85

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "could", "do", "does", "for", "from", "had", "has", "have", "if", "in",
    "into", "is", "it", "its", "may", "me", "more", "must", "my", "no", "not",
    "of", "on", "or", "our", "should", "so", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "to", "under", "up", "use",
    "used", "using", "was", "we", "were", "what", "when", "where", "which", "who",
    "will", "with", "would", "you", "your", "true", "false", "null", "json", "text",
    "file", "files", "code", "project", "source", "path", "name", "value", "output",
    "read", "update", "make", "now", "new", "one", "also", "all", "just", "only",
    "之", "的", "了", "和", "是", "在", "有", "我", "你", "他", "它", "这", "那",
}


def normalize_token(token: str) -> str:
    return token.strip().lower()


def useful(token: str) -> bool:
    token = normalize_token(token)
    if not token or token in STOPWORDS or token.isdigit():
        return False
    if re.fullmatch(r"[a-z0-9_]+", token) and len(token) < 3:
        return False
    if re.fullmatch(r"[\W_]+", token, flags=re.UNICODE):
        return False
    return True


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_event_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[str(row["event_id"])] = row
    return rows


def load_slice_events(path: Path) -> dict[str, list[str]]:
    return {row["slice_id"]: row.get("event_ids", []) for row in load_json(path)}


def event_weight(category: str) -> float:
    if category.startswith("tool_call:"):
        return TOOL_CALL_WEIGHT
    return EVENT_WEIGHTS.get(category, 0.0)


def slice_counts(
    slice_event_ids: list[str],
    events: dict[str, dict[str, Any]],
) -> tuple[Counter[str], float]:
    counts: Counter[str] = Counter()
    total_weight = 0.0
    seen: set[str] = set()
    for event_id in slice_event_ids:
        if event_id in seen:
            continue
        seen.add(event_id)
        row = events.get(event_id)
        if not row:
            continue
        weight = event_weight(str(row.get("category", "")))
        if weight <= 0:
            continue
        for raw_token, value in row.get("token_frequencies", {}).items():
            token = normalize_token(str(raw_token))
            if useful(token):
                amount = float(value) * weight
                counts[token] += amount
                total_weight += amount
    return counts, total_weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--slice-events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    candidates = load_json(args.candidates)
    events = load_event_rows(args.events)
    slice_events = load_slice_events(args.slice_events)
    cards = candidates.get("cards", [])

    per_slice: dict[str, Counter[str]] = {}
    per_slice_total: dict[str, float] = {}
    for slice_id, event_ids in slice_events.items():
        counts, total = slice_counts(event_ids, events)
        per_slice[slice_id] = counts
        per_slice_total[slice_id] = total

    document_frequency: Counter[str] = Counter()
    for counts in per_slice.values():
        document_frequency.update(counts.keys())
    corpus_size = len(per_slice)
    allowed = {
        token for token, frequency in document_frequency.items()
        if frequency >= 1 and frequency / max(1, corpus_size) <= MAX_CORPUS_RATE
    }

    results = []
    for card in cards:
        member_ids = list(card.get("member_slice_ids", []))
        aggregate: Counter[str] = Counter()
        member_frequency: Counter[str] = Counter()
        for slice_id in member_ids:
            counts = per_slice.get(slice_id, Counter())
            total = per_slice_total.get(slice_id, 0.0)
            if total <= 0:
                continue
            for token, value in counts.items():
                if token in allowed:
                    aggregate[token] += value / total
                    member_frequency[token] += 1

        scored = []
        for token, normalized_count in aggregate.items():
            slice_df = member_frequency[token]
            idf = math.log((corpus_size + 1) / (document_frequency[token] + 1)) + 1.0
            coverage = slice_df / max(1, len(member_ids))
            score = normalized_count * idf * (0.5 + 0.5 * coverage)
            scored.append({
                "token": token,
                "score": round(score, 6),
                "weighted_normalized_frequency": round(normalized_count, 6),
                "slice_df": slice_df,
                "slice_coverage": round(coverage, 6),
                "corpus_df": document_frequency[token],
                "idf": round(idf, 6),
            })
        scored.sort(key=lambda row: (-row["score"], row["token"]))
        results.append({
            "candidate_cluster_id": card["candidate_cluster_id"],
            "support": card.get("support", len(member_ids)),
            "session_count": card.get("session_count"),
            "top_tokens": scored[: args.top_k],
            "eligible_token_count": len(scored),
        })

    output = {
        "algorithm_version": "weighted-corpus-token-evidence-v1",
        "source_candidate_algorithm_version": candidates.get("algorithm_version"),
        "event_weights": {**EVENT_WEIGHTS, "tool_call:*": TOOL_CALL_WEIGHT},
        "corpus_size": corpus_size,
        "corpus_filter": {
            "max_corpus_rate": MAX_CORPUS_RATE,
            "stopword_filter": "English/Chinese structural stopwords and generic metadata terms",
            "tokenizer": "token_frequency.tokenize(include_symbols=False)",
        },
        "candidate_cluster_count": len(results),
        "top_k": args.top_k,
        "clusters": results,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "candidate-token-evidence.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "README.md").write_text(
        "# 候选簇加权词证据\n\n"
        "每个候选簇由其全部 slice 的可用事件正文和参数值提取 Top-K 词。"
        "词频按事件类别加权，再用全体 slice 的 document frequency 做 IDF；"
        "该结果是可追溯词证据，不是行为名称。\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "candidate_cluster_count": len(results),
        "corpus_size": corpus_size,
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
