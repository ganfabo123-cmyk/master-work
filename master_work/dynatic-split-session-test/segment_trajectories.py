#!/usr/bin/env python3
"""Detect stable candidate boundaries in tool trajectories.

The trajectory values are used only for plotting. Boundary detection compares
tool distributions on both sides of a position, at several window sizes.
The final score rewards distribution change, multi-scale stability, and
supporting changes in entropy/switch rate.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def distribution(values: list[float], tool_ids: list[float]) -> list[float]:
    counts = Counter(values)
    total = max(1, len(values))
    return [counts[tool_id] / total for tool_id in tool_ids]


def entropy(probabilities: list[float]) -> float:
    return -sum(p * math.log2(p) for p in probabilities if p > 0)


def js_divergence(left: list[float], right: list[float]) -> float:
    midpoint = [(a + b) / 2 for a, b in zip(left, right)]
    return entropy(midpoint) - entropy(left) / 2 - entropy(right) / 2


def switch_rate(values: list[float]) -> float:
    return sum(a != b for a, b in zip(values, values[1:])) / max(1, len(values) - 1)


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def minmax_normalize(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    low = min(values)
    high = max(values)
    if high <= low:
        return 0.0
    return (value - low) / (high - low)


def window_evidence(values: list[float], boundary: int, window: int, tool_ids: list[float]) -> dict:
    left = values[boundary - window:boundary]
    right = values[boundary:boundary + window]
    left_distribution = distribution(left, tool_ids)
    right_distribution = distribution(right, tool_ids)
    return {
        "window": window,
        "js_divergence": js_divergence(left_distribution, right_distribution),
        "left_switch_rate": switch_rate(left),
        "right_switch_rate": switch_rate(right),
        "switch_rate_delta": switch_rate(right) - switch_rate(left),
        "left_entropy": entropy(left_distribution),
        "right_entropy": entropy(right_distribution),
        "entropy_delta": entropy(right_distribution) - entropy(left_distribution),
        "left_distribution": {
            str(tool_id): probability
            for tool_id, probability in zip(tool_ids, left_distribution)
            if probability > 0
        },
        "right_distribution": {
            str(tool_id): probability
            for tool_id, probability in zip(tool_ids, right_distribution)
            if probability > 0
        },
    }


def add_multiscale_scores(evidence: list[dict], windows: list[int], quantile_level: float) -> None:
    """Add a comparable score to every boundary evidence item in-place."""
    js_by_window = {
        window: [item["by_window"][str(window)]["js_divergence"] for item in evidence]
        for window in windows
    }
    js_reference = {
        window: max(quantile(values, 0.95), 1e-12)
        for window, values in js_by_window.items()
    }
    all_entropy_delta = [abs(item["entropy_delta_mean"]) for item in evidence]
    all_switch_delta = [abs(item["switch_rate_delta_mean"]) for item in evidence]

    for item in evidence:
        normalized_js = mean(
            min(1.0, item["by_window"][str(window)]["js_divergence"] / js_reference[window])
            for window in windows
        )
        stability = mean(
            item["by_window"][str(window)]["js_divergence"]
            >= quantile(js_by_window[window], quantile_level)
            for window in windows
        )
        entropy_support = minmax_normalize(abs(item["entropy_delta_mean"]), all_entropy_delta)
        switch_support = minmax_normalize(abs(item["switch_rate_delta_mean"]), all_switch_delta)
        support = (entropy_support + switch_support) / 2
        item["normalized_js"] = normalized_js
        item["multiscale_stability"] = stability
        item["supporting_change"] = support
        item["score"] = 0.7 * normalized_js + 0.2 * stability + 0.1 * support
        item["threshold"] = None


def boundary_evidence(values: list[float], boundary: int, windows: list[int], tool_ids: list[float]) -> dict:
    by_window = {
        str(window): window_evidence(values, boundary, window, tool_ids)
        for window in windows
    }
    return {
        "boundary_after_call": boundary,
        "by_window": by_window,
        "js_divergence_mean": mean(item["js_divergence"] for item in by_window.values()),
        "js_divergence_min": min(item["js_divergence"] for item in by_window.values()),
        "entropy_delta_mean": mean(item["entropy_delta"] for item in by_window.values()),
        "switch_rate_delta_mean": mean(item["switch_rate_delta"] for item in by_window.values()),
    }


def choose_boundaries(values: list[float], windows: list[int], min_gap: int, quantile_level: float, tool_ids: list[float]) -> tuple[list[dict], list[dict]]:
    largest_window = max(windows)
    if len(values) < 2 * largest_window + 1:
        return [], []

    evidence = [
        boundary_evidence(values, boundary, windows, tool_ids)
        for boundary in range(largest_window, len(values) - largest_window + 1)
    ]
    add_multiscale_scores(evidence, windows, quantile_level)
    scores = [item["score"] for item in evidence]
    threshold = quantile(scores, quantile_level)
    candidates = []
    for index, item in enumerate(evidence):
        previous_score = scores[index - 1] if index > 0 else -1.0
        next_score = scores[index + 1] if index + 1 < len(scores) else -1.0
        item["threshold"] = threshold
        item["is_candidate"] = item["score"] >= threshold and item["score"] >= previous_score and item["score"] >= next_score
        if item["is_candidate"]:
            candidates.append(item)

    selected: list[dict] = []
    for item in sorted(candidates, key=lambda value: value["score"], reverse=True):
        if all(abs(item["boundary_after_call"] - other["boundary_after_call"]) >= min_gap for other in selected):
            selected.append(item)
    selected.sort(key=lambda value: value["boundary_after_call"])
    selected_positions = {item["boundary_after_call"] for item in selected}
    for item in evidence:
        item["selected"] = item["boundary_after_call"] in selected_positions
    return selected, evidence


def segment_summary(values: list[float], names: list[str], boundaries: list[int]) -> list[dict]:
    result: list[dict] = []
    starts = [0, *boundaries]
    ends = [*boundaries, len(values)]
    tool_ids = sorted(set(values))
    for index, (start, end) in enumerate(zip(starts, ends), start=1):
        segment_values = values[start:end]
        segment_names = names[start:end]
        counts = Counter(segment_names)
        result.append({
            "segment_index": index,
            "start_call": start + 1,
            "end_call": end,
            "length": len(segment_values),
            "dominant_tool": counts.most_common(1)[0][0] if counts else None,
            "tool_counts": dict(counts.most_common()),
            "tool_entropy": entropy(distribution(segment_values, tool_ids)) if segment_values else 0.0,
            "switch_rate": switch_rate(segment_values),
        })
    return result


def plot_session(session: dict, mapping: dict[str, float], output_dir: Path, windows: list[int], min_gap: int, quantile_level: float) -> dict:
    values = list(session.get("trajectory", []))
    names = list(session.get("tool_names", []))
    tool_ids = sorted(set(mapping.values()))
    selected, evidence = choose_boundaries(values, windows, min_gap, quantile_level, tool_ids)
    boundaries = [item["boundary_after_call"] for item in selected]
    segments = segment_summary(values, names, boundaries) if values else []

    figure, axes = plt.subplots(2, 1, figsize=(15, 7), sharex=True, constrained_layout=True)
    if values:
        x_values = list(range(1, len(values) + 1))
        axes[0].step(x_values, values, where="mid", linewidth=0.8, alpha=0.7)
        axes[0].set_ylim(min(mapping.values()) - 0.05, max(mapping.values()) + 0.05)
        axes[0].set_yticks(tool_ids)
        axes[0].set_yticklabels([name for name, _ in sorted(mapping.items(), key=lambda item: item[1])], fontsize=8)
        axes[0].set_ylabel("Tool ID")
        boundary_x = [item["boundary_after_call"] for item in evidence]
        axes[1].plot(boundary_x, [item["score"] for item in evidence], linewidth=1.0, label="multiscale score")
        axes[1].plot(boundary_x, [item["js_divergence_mean"] for item in evidence], linewidth=0.8, alpha=0.6, label="mean JS")
        axes[1].set_ylabel("Boundary score")
        axes[1].set_xlabel("Tool-call index / candidate boundary after call")
        threshold = evidence[0]["threshold"] if evidence else 0.0
        axes[1].axhline(threshold, linestyle="--", linewidth=0.9, label=f"{quantile_level:.0%} threshold")
        axes[1].legend(loc="upper right")
        for boundary in boundaries:
            axes[0].axvline(boundary + 0.5, linestyle="--", linewidth=1.0, alpha=0.75)
            axes[1].axvline(boundary, linestyle="--", linewidth=1.0, alpha=0.75)
    else:
        for axis in axes:
            axis.text(0.5, 0.5, "No tool calls", ha="center", va="center", transform=axis.transAxes)
        axes[1].set_xlabel("Tool-call index / candidate boundary after call")

    for axis in axes:
        axis.grid(axis="y", alpha=0.25)
    label = f"{session.get('harness', 'unknown')} / {session.get('session_id', 'unknown')}"
    figure.suptitle(f"Multiscale candidate segmentation: {label}")
    filename = f"{session.get('harness', 'unknown')}__{session.get('session_id', 'unknown')}.png"
    figure.savefig(output_dir / filename, dpi=150)
    plt.close(figure)

    return {
        "harness": session.get("harness"),
        "session_id": session.get("session_id"),
        "tool_call_count": len(values),
        "candidate_boundary_count": len(boundaries),
        "candidate_boundaries_after_call": boundaries,
        "segments": segments,
        "boundary_evidence": evidence,
        "plot_file": filename,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().with_name("session-trajectories.json"))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().with_name("multiscale-trajectory-plots"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().with_name("multiscale-trajectory-segments.json"))
    parser.add_argument("--windows", default="7,9,13", help="Comma-separated calls on each side (default: 7,9,13)")
    parser.add_argument("--min-gap", type=int, default=10, help="Minimum calls between selected boundaries (default: 10)")
    parser.add_argument("--quantile", type=float, default=0.85, help="Per-session score threshold quantile (default: 0.85)")
    args = parser.parse_args()

    try:
        windows = sorted({int(item) for item in args.windows.split(",") if item.strip()})
    except ValueError as error:
        parser.error(f"invalid --windows: {error}")
    if not windows or min(windows) < 1 or args.min_gap < 1 or not 0.0 < args.quantile < 1.0:
        parser.error("windows and min-gap must be positive; quantile must be between 0 and 1")

    source = load_json(args.input.resolve())
    mapping = source.get("mapping", {})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = [
        plot_session(session, mapping, args.output_dir, windows, args.min_gap, args.quantile)
        for session in source.get("trajectories", [])
    ]
    selected_count = sum(item["candidate_boundary_count"] for item in sessions)
    output = {
        "mapping": mapping,
        "method": {
            "primary_signal": "multi-scale Jensen-Shannon divergence between left and right tool distributions",
            "formula": "score = 0.7 * normalized_mean_js + 0.2 * multiscale_stability + 0.1 * supporting_change",
            "supporting_signals": ["entropy_delta", "switch_rate_delta"],
            "windows": windows,
            "min_gap": args.min_gap,
            "quantile": args.quantile,
            "boundary_semantics": "boundary_after_call is the last call in the left slice; the next call starts the right slice",
            "interpretation": "selected boundaries are statistically supported candidates, not ground-truth atomic boundaries",
        },
        "session_count": len(sessions),
        "candidate_boundary_count": selected_count,
        "sessions": sessions,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sessions={len(sessions)}")
    print(f"candidate_boundaries={selected_count}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
