#!/usr/bin/env python3
"""Recall-first recursive segmentation over full message trajectories.

The frozen boundary score proposes a split inside the current interval. A
split is accepted only when both children have enough basic task evidence and
the cut is adjacent to a safe text boundary. Otherwise the interval remains
unsplit. Materialized slices optionally receive duplicated context on both
sides, while core ranges remain a complete partition of the source session.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import frozen_message_segmentation as frozen


def has_text(events: list[dict], category: str) -> bool:
    return any(event.get("category") == category for event in events)


def has_tool_call(events: list[dict]) -> bool:
    return any(event.get("category", "").startswith("tool_call:") for event in events)


def has_closure_text(events: list[dict]) -> bool:
    return any(
        event.get("category") == "assistant_text"
        and frozen.CLOSURE_RE.search(event.get("text", "") or "")
        for event in events
    )


def child_completeness(events: list[dict]) -> tuple[float, dict]:
    """A conservative structural proxy, not an LLM semantic judgment."""
    signals = {
        "has_user_text": has_text(events, "user_text"),
        "has_assistant_text": has_text(events, "assistant_text"),
        "has_tool_call": has_tool_call(events),
        "has_closure_text": has_closure_text(events),
    }
    # User intent, assistant context, and execution are required. Closure is
    # useful evidence but is optional because many traces continue naturally.
    score = (
        0.35 * signals["has_user_text"]
        + 0.25 * signals["has_assistant_text"]
        + 0.30 * signals["has_tool_call"]
        + 0.10 * signals["has_closure_text"]
    )
    return score, signals


def local_best_split(
    events: list[dict],
    start: int,
    end: int,
    vocabulary: list[str],
    config: frozen.SegmentationConfig,
) -> tuple[dict | None, list[dict]]:
    largest_window = max(config.windows)
    if end - start < 2 * config.min_segment_events + 2 * largest_window:
        return None, []
    evidence = [
        frozen.boundary_features(events, boundary, vocabulary, config)
        for boundary in range(start + largest_window, end - largest_window + 1)
    ]
    frozen.score_boundaries(evidence, config)
    if not evidence:
        return None, evidence
    threshold = frozen.quantile(
        [item["score"] for item in evidence], config.threshold_quantile
    )
    for item in evidence:
        item["threshold"] = threshold
    candidates = []
    scores = [item["score"] for item in evidence]
    for index, item in enumerate(evidence):
        previous = scores[index - 1] if index else -1.0
        following = scores[index + 1] if index + 1 < len(scores) else -1.0
        if item["score"] >= threshold and item["score"] >= previous and item["score"] >= following:
            position = item["boundary_after_event"]
            if not frozen.is_safe_text_boundary(events, position):
                continue
            if position - start < config.min_segment_events or end - position < config.min_segment_events:
                continue
            left_score, left_signals = child_completeness(events[start:position])
            right_score, right_signals = child_completeness(events[position:end])
            # Conservative: both children need the three structural signals.
            if left_score < 0.90 or right_score < 0.90:
                continue
            item = dict(item)
            item.update({
                "recursive_split": True,
                "left_completeness": left_score,
                "right_completeness": right_score,
                "left_signals": left_signals,
                "right_signals": right_signals,
            })
            candidates.append(item)
    if not candidates:
        return None, evidence
    # Prefer strong score, then prefer a balanced split only as a tie-breaker.
    chosen = max(
        candidates,
        key=lambda item: (
            item["score"],
            min(item["left_completeness"], item["right_completeness"]),
            -abs((item["boundary_after_event"] - start) - (end - item["boundary_after_event"])),
        ),
    )
    return chosen, evidence


def recursive_boundaries(
    events: list[dict], vocabulary: list[str], config: frozen.SegmentationConfig, max_depth: int
) -> tuple[list[dict], list[dict]]:
    selected: list[dict] = []
    all_evidence: list[dict] = []

    def visit(start: int, end: int, depth: int) -> None:
        if depth >= max_depth:
            return
        chosen, evidence = local_best_split(events, start, end, vocabulary, config)
        all_evidence.extend(evidence)
        if chosen is None:
            return
        selected.append(chosen)
        position = chosen["boundary_after_event"]
        visit(start, position, depth + 1)
        visit(position, end, depth + 1)

    visit(0, len(events), 0)
    selected.sort(key=lambda item: item["boundary_after_event"])
    return selected, all_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--windows", default="13,25,37")
    parser.add_argument("--quantile", type=float, default=0.92)
    parser.add_argument("--min-gap", type=int, default=30)
    parser.add_argument("--min-segment", type=int, default=30)
    parser.add_argument("--overlap-events", type=int, default=25)
    parser.add_argument("--max-depth", type=int, default=10)
    args = parser.parse_args()
    windows = tuple(sorted({int(item) for item in args.windows.split(",") if item.strip()}))
    if not windows or min(windows) < 1 or args.min_gap < 1 or args.min_segment < 1 or args.overlap_events < 0 or args.max_depth < 1:
        parser.error("windows, min-gap, min-segment, max-depth must be positive; overlap-events must be non-negative")

    config = frozen.SegmentationConfig(
        formula_version="full-message-boundary-v1-recursive-recall-v1",
        windows=windows,
        threshold_quantile=args.quantile,
        min_gap_events=args.min_gap,
        min_segment_events=args.min_segment,
        category_weights={"tool_result": 0.0, "record:*": 0.0, "assistant_thinking": 0.25},
        safe_boundary_only=True,
        safe_boundary_radius=0,
        overlap_events=args.overlap_events,
    )
    source = frozen.load_json(args.input.resolve())
    mapping = source["mapping"]
    vocabulary = list(mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        events = session.get("events", [])
        selected, evidence = recursive_boundaries(events, vocabulary, config, args.max_depth)
        boundaries = [item["boundary_after_event"] for item in selected]
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
        frozen.plot_session(session, mapping, selected, evidence, args.output_dir / filename)
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session.get("session_id"),
            "event_count": len(events),
            "candidate_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "boundary_evidence": evidence,
            "segments": segments,
            "plot_file": filename,
        })

    output = {
        "formula": {
            **asdict(config),
            "max_depth": args.max_depth,
            "formula": "frozen boundary score + recursive safe split + child completeness gate",
            "selection": "recursively choose the strongest safe local maximum; accept only when both children have user text, assistant text, and tool-call evidence",
        },
        "mapping": mapping,
        "session_count": len(sessions),
        "total_event_count": sum(item["event_count"] for item in sessions),
        "total_selected_boundaries": sum(item["candidate_boundary_count"] for item in sessions),
        "total_segments": sum(len(item["segments"]) for item in sessions),
        "sessions": sessions,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"formula_version={config.formula_version}")
    print(f"sessions={output['session_count']}")
    print(f"events={output['total_event_count']}")
    print(f"selected_boundaries={output['total_selected_boundaries']}")
    print(f"segments={output['total_segments']}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
