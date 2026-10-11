#!/usr/bin/env python3
"""Cut full message trajectories with distribution and text-boundary evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CLOSURE_RE = re.compile(r"\b(done|complete|completed|finished|success|successful|passed|passing|all set|summary|implemented|verified|ready)\b|完成|通过|成功|验证|总结|已实现|好了", re.IGNORECASE)
ZERO_WEIGHT_CATEGORIES = {"tool_result"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def distribution(categories: list[str], vocabulary: list[str]) -> list[float]:
    counts = Counter(categories)
    total = max(1, len(categories))
    return [counts[item] / total for item in vocabulary]


def entropy(probabilities: list[float]) -> float:
    return -sum(p * math.log2(p) for p in probabilities if p > 0)


def js_divergence(left: list[float], right: list[float]) -> float:
    midpoint = [(a + b) / 2 for a, b in zip(left, right)]
    return entropy(midpoint) - entropy(left) / 2 - entropy(right) / 2


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    ratio = position - lower
    return ordered[lower] * (1 - ratio) + ordered[upper] * ratio


def normalized(value: float, reference: float) -> float:
    return min(1.0, value / max(reference, 1e-12))


def text_boundary_signal(left: dict, right: dict) -> tuple[float, float]:
    left_category = left.get("category", "")
    right_category = right.get("category", "")
    left_text = left.get("text", "") or ""
    right_text = right.get("text", "") or ""
    signal = 0.0
    closure = 0.0
    if right_category == "user_text":
        signal = 1.0
    elif left_category == "assistant_text":
        signal = 0.75
    elif left_category.endswith("_text") or right_category.endswith("_text"):
        signal = 0.3
    if left_category == "assistant_text" and CLOSURE_RE.search(left_text):
        closure = 1.0
    if right_category == "user_text" and CLOSURE_RE.search(right_text):
        closure = max(closure, 0.5)
    return signal, closure


def boundary_evidence(events: list[dict], boundary: int, windows: list[int], vocabulary: list[str]) -> dict:
    per_window = {}
    for window in windows:
        left_categories = [
            event["category"] for event in events[boundary - window:boundary]
            if event["category"] not in ZERO_WEIGHT_CATEGORIES
        ]
        right_categories = [
            event["category"] for event in events[boundary:boundary + window]
            if event["category"] not in ZERO_WEIGHT_CATEGORIES
        ]
        per_window[str(window)] = {
            "js_divergence": js_divergence(distribution(left_categories, vocabulary), distribution(right_categories, vocabulary)),
            "left_size": len(left_categories),
            "right_size": len(right_categories),
        }
    text_signal, closure_signal = text_boundary_signal(events[boundary - 1], events[boundary])
    return {
        "boundary_after_event": boundary,
        "by_window": per_window,
        "js_mean": mean(item["js_divergence"] for item in per_window.values()),
        "js_min": min(item["js_divergence"] for item in per_window.values()),
        "text_boundary_signal": text_signal,
        "closure_signal": closure_signal,
    }


def score_evidence(evidence: list[dict], windows: list[int], threshold_quantile: float) -> None:
    js_values = {
        window: [item["by_window"][str(window)]["js_divergence"] for item in evidence]
        for window in windows
    }
    references = {window: max(quantile(values, 0.95), 1e-12) for window, values in js_values.items()}
    for item in evidence:
        normalized_js = mean(
            normalized(item["by_window"][str(window)]["js_divergence"], references[window])
            for window in windows
        )
        stability = mean(
            item["by_window"][str(window)]["js_divergence"] >= quantile(js_values[window], threshold_quantile)
            for window in windows
        )
        item["normalized_js"] = normalized_js
        item["multiscale_stability"] = stability
        item["score"] = (
            0.65 * normalized_js
            + 0.20 * stability
            + 0.10 * item["text_boundary_signal"]
            + 0.05 * item["closure_signal"]
        )


def choose_boundaries(events: list[dict], vocabulary: list[str], windows: list[int], min_gap: int, threshold_quantile: float) -> tuple[list[dict], list[dict]]:
    largest = max(windows)
    if len(events) < 2 * largest + 1:
        return [], []
    evidence = [
        boundary_evidence(events, boundary, windows, vocabulary)
        for boundary in range(largest, len(events) - largest + 1)
    ]
    score_evidence(evidence, windows, threshold_quantile)
    scores = [item["score"] for item in evidence]
    threshold = quantile(scores, threshold_quantile)
    candidates = []
    for index, item in enumerate(evidence):
        item["threshold"] = threshold
        previous = scores[index - 1] if index else -1.0
        following = scores[index + 1] if index + 1 < len(scores) else -1.0
        item["is_candidate"] = item["score"] >= threshold and item["score"] >= previous and item["score"] >= following
        if item["is_candidate"]:
            candidates.append(item)
    selected = []
    for item in sorted(candidates, key=lambda value: value["score"], reverse=True):
        if all(abs(item["boundary_after_event"] - other["boundary_after_event"]) >= min_gap for other in selected):
            selected.append(item)
    selected.sort(key=lambda value: value["boundary_after_event"])
    selected_positions = {item["boundary_after_event"] for item in selected}
    for item in evidence:
        item["selected"] = item["boundary_after_event"] in selected_positions
    return selected, evidence


def plot_session(session: dict, events: list[dict], mapping: dict[str, float], selected: list[dict], evidence: list[dict], output: Path) -> None:
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
            x = [item["boundary_after_event"] for item in evidence]
            axes[1].plot(x, [item["score"] for item in evidence], label="full-message score", linewidth=1.0)
            axes[1].plot(x, [item["js_mean"] for item in evidence], label="mean JS", linewidth=0.8, alpha=0.65)
            axes[1].axhline(evidence[0]["threshold"], linestyle="--", linewidth=0.8, label="85% threshold")
            axes[1].set_ylabel("Boundary score")
            axes[1].set_xlabel("Message event index / boundary after event")
            axes[1].legend(loc="upper right")
        for item in selected:
            axes[0].axvline(item["boundary_after_event"] + 0.5, linestyle="--", linewidth=0.9, alpha=0.8)
            axes[1].axvline(item["boundary_after_event"], linestyle="--", linewidth=0.9, alpha=0.8)
    else:
        for axis in axes:
            axis.text(0.5, 0.5, "No message events", ha="center", va="center", transform=axis.transAxes)
    label = f"{session.get('harness', 'unknown')} / {session.get('session_id', 'unknown')}"
    figure.suptitle(f"Full-message segmentation: {label}")
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
    figure.savefig(output, dpi=150)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--output", type=Path, default=base / "full-message-segments.json")
    parser.add_argument("--output-dir", type=Path, default=base / "full-message-segment-plots")
    parser.add_argument("--windows", default="7,13,19")
    parser.add_argument("--min-gap", type=int, default=15)
    parser.add_argument("--quantile", type=float, default=0.85)
    args = parser.parse_args()
    windows = sorted({int(item) for item in args.windows.split(",") if item.strip()})
    if not windows or min(windows) < 1 or args.min_gap < 1 or not 0.0 < args.quantile < 1.0:
        parser.error("windows/min-gap must be positive and quantile must be between 0 and 1")

    source = load_json(args.input.resolve())
    mapping = source["mapping"]
    vocabulary = list(mapping)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        events = session.get("events", [])
        selected, evidence = choose_boundaries(events, vocabulary, windows, args.min_gap, args.quantile)
        boundaries = [item["boundary_after_event"] for item in selected]
        starts = [0, *boundaries]
        ends = [*boundaries, len(events)]
        segments = []
        for index, (start, end) in enumerate(zip(starts, ends), start=1):
            part = events[start:end]
            categories = Counter(event["category"] for event in part)
            segments.append({
                "segment_index": index,
                "start_event": start + 1,
                "end_event": end,
                "length": len(part),
                "first_category": part[0]["category"] if part else None,
                "last_category": part[-1]["category"] if part else None,
                "dominant_category": categories.most_common(1)[0][0] if categories else None,
                "category_counts": dict(categories.most_common()),
                "events": part,
            })
        filename = f"{session.get('harness', 'unknown')}__{session.get('session_id', 'unknown')}.png"
        plot_session(session, events, mapping, selected, evidence, args.output_dir / filename)
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session.get("session_id"),
            "event_count": len(events),
            "candidate_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "segments": segments,
            "boundary_evidence": evidence,
            "plot_file": filename,
        })

    output = {
        "method": {
            "signals": ["multi-scale JS divergence over all message categories", "text boundary prior", "closure-language prior", "multi-scale stability"],
            "formula": "score = 0.65 * normalized_mean_js + 0.20 * multiscale_stability + 0.10 * text_boundary_signal + 0.05 * closure_signal",
            "category_weights": {"tool_result": 0.0, "other_categories": 1.0},
            "zero_weight_categories": sorted(ZERO_WEIGHT_CATEGORIES),
            "windows": windows,
            "min_gap_events": args.min_gap,
            "threshold_quantile": args.quantile,
            "text_boundary_rule": "right user_text or left assistant_text receives a prior; closure words add a small bonus",
            "status": "first mathematical baseline; weights are explicit hyperparameters and not tuned",
        },
        "mapping": mapping,
        "session_count": len(sessions),
        "total_event_count": sum(item["event_count"] for item in sessions),
        "total_selected_boundaries": sum(item["candidate_boundary_count"] for item in sessions),
        "total_segments": sum(len(item["segments"]) for item in sessions),
        "sessions": sessions,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sessions={len(sessions)}")
    print(f"events={output['total_event_count']}")
    print(f"selected_boundaries={output['total_selected_boundaries']}")
    print(f"segments={output['total_segments']}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
