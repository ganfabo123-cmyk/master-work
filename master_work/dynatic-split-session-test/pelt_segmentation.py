#!/usr/bin/env python3
"""Unsupervised PELT segmentation for full message trajectories.

The segment cost is weighted multinomial entropy: a good segment has a stable
message/tool-category distribution. PELT minimizes the sum of segment costs
plus a fixed penalty for every additional segment. No manual boundary labels
are used.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import frozen_message_segmentation as frozen


def category_weight(category: str) -> float:
    if category == "tool_result" or category.startswith("record:"):
        return 0.0
    if category == "assistant_thinking":
        return 0.25
    return 1.0


def safe_boundary(events: list[dict], position: int) -> bool:
    if position <= 0 or position >= len(events):
        return False
    return events[position - 1].get("category") == "assistant_text" or events[position].get("category") == "user_text"


def build_prefix(events: list[dict], vocabulary: list[str]) -> tuple[list[list[float]], list[float]]:
    index = {category: i for i, category in enumerate(vocabulary)}
    counts = [[0.0] * len(vocabulary)]
    totals = [0.0]
    for event in events:
        row = counts[-1].copy()
        weight = category_weight(event.get("category", ""))
        if weight > 0:
            row[index[event["category"]]] += weight
        counts.append(row)
        totals.append(totals[-1] + weight)
    return counts, totals


def segment_cost(
    prefix: list[list[float]],
    totals: list[float],
    start: int,
    end: int,
    alpha: float,
) -> float:
    total = totals[end] - totals[start]
    if total <= 0:
        return 0.0
    dimension = len(prefix[0])
    entropy = 0.0
    for left, right in zip(prefix[start], prefix[end]):
        count = right - left
        probability = (count + alpha) / (total + dimension * alpha)
        if count > 0:
            entropy -= count * math.log(probability)
    return entropy


def pelt(
    events: list[dict],
    vocabulary: list[str],
    penalty: float,
    min_segment: int,
    alpha: float,
) -> tuple[list[int], dict]:
    n = len(events)
    prefix, totals = build_prefix(events, vocabulary)
    endpoints = [0] + [p for p in range(1, n) if safe_boundary(events, p)] + [n]
    endpoints = sorted(set(endpoints))
    cost = {0: -penalty}
    previous: dict[int, int] = {}
    # Keep every previously reachable safe endpoint. This is the exact
    # penalized-partitioning baseline for the PELT objective. The custom
    # weighted entropy cost is not yet proven to satisfy PELT's pruning
    # inequality, so applying pruning here would risk deleting valid paths.
    candidates = [0]
    trace = []
    for end in endpoints[1:]:
        eligible = [start for start in candidates if end - start >= min_segment]
        if not eligible:
            continue
        values = [
            (cost[start] + segment_cost(prefix, totals, start, end, alpha) + penalty, start)
            for start in eligible
        ]
        best_value, best_start = min(values)
        cost[end] = best_value
        previous[end] = best_start
        trace.append({
            "end": end,
            "candidate_count": len(eligible),
            "best_start": best_start,
            "objective": best_value,
        })
        candidates.append(end)
    if n not in previous:
        return [], {"objective": None, "trace": trace, "endpoint_count": len(endpoints)}
    boundaries = []
    cursor = n
    while cursor != 0:
        start = previous[cursor]
        if start != 0:
            boundaries.append(start)
        cursor = start
    boundaries.sort()
    return boundaries, {"objective": cost[n], "trace": trace, "endpoint_count": len(endpoints)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--penalty", type=float, default=100.0)
    parser.add_argument("--min-segment", type=int, default=30)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--overlap-events", type=int, default=25)
    args = parser.parse_args()
    if args.penalty <= 0 or args.min_segment < 1 or args.alpha <= 0 or args.overlap_events < 0:
        parser.error("penalty, min-segment, and alpha must be positive; overlap-events must be non-negative")

    source = frozen.load_json(args.input.resolve())
    mapping = source["mapping"]
    vocabulary = list(mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        events = session.get("events", [])
        boundaries, pelt_meta = pelt(events, vocabulary, args.penalty, args.min_segment, args.alpha)
        core_ranges = list(zip([0, *boundaries], [*boundaries, len(events)]))
        segments = []
        for index, (core_start, core_end) in enumerate(core_ranges, start=1):
            start = max(0, core_start - args.overlap_events)
            end = min(len(events), core_end + args.overlap_events)
            part = events[start:end]
            counts = Counter(event["category"] for event in part)
            segments.append({
                "segment_index": index,
                "start_event": start + 1,
                "end_event": end,
                "core_start_event": core_start + 1,
                "core_end_event": core_end,
                "overlap_before": core_start - start,
                "overlap_after": end - core_end,
                "length": len(part),
                "first_category": part[0]["category"] if part else None,
                "last_category": part[-1]["category"] if part else None,
                "dominant_category": counts.most_common(1)[0][0] if counts else None,
                "category_counts": dict(counts.most_common()),
                "events": part,
            })
        filename = f"{session.get('harness', 'unknown')}__{session.get('session_id', 'unknown')}.png"
        selected = [{"boundary_after_event": position} for position in boundaries]
        frozen.plot_session(session, mapping, selected, [], args.output_dir / filename)
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session.get("session_id"),
            "event_count": len(events),
            "candidate_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "pelt_meta": pelt_meta,
            "segments": segments,
            "plot_file": filename,
        })

    output = {
        "formula": {
            "version": "pelt-weighted-multinomial-entropy-v1",
            "penalty": args.penalty,
            "min_segment": args.min_segment,
            "alpha": args.alpha,
            "overlap_events": args.overlap_events,
            "segment_cost": "weighted multinomial negative log-likelihood / entropy",
            "objective": "sum(segment_cost) + penalty * number_of_segments",
            "search": "exact dynamic programming for the PELT penalized objective; pruning disabled until the custom cost satisfies the pruning condition",
            "constraints": "all changepoints are adjacent to assistant_text or user_text; tool_result and record:* have zero cost weight; assistant_thinking has weight 0.25",
            "labels_used": False,
        },
        "mapping": mapping,
        "session_count": len(sessions),
        "total_event_count": sum(item["event_count"] for item in sessions),
        "total_selected_boundaries": sum(item["candidate_boundary_count"] for item in sessions),
        "total_segments": sum(len(item["segments"]) for item in sessions),
        "sessions": sessions,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"formula_version={output['formula']['version']}")
    print(f"sessions={output['session_count']}")
    print(f"events={output['total_event_count']}")
    print(f"selected_boundaries={output['total_selected_boundaries']}")
    print(f"segments={output['total_segments']}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
