#!/usr/bin/env python3
"""Best-first, confidence-gated segmentation for full message trajectories.

At every iteration the algorithm evaluates the best safe cut in every active
interval, accepts only the globally highest-confidence cut, and stops when
that confidence falls below the configured threshold. The confidence is an
auditable proxy score, not a calibrated probability.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import frozen_message_segmentation as frozen


def has_category(events: list[dict], category: str) -> bool:
    return any(event.get("category") == category for event in events)


def has_tool_call(events: list[dict]) -> bool:
    return any(event.get("category", "").startswith("tool_call:") for event in events)


def has_closure(events: list[dict]) -> bool:
    return any(
        event.get("category") == "assistant_text"
        and frozen.CLOSURE_RE.search(event.get("text", "") or "")
        for event in events
    )


def completeness(events: list[dict]) -> tuple[float, dict]:
    signals = {
        "user_text": has_category(events, "user_text"),
        "assistant_text": has_category(events, "assistant_text"),
        "tool_call": has_tool_call(events),
        "closure_text": has_closure(events),
    }
    value = (
        0.35 * signals["user_text"]
        + 0.25 * signals["assistant_text"]
        + 0.30 * signals["tool_call"]
        + 0.10 * signals["closure_text"]
    )
    return value, signals


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def nearby_goal_signal(events: list[dict], position: int, radius: int = 40) -> float:
    """Prefer boundaries near a new user goal, without requiring adjacency."""
    right = events[position:min(len(events), position + radius)]
    if any(event.get("category") == "user_text" for event in right):
        return 1.0
    left = events[max(0, position - radius):position]
    if any(event.get("category") == "user_text" for event in left):
        return 0.35
    return 0.0


def nearby_closure_signal(events: list[dict], position: int, radius: int = 20) -> float:
    left = events[max(0, position - radius):position]
    return 1.0 if has_closure(left) else 0.0


def interval_candidates(
    events: list[dict],
    start: int,
    end: int,
    vocabulary: list[str],
    config: frozen.SegmentationConfig,
    profile: str = "best-first-v1",
    goal_radius: int = 40,
) -> list[dict]:
    largest_window = max(config.windows)
    if end - start < 2 * config.min_segment_events + 2 * largest_window:
        return []
    evidence = [
        frozen.boundary_features(events, boundary, vocabulary, config)
        for boundary in range(start + largest_window, end - largest_window + 1)
    ]
    if not evidence:
        return []
    frozen.score_boundaries(evidence, config)
    scores = [item["score"] for item in evidence]
    threshold = frozen.quantile(scores, config.threshold_quantile)
    local_maxima = []
    for index, item in enumerate(evidence):
        position = item["boundary_after_event"]
        previous = scores[index - 1] if index else -1.0
        following = scores[index + 1] if index + 1 < len(scores) else -1.0
        if item["score"] < threshold or item["score"] < previous or item["score"] < following:
            continue
        if not frozen.is_safe_text_boundary(events, position):
            continue
        if position - start < config.min_segment_events or end - position < config.min_segment_events:
            continue
        left_value, left_signals = completeness(events[start:position])
        right_value, right_signals = completeness(events[position:end])
        if min(left_value, right_value) < 0.65:
            continue
        local_maxima.append({
            **item,
            "interval_start": start,
            "interval_end": end,
            "left_completeness": left_value,
            "right_completeness": right_value,
            "left_signals": left_signals,
            "right_signals": right_signals,
            "goal_change_signal": nearby_goal_signal(events, position, goal_radius),
            "closure_signal": nearby_closure_signal(events, position),
        })
    if profile == "optimized-v2":
        # Let the new label-informed features participate in candidate
        # selection, instead of selecting by the old score first.
        local_maxima.sort(
            key=lambda item: (
                0.30 * item["score"]
                + 0.20 * min(item["left_completeness"], item["right_completeness"])
                + 0.20 * item["goal_change_signal"]
                + 0.20 * item["closure_signal"]
                + 0.10 * 0.5
            ),
            reverse=True,
        )
    else:
        local_maxima.sort(key=lambda item: item["score"], reverse=True)
    if not local_maxima:
        return []
    best = local_maxima[0]
    second_score = local_maxima[1]["score"] if len(local_maxima) > 1 else 0.0
    margin = max(0.0, best["score"] - second_score)
    # Margin is deliberately bounded and auditable. One candidate gets a
    # neutral margin rather than an artificial certainty bonus.
    margin_signal = 0.5 if len(local_maxima) == 1 else sigmoid(12.0 * (margin - 0.05))
    best["score_margin"] = margin
    best["margin_signal"] = margin_signal
    best["goal_change_signal"] = nearby_goal_signal(events, best["boundary_after_event"], goal_radius)
    best["closure_signal"] = nearby_closure_signal(events, best["boundary_after_event"])
    if profile == "optimized-v2":
        best["confidence"] = (
            0.30 * best["score"]
            + 0.20 * min(best["left_completeness"], best["right_completeness"])
            + 0.20 * best["goal_change_signal"]
            + 0.20 * best["closure_signal"]
            + 0.10 * margin_signal
        )
    else:
        best["confidence"] = (
            0.50 * best["score"]
            + 0.25 * min(best["left_completeness"], best["right_completeness"])
            + 0.15 * best["text_boundary_signal"]
            + 0.10 * margin_signal
        )
    return [best]


def best_first_boundaries(
    events: list[dict],
    vocabulary: list[str],
    config: frozen.SegmentationConfig,
    confidence_threshold: float,
    max_splits: int,
    profile: str = "best-first-v1",
    goal_radius: int = 40,
) -> tuple[list[dict], list[dict]]:
    active = [(0, len(events))]
    accepted: list[dict] = []
    decisions: list[dict] = []
    while active and len(accepted) < max_splits:
        candidates = []
        for start, end in active:
            candidates.extend(interval_candidates(events, start, end, vocabulary, config, profile, goal_radius))
        if not candidates:
            break
        chosen = max(candidates, key=lambda item: item["confidence"])
        decision = {
            "iteration": len(decisions) + 1,
            "boundary_after_event": chosen["boundary_after_event"],
            "interval_start": chosen["interval_start"],
            "interval_end": chosen["interval_end"],
            "confidence": chosen["confidence"],
            "score": chosen["score"],
            "score_margin": chosen["score_margin"],
            "left_completeness": chosen["left_completeness"],
            "right_completeness": chosen["right_completeness"],
            "goal_change_signal": chosen.get("goal_change_signal", 0.0),
            "closure_signal": chosen.get("closure_signal", 0.0),
            "accepted": chosen["confidence"] >= confidence_threshold,
            "stop_reason": None,
        }
        decisions.append(decision)
        if chosen["confidence"] < confidence_threshold:
            decision["stop_reason"] = "best_confidence_below_threshold"
            break
        interval = (chosen["interval_start"], chosen["interval_end"])
        active.remove(interval)
        position = chosen["boundary_after_event"]
        active.extend([(interval[0], position), (position, interval[1])])
        accepted.append(chosen)
    accepted.sort(key=lambda item: item["boundary_after_event"])
    return accepted, decisions


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
    parser.add_argument("--confidence-threshold", type=float, default=0.72)
    parser.add_argument("--overlap-events", type=int, default=25)
    parser.add_argument("--max-splits", type=int, default=100)
    parser.add_argument("--profile", choices=["best-first-v1", "optimized-v2"], default="best-first-v1")
    parser.add_argument("--goal-radius", type=int, default=40)
    args = parser.parse_args()
    windows = tuple(sorted({int(item) for item in args.windows.split(",") if item.strip()}))
    if not windows or min(windows) < 1 or args.min_gap < 1 or args.min_segment < 1 or args.overlap_events < 0 or args.max_splits < 1 or not 0.0 < args.confidence_threshold < 1.0:
        parser.error("invalid segmentation parameters")

    config = frozen.SegmentationConfig(
        formula_version=f"full-message-boundary-v1-{args.profile}",
        windows=windows,
        threshold_quantile=args.quantile,
        min_gap_events=args.min_gap,
        min_segment_events=args.min_segment,
        category_weights={"tool_result": 0.0, "record:*": 0.0, "assistant_thinking": 0.25},
        safe_boundary_only=True,
        overlap_events=args.overlap_events,
    )
    source = frozen.load_json(args.input.resolve())
    mapping = source["mapping"]
    vocabulary = list(mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        events = session.get("events", [])
        selected, decisions = best_first_boundaries(
            events, vocabulary, config, args.confidence_threshold, args.max_splits, args.profile, args.goal_radius
        )
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
        frozen.plot_session(session, mapping, selected, [], args.output_dir / filename)
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session.get("session_id"),
            "event_count": len(events),
            "candidate_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "split_decisions": decisions,
            "segments": segments,
            "plot_file": filename,
        })

    output = {
        "formula": {
            **asdict(config),
            "confidence_threshold": args.confidence_threshold,
            "max_splits": args.max_splits,
            "goal_radius": args.goal_radius,
            "profile": args.profile,
            "formula": "optimized-v2: confidence = 0.30*boundary_score + 0.20*min_child_completeness + 0.20*goal_change + 0.20*closure_signal + 0.10*margin_signal" if args.profile == "optimized-v2" else "confidence = 0.50*boundary_score + 0.25*min_child_completeness + 0.15*safe_text_signal + 0.10*margin_signal",
            "confidence_note": "confidence is an auditable proxy score, not a calibrated probability",
            "selection": "best-first global split; stop when highest confidence is below threshold",
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
