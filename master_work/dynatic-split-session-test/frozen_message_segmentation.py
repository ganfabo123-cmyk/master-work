#!/usr/bin/env python3
"""Canonical parameterized segmentation model for full message trajectories.

The formula in this file is frozen as v1. Future experiments should change
only SegmentationConfig values, not the feature definitions or pipeline.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CLOSURE_RE = re.compile(
    r"\b(done|complete|completed|finished|success|successful|passed|passing|all set|summary|implemented|verified|ready)\b"
    r"|完成|通过|成功|验证|总结|已实现|好了",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SegmentationConfig:
    formula_version: str = "full-message-boundary-v1"
    windows: tuple[int, ...] = (7, 13, 19)
    threshold_quantile: float = 0.85
    min_gap_events: int = 15
    min_segment_events: int = 15
    js_weight: float = 0.65
    stability_weight: float = 0.20
    text_weight: float = 0.10
    closure_weight: float = 0.05
    category_weights: dict[str, float] = field(default_factory=lambda: {"tool_result": 0.0})
    safe_boundary_only: bool = False
    safe_boundary_radius: int = 0
    overlap_events: int = 0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def entropy(probabilities: list[float]) -> float:
    return -sum(p * math.log2(p) for p in probabilities if p > 0)


def distribution(events: list[dict], vocabulary: list[str], config: SegmentationConfig) -> list[float]:
    counts = Counter()
    total = 0.0
    for event in events:
        category = event["category"]
        weight = category_weight(category, config)
        if weight <= 0:
            continue
        counts[category] += weight
        total += weight
    total = max(total, 1e-12)
    return [counts[category] / total for category in vocabulary]


def category_weight(category: str, config: SegmentationConfig) -> float:
    if category in config.category_weights:
        return config.category_weights[category]
    if category.startswith("record:") and "record:*" in config.category_weights:
        return config.category_weights["record:*"]
    return 1.0


def js_divergence(left: list[float], right: list[float]) -> float:
    midpoint = [(a + b) / 2 for a, b in zip(left, right)]
    return entropy(midpoint) - entropy(left) / 2 - entropy(right) / 2


def quantile(values: list[float], level: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * level
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    ratio = position - lower
    return ordered[lower] * (1 - ratio) + ordered[upper] * ratio


def normalized(value: float, reference: float) -> float:
    return min(1.0, value / max(reference, 1e-12))


def text_features(left: dict, right: dict) -> tuple[float, float]:
    left_category = left.get("category", "")
    right_category = right.get("category", "")
    left_text = left.get("text", "") or ""
    right_text = right.get("text", "") or ""
    if right_category == "user_text":
        text_signal = 1.0
    elif left_category == "assistant_text":
        text_signal = 0.75
    elif left_category.endswith("_text") or right_category.endswith("_text"):
        text_signal = 0.3
    else:
        text_signal = 0.0
    closure_signal = 0.0
    if left_category == "assistant_text" and CLOSURE_RE.search(left_text):
        closure_signal = 1.0
    if right_category == "user_text" and CLOSURE_RE.search(right_text):
        closure_signal = max(closure_signal, 0.5)
    return text_signal, closure_signal


def boundary_features(events: list[dict], boundary: int, vocabulary: list[str], config: SegmentationConfig) -> dict:
    per_window = {}
    for window in config.windows:
        left = events[boundary - window:boundary]
        right = events[boundary:boundary + window]
        per_window[str(window)] = {
            "js_divergence": js_divergence(
                distribution(left, vocabulary, config),
                distribution(right, vocabulary, config),
            ),
        }
    text_signal, closure_signal = text_features(events[boundary - 1], events[boundary])
    return {
        "boundary_after_event": boundary,
        "by_window": per_window,
        "js_mean": mean(item["js_divergence"] for item in per_window.values()),
        "js_min": min(item["js_divergence"] for item in per_window.values()),
        "text_boundary_signal": text_signal,
        "closure_signal": closure_signal,
    }


def score_boundaries(evidence: list[dict], config: SegmentationConfig) -> None:
    js_by_window = {
        window: [item["by_window"][str(window)]["js_divergence"] for item in evidence]
        for window in config.windows
    }
    references = {window: max(quantile(values, 0.95), 1e-12) for window, values in js_by_window.items()}
    thresholds = {window: quantile(values, config.threshold_quantile) for window, values in js_by_window.items()}
    for item in evidence:
        normalized_js = mean(
            normalized(item["by_window"][str(window)]["js_divergence"], references[window])
            for window in config.windows
        )
        stability = mean(
            item["by_window"][str(window)]["js_divergence"] >= thresholds[window]
            for window in config.windows
        )
        item["normalized_js"] = normalized_js
        item["multiscale_stability"] = stability
        item["score"] = (
            config.js_weight * normalized_js
            + config.stability_weight * stability
            + config.text_weight * item["text_boundary_signal"]
            + config.closure_weight * item["closure_signal"]
        )


def select_boundaries(events: list[dict], vocabulary: list[str], config: SegmentationConfig) -> tuple[list[dict], list[dict]]:
    largest_window = max(config.windows)
    if len(events) < 2 * largest_window + config.min_segment_events:
        return [], []
    evidence = [
        boundary_features(events, boundary, vocabulary, config)
        for boundary in range(largest_window, len(events) - largest_window + 1)
    ]
    score_boundaries(evidence, config)
    scores = [item["score"] for item in evidence]
    threshold = quantile(scores, config.threshold_quantile)
    candidates = []
    for index, item in enumerate(evidence):
        previous = scores[index - 1] if index else -1.0
        following = scores[index + 1] if index + 1 < len(scores) else -1.0
        item["threshold"] = threshold
        item["is_candidate"] = item["score"] >= threshold and item["score"] >= previous and item["score"] >= following
        if item["is_candidate"]:
            candidates.append(item)

    selected = []
    for item in sorted(candidates, key=lambda value: value["score"], reverse=True):
        position = item["boundary_after_event"]
        if position < config.min_segment_events or len(events) - position < config.min_segment_events:
            continue
        if all(abs(position - other["boundary_after_event"]) >= config.min_gap_events for other in selected):
            selected.append(item)
    selected.sort(key=lambda item: item["boundary_after_event"])
    selected_positions = {item["boundary_after_event"] for item in selected}
    for item in evidence:
        item["selected"] = item["boundary_after_event"] in selected_positions
    return selected, evidence


def is_safe_text_boundary(events: list[dict], position: int) -> bool:
    """Return whether a boundary is adjacent to a human-readable text message."""
    if position <= 0 or position >= len(events):
        return False
    left_category = events[position - 1].get("category", "")
    right_category = events[position].get("category", "")
    return left_category == "assistant_text" or right_category == "user_text"


def project_to_safe_boundaries(
    events: list[dict], selected: list[dict], config: SegmentationConfig
) -> list[dict]:
    """Move statistical cuts to nearby text boundaries, dropping unsafe cuts."""
    if not config.safe_boundary_only:
        return selected
    safe_positions = [
        position
        for position in range(1, len(events))
        if is_safe_text_boundary(events, position)
    ]
    projected = []
    used = set()
    for item in selected:
        source_position = item["boundary_after_event"]
        choices = [
            position for position in safe_positions
            if abs(position - source_position) <= config.safe_boundary_radius
        ]
        if not choices:
            continue
        position = min(choices, key=lambda candidate: (abs(candidate - source_position), candidate))
        if position in used:
            continue
        projected_item = dict(item)
        projected_item["statistical_boundary_after_event"] = source_position
        projected_item["boundary_after_event"] = position
        projected_item["boundary_projection_distance"] = abs(position - source_position)
        projected_item["safe_boundary"] = True
        projected.append(projected_item)
        used.add(position)
    projected.sort(key=lambda value: value["boundary_after_event"])
    filtered = []
    previous = 0
    for item in projected:
        position = item["boundary_after_event"]
        if position - previous < config.min_segment_events:
            continue
        if len(events) - position < config.min_segment_events:
            continue
        if filtered and position - filtered[-1]["boundary_after_event"] < config.min_gap_events:
            continue
        filtered.append(item)
        previous = position
    return filtered


def plot_session(session: dict, mapping: dict[str, float], selected: list[dict], evidence: list[dict], output: Path) -> None:
    events = session.get("events", [])
    values = [mapping[event["category"]] for event in events]
    figure, axes = plt.subplots(2, 1, figsize=(16, 7), sharex=True, constrained_layout=True)
    if values:
        x_values = list(range(1, len(values) + 1))
        axes[0].step(x_values, values, where="mid", linewidth=0.65, alpha=0.65)
        axes[0].set_ylim(min(mapping.values()) - 0.05, max(mapping.values()) + 0.05)
        axes[0].set_yticks(list(mapping.values()))
        axes[0].set_yticklabels([name for name, _ in sorted(mapping.items(), key=lambda item: item[1])], fontsize=6)
        axes[0].set_ylabel("Message ID")
        if evidence:
            positions = [item["boundary_after_event"] for item in evidence]
            axes[1].plot(positions, [item["score"] for item in evidence], label="score", linewidth=1.0)
            axes[1].plot(positions, [item["js_mean"] for item in evidence], label="mean JS", linewidth=0.8, alpha=0.65)
            axes[1].axhline(evidence[0]["threshold"], linestyle="--", linewidth=0.8, label="threshold")
            axes[1].set_ylabel("Boundary score")
        for item in selected:
            position = item["boundary_after_event"]
            axes[0].axvline(position + 0.5, linestyle="--", linewidth=0.9, alpha=0.8)
            axes[1].axvline(position, linestyle="--", linewidth=0.9, alpha=0.8)
        axes[1].set_xlabel("Message event index / boundary after event")
        if evidence:
            axes[1].legend(loc="upper right")
    else:
        for axis in axes:
            axis.text(0.5, 0.5, "No message events", ha="center", va="center", transform=axis.transAxes)
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
    label = f"{session.get('harness', 'unknown')} / {session.get('session_id', 'unknown')}"
    figure.suptitle(f"Frozen formula segmentation: {label}")
    figure.savefig(output, dpi=150)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--output", type=Path, default=base / "frozen-full-message-segments.json")
    parser.add_argument("--output-dir", type=Path, default=base / "frozen-full-message-plots")
    parser.add_argument("--windows", default="7,13,19")
    parser.add_argument("--quantile", type=float, default=0.85)
    parser.add_argument("--min-gap", type=int, default=15)
    parser.add_argument("--min-segment", type=int, default=15)
    parser.add_argument("--profile", choices=["frozen-v1", "recommended-v2"], default="frozen-v1")
    parser.add_argument("--safe-boundary", action="store_true", help="Keep cuts only near assistant/user text boundaries")
    parser.add_argument("--safe-radius", type=int, default=0, help="Maximum distance from a statistical cut to a safe text boundary")
    parser.add_argument("--overlap-events", type=int, default=0, help="Duplicate this many events on each side of every core cut")
    args = parser.parse_args()
    windows = tuple(sorted({int(item) for item in args.windows.split(",") if item.strip()}))
    if not windows or min(windows) < 1 or args.min_gap < 1 or args.min_segment < 1 or args.safe_radius < 0 or args.overlap_events < 0 or not 0.0 < args.quantile < 1.0:
        parser.error("windows, min-gap, min-segment, safe-radius, and overlap-events must be valid; quantile must be between 0 and 1")

    if args.profile == "recommended-v2":
        category_weights = {"tool_result": 0.0, "record:*": 0.0, "assistant_thinking": 0.25}
        formula_version = "full-message-boundary-v1-recommended-v2"
    else:
        category_weights = {"tool_result": 0.0}
        formula_version = "full-message-boundary-v1"
    config = SegmentationConfig(
        formula_version=formula_version,
        windows=windows,
        threshold_quantile=args.quantile,
        min_gap_events=args.min_gap,
        min_segment_events=args.min_segment,
        category_weights=category_weights,
        safe_boundary_only=args.safe_boundary,
        safe_boundary_radius=args.safe_radius,
        overlap_events=args.overlap_events,
    )
    source = load_json(args.input.resolve())
    mapping = source["mapping"]
    vocabulary = list(mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        events = session.get("events", [])
        selected, evidence = select_boundaries(events, vocabulary, config)
        selected = project_to_safe_boundaries(events, selected, config)
        boundaries = [item["boundary_after_event"] for item in selected]
        core_ranges = list(zip([0, *boundaries], [*boundaries, len(events)]))
        segments = []
        for index, (core_start, core_end) in enumerate(core_ranges, start=1):
            start = max(0, core_start - config.overlap_events)
            end = min(len(events), core_end + config.overlap_events)
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
        plot_session(session, mapping, selected, evidence, args.output_dir / filename)
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session.get("session_id"),
            "event_count": len(events),
            "candidate_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "statistical_boundaries_after_event": [item.get("statistical_boundary_after_event", item["boundary_after_event"]) for item in selected],
            "segments": segments,
            "boundary_evidence": evidence,
            "plot_file": filename,
        })

    output = {
        "formula": {
            **asdict(config),
            "formula": "score(t) = js_weight*normalized_mean_js + stability_weight*multiscale_stability + text_weight*text_boundary_signal + closure_weight*closure_signal",
            "selection": "local maxima above per-session quantile, non-maximum suppression by min_gap_events, and edge/short-segment constraints",
            "category_weight_default": 1.0,
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
