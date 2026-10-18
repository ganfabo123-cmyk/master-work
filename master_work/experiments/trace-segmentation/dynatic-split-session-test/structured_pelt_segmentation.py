#!/usr/bin/env python3
"""Unsupervised structured-cost PELT baseline for Agent trajectories.

This version keeps the event representation fixed and improves the segment
cost with both category likelihood and event-family transition likelihood.
It also rewards safe boundaries near a new user goal or assistant closure.
The search is exact dynamic programming for the penalized PELT objective;
pruning is intentionally disabled until the custom cost is proven compatible
with PELT's pruning condition.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import frozen_message_segmentation as frozen


FAMILIES = ("user", "assistant", "tool_call", "tool_result", "other")
FAMILY_INDEX = {name: index for index, name in enumerate(FAMILIES)}


def event_weight(event: dict) -> float:
    category = event.get("category", "")
    if category == "tool_result" or category.startswith("record:"):
        return 0.0
    if category == "assistant_thinking":
        return 0.25
    return 1.0


def family(category: str) -> str:
    if category == "user_text":
        return "user"
    if category == "assistant_text" or category in {"assistant_thinking", "assistant_reasoning"}:
        return "assistant"
    if category.startswith("tool_call:"):
        return "tool_call"
    if category == "tool_result":
        return "tool_result"
    return "other"


def safe_boundary(events: list[dict], position: int) -> bool:
    if position <= 0 or position >= len(events):
        return False
    return events[position - 1].get("category") == "assistant_text" or events[position].get("category") == "user_text"


def closure_signal(events: list[dict], position: int, radius: int = 20) -> float:
    left = events[max(0, position - radius):position]
    return 1.0 if any(
        event.get("category") == "assistant_text"
        and frozen.CLOSURE_RE.search(event.get("text", "") or "")
        for event in left
    ) else 0.0


def goal_signal(events: list[dict], position: int, radius: int = 40) -> float:
    right = events[position:min(len(events), position + radius)]
    if any(event.get("category") == "user_text" for event in right):
        return 1.0
    return 0.0


def build_prefix(events: list[dict], vocabulary: list[str]) -> tuple[list[list[float]], list[list[float]], list[float]]:
    category_index = {category: index for index, category in enumerate(vocabulary)}
    category_prefix = [[0.0] * len(vocabulary)]
    transition_prefix = [[0.0] * (len(FAMILIES) * len(FAMILIES))]
    total_prefix = [0.0]
    previous_family = None
    previous_weight = 0.0
    for event in events:
        category_row = category_prefix[-1].copy()
        transition_row = transition_prefix[-1].copy()
        weight = event_weight(event)
        if weight > 0:
            category_row[category_index[event["category"]]] += weight
        current_family = family(event.get("category", ""))
        if previous_family is not None and weight > 0 and previous_weight > 0:
            transition_row[FAMILY_INDEX[previous_family] * len(FAMILIES) + FAMILY_INDEX[current_family]] += min(weight, previous_weight)
        category_prefix.append(category_row)
        transition_prefix.append(transition_row)
        total_prefix.append(total_prefix[-1] + weight)
        previous_family = current_family
        previous_weight = weight
    return category_prefix, transition_prefix, total_prefix


def nll_from_counts(counts: list[float], total: float, alpha: float) -> float:
    if total <= 0:
        return 0.0
    dimension = len(counts)
    result = 0.0
    for count in counts:
        probability = (count + alpha) / (total + dimension * alpha)
        if count > 0:
            result -= count * math.log(probability)
    return result


def segment_cost(
    category_prefix: list[list[float]],
    transition_prefix: list[list[float]],
    total_prefix: list[float],
    start: int,
    end: int,
    alpha: float,
) -> float:
    category_counts = [right - left for left, right in zip(category_prefix[start], category_prefix[end])]
    transition_counts = [right - left for left, right in zip(transition_prefix[start], transition_prefix[end])]
    total = total_prefix[end] - total_prefix[start]
    transition_total = sum(transition_counts)
    category_cost = nll_from_counts(category_counts, total, alpha)
    transition_cost = nll_from_counts(transition_counts, transition_total, alpha)
    return 0.65 * category_cost + 0.35 * transition_cost


def optimize_session(
    events: list[dict],
    vocabulary: list[str],
    penalty: float,
    min_segment: int,
    alpha: float,
    boundary_reward: float,
) -> tuple[list[int], dict]:
    n = len(events)
    category_prefix, transition_prefix, total_prefix = build_prefix(events, vocabulary)
    endpoints = [0] + [p for p in range(1, n) if safe_boundary(events, p)] + [n]
    endpoints = sorted(set(endpoints))
    objective = {0: -penalty}
    previous = {}
    trace = []
    for end in endpoints[1:]:
        candidates = [start for start in endpoints[:-1] if start in objective and end - start >= min_segment]
        if not candidates:
            continue
        values = []
        for start in candidates:
            cost = segment_cost(category_prefix, transition_prefix, total_prefix, start, end, alpha)
            reward = 0.0 if end == n else boundary_reward * (goal_signal(events, end) + closure_signal(events, end))
            values.append((objective[start] + cost + penalty - reward, start))
        best_value, best_start = min(values)
        objective[end] = best_value
        previous[end] = best_start
        trace.append({"end": end, "candidate_count": len(candidates), "best_start": best_start, "objective": best_value})
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
    return boundaries, {"objective": objective[n], "trace": trace, "endpoint_count": len(endpoints)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--penalty", type=float, default=1.0)
    parser.add_argument("--min-segment", type=int, default=30)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--boundary-reward", type=float, default=1.0)
    parser.add_argument("--overlap-events", type=int, default=25)
    args = parser.parse_args()
    if args.penalty <= 0 or args.min_segment < 1 or args.alpha <= 0 or args.boundary_reward < 0 or args.overlap_events < 0:
        parser.error("invalid structured PELT parameters")

    source = frozen.load_json(args.input.resolve())
    mapping = source["mapping"]
    vocabulary = list(mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        events = session.get("events", [])
        boundaries, meta = optimize_session(events, vocabulary, args.penalty, args.min_segment, args.alpha, args.boundary_reward)
        ranges = list(zip([0, *boundaries], [*boundaries, len(events)]))
        segments = []
        for index, (core_start, core_end) in enumerate(ranges, start=1):
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
        frozen.plot_session(session, mapping, [{"boundary_after_event": p} for p in boundaries], [], args.output_dir / filename)
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session.get("session_id"),
            "event_count": len(events),
            "candidate_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "pelt_meta": meta,
            "segments": segments,
            "plot_file": filename,
        })
    output = {
        "formula": {
            "version": "structured-pelt-fixed-representation-v1",
            "penalty": args.penalty,
            "min_segment": args.min_segment,
            "alpha": args.alpha,
            "boundary_reward": args.boundary_reward,
            "overlap_events": args.overlap_events,
            "segment_cost": "0.65*category_nll + 0.35*event_family_transition_nll",
            "objective": "sum(segment_cost) + penalty*segments - boundary_reward*(goal_signal+closure_signal)",
            "representation": "fixed categorical event mapping; no labels and no learned A in this stage",
            "pruning": "disabled; exact dynamic programming baseline",
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
