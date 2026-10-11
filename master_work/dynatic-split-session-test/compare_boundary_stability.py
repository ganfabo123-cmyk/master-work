#!/usr/bin/env python3
"""Compare candidate boundaries detected at several observation windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from segment_trajectories import boundary_evidence, quantile


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def local_peaks(values: list[dict], quantile_level: float) -> list[dict]:
    if not values:
        return []
    scores = [item["js_divergence"] for item in values]
    threshold = quantile(scores, quantile_level)
    peaks = []
    for index, item in enumerate(values):
        previous = scores[index - 1] if index else -1.0
        following = scores[index + 1] if index + 1 < len(scores) else -1.0
        if item["js_divergence"] >= threshold and item["js_divergence"] >= previous and item["js_divergence"] >= following:
            peaks.append({
                "boundary_after_call": item["boundary_after_call"],
                "window": item["window"],
                "js_divergence": item["js_divergence"],
                "threshold": threshold,
            })
    return peaks


def cluster_peaks(peaks: list[dict], tolerance: int, window_count: int) -> list[dict]:
    if not peaks:
        return []
    ordered = sorted(peaks, key=lambda item: item["boundary_after_call"])
    groups: list[list[dict]] = [[ordered[0]]]
    for item in ordered[1:]:
        if item["boundary_after_call"] - groups[-1][-1]["boundary_after_call"] <= tolerance:
            groups[-1].append(item)
        else:
            groups.append([item])

    result = []
    for group in groups:
        positions = [item["boundary_after_call"] for item in group]
        by_window = {str(item["window"]): item for item in group}
        recurrence = len(by_window)
        result.append({
            "representative_boundary_after_call": round(sum(positions) / len(positions)),
            "matched_boundaries_after_call": positions,
            "supporting_windows": sorted(int(window) for window in by_window),
            "recurrence": recurrence,
            "recurrence_ratio": recurrence / window_count,
            "confidence_class": (
                "all_windows" if recurrence == window_count
                else "multi_window" if recurrence >= 2
                else "single_window"
            ),
            "max_js_divergence": max(item["js_divergence"] for item in group),
        })
    return result


def analyze_session(session: dict, windows: list[int], quantile_level: float, tolerance: int, tool_ids: list[float]) -> dict:
    values = list(session.get("trajectory", []))
    per_window = {}
    all_peaks = []
    for window in windows:
        if len(values) < 2 * window + 1:
            per_window[str(window)] = {"eligible": False, "peaks": []}
            continue
        evidence = [
            boundary_evidence(values, boundary, [window], tool_ids)["by_window"][str(window)]
            | {"boundary_after_call": boundary, "window": window}
            for boundary in range(window, len(values) - window + 1)
        ]
        peaks = local_peaks(evidence, quantile_level)
        per_window[str(window)] = {"eligible": True, "peaks": peaks}
        all_peaks.extend(peaks)

    clusters = cluster_peaks(all_peaks, tolerance, len(windows))
    return {
        "harness": session.get("harness"),
        "session_id": session.get("session_id"),
        "tool_call_count": len(values),
        "per_window": per_window,
        "stable_boundaries": clusters,
        "multi_window_boundary_count": sum(item["recurrence"] >= 2 for item in clusters),
        "all_window_boundary_count": sum(item["recurrence"] == len(windows) for item in clusters),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().with_name("session-trajectories.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().with_name("boundary-stability.json"))
    parser.add_argument("--windows", default="7,9,13")
    parser.add_argument("--quantile", type=float, default=0.85)
    parser.add_argument("--tolerance", type=int, default=2, help="Maximum call-index distance for matching peaks")
    args = parser.parse_args()

    windows = sorted({int(item) for item in args.windows.split(",") if item.strip()})
    if not windows or min(windows) < 1 or args.tolerance < 0 or not 0.0 < args.quantile < 1.0:
        parser.error("windows must be positive; tolerance must be non-negative; quantile must be between 0 and 1")

    source = load_json(args.input.resolve())
    mapping = source.get("mapping", {})
    tool_ids = sorted(set(mapping.values()))
    sessions = [
        analyze_session(session, windows, args.quantile, args.tolerance, tool_ids)
        for session in source.get("trajectories", [])
    ]
    all_stable = [boundary for session in sessions for boundary in session["stable_boundaries"]]
    output = {
        "method": {
            "windows": windows,
            "quantile": args.quantile,
            "matching_tolerance_calls": args.tolerance,
            "definition": "a stable boundary is a local JS-divergence peak that recurs near the same call index across multiple windows",
            "confidence_classes": {
                "single_window": "appears at only one window",
                "multi_window": "appears at least two windows",
                "all_windows": "appears at every configured window",
            },
        },
        "session_count": len(sessions),
        "total_stable_clusters": len(all_stable),
        "total_multi_window_boundaries": sum(item["recurrence"] >= 2 for item in all_stable),
        "total_all_window_boundaries": sum(item["recurrence"] == len(windows) for item in all_stable),
        "sessions": sessions,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sessions={len(sessions)}")
    print(f"stable_clusters={len(all_stable)}")
    print(f"multi_window_boundaries={output['total_multi_window_boundaries']}")
    print(f"all_window_boundaries={output['total_all_window_boundaries']}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
