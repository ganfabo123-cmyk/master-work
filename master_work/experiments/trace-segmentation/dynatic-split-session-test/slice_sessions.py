#!/usr/bin/env python3
"""Materialize strict and relaxed session slices from stable boundaries."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def entropy(counts: Counter[str], total: int) -> float:
    if not total:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def switch_rate(names: list[str]) -> float:
    return sum(a != b for a, b in zip(names, names[1:])) / max(1, len(names) - 1)


def select_boundaries(clusters: list[dict], minimum_gap: int, minimum_recurrence: int) -> list[int]:
    candidates = [item for item in clusters if item["recurrence"] >= minimum_recurrence]
    selected: list[dict] = []
    for item in sorted(candidates, key=lambda value: (value["recurrence"], value["max_js_divergence"]), reverse=True):
        position = item["representative_boundary_after_call"]
        if all(abs(position - other["representative_boundary_after_call"]) >= minimum_gap for other in selected):
            selected.append(item)
    return sorted(item["representative_boundary_after_call"] for item in selected)


def summarize_slice(calls: list[dict], start: int, end: int, index: int) -> dict:
    names = [call.get("tool_name", "unknown") for call in calls[start:end]]
    counts = Counter(names)
    return {
        "segment_index": index,
        "start_call": start + 1,
        "end_call": end,
        "length": len(names),
        "dominant_tool": counts.most_common(1)[0][0] if counts else None,
        "tool_counts": dict(counts.most_common()),
        "tool_entropy": entropy(counts, len(names)),
        "switch_rate": switch_rate(names),
    }


def plot_slices(session: dict, boundaries: list[int], mapping: dict[str, float], output: Path, label: str) -> None:
    calls = session.get("tool_calls", [])
    values = [mapping.get(call.get("tool_name"), 0.0) for call in calls]
    figure, axis = plt.subplots(figsize=(15, 4.5), constrained_layout=True)
    if values:
        axis.step(range(1, len(values) + 1), values, where="mid", linewidth=0.8)
        axis.set_ylim(min(mapping.values()) - 0.05, max(mapping.values()) + 0.05)
        axis.set_yticks(sorted(set(mapping.values())))
        axis.set_yticklabels([name for name, _ in sorted(mapping.items(), key=lambda item: item[1])], fontsize=8)
        for index, boundary in enumerate(boundaries, start=1):
            axis.axvline(boundary + 0.5, linestyle="--", linewidth=1.0, alpha=0.75)
            axis.text(boundary + 1, max(values), str(index), fontsize=8, va="top")
        axis.set_xlabel("Tool-call index")
        axis.set_ylabel("Tool ID")
    else:
        axis.text(0.5, 0.5, "No tool calls", ha="center", va="center", transform=axis.transAxes)
    axis.grid(axis="y", alpha=0.25)
    axis.set_title(f"{label}: materialized slices")
    figure.savefig(output, dpi=150)
    plt.close(figure)


def materialize_sessions(report: dict, stability: dict, trajectories: dict, output_root: Path, mapping: dict[str, float], mode: str, minimum_recurrence: int, minimum_gap: int) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    plot_dir = output_root / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    stability_by_key = {(item["harness"], item["session_id"]): item for item in stability["sessions"]}
    trajectory_by_key = {(item["harness"], item["session_id"]): item for item in trajectories["trajectories"]}
    session_outputs = []

    for session in report["sessions"]:
        key = (session["harness"], session["session_id"])
        stable = stability_by_key[key]
        boundaries = select_boundaries(stable["stable_boundaries"], minimum_gap, minimum_recurrence)
        calls = session.get("tool_calls", [])
        starts = [0, *boundaries]
        ends = [*boundaries, len(calls)]
        slices = []
        for index, (start, end) in enumerate(zip(starts, ends), start=1):
            summary = summarize_slice(calls, start, end, index)
            slice_record = {
                "harness": session["harness"],
                "session_id": session["session_id"],
                "source_file": session["source_file"],
                "mode": mode,
                "boundary_before_segment": boundaries[index - 2] if index > 1 else None,
                "boundary_after_segment": boundaries[index - 1] if index <= len(boundaries) else None,
                **summary,
                "tool_calls": calls[start:end],
            }
            filename = f"{session['harness']}__{session['session_id']}__segment-{index:02d}.json"
            (output_root / filename).write_text(json.dumps(slice_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            slices.append({key: value for key, value in summary.items()})

        trajectory = trajectory_by_key[key]
        plot_name = f"{session['harness']}__{session['session_id']}.png"
        plot_slices(session, boundaries, mapping, plot_dir / plot_name, f"{session['harness']} / {session['session_id']} / {mode}")
        session_outputs.append({
            "harness": session["harness"],
            "session_id": session["session_id"],
            "tool_call_count": len(calls),
            "boundary_after_calls": boundaries,
            "segment_count": len(slices),
            "segments": slices,
            "plot_file": str(Path("plots") / plot_name),
        })

    output = {
        "mode": mode,
        "minimum_recurrence": minimum_recurrence,
        "minimum_gap": minimum_gap,
        "session_count": len(session_outputs),
        "total_segments": sum(item["segment_count"] for item in session_outputs),
        "sessions": session_outputs,
    }
    (output_root / "index.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--report", type=Path, default=base / "toolcall-report.json")
    parser.add_argument("--stability", type=Path, default=base / "boundary-stability.json")
    parser.add_argument("--trajectories", type=Path, default=base / "session-trajectories.json")
    parser.add_argument("--output-root", type=Path, default=base / "sliced-sessions")
    parser.add_argument("--minimum-gap", type=int, default=10)
    args = parser.parse_args()
    if args.minimum_gap < 1:
        parser.error("minimum-gap must be positive")

    report = load_json(args.report.resolve())
    stability = load_json(args.stability.resolve())
    trajectories = load_json(args.trajectories.resolve())
    mapping = trajectories.get("mapping", {})
    strict = materialize_sessions(report, stability, trajectories, args.output_root.resolve() / "strict-all-windows", mapping, "strict-all-windows", 3, args.minimum_gap)
    relaxed = materialize_sessions(report, stability, trajectories, args.output_root.resolve() / "relaxed-multi-window", mapping, "relaxed-multi-window", 2, args.minimum_gap)
    summary = {
        "strict_all_windows": {key: strict[key] for key in ("session_count", "total_segments", "minimum_gap")},
        "relaxed_multi_window": {key: relaxed[key] for key in ("session_count", "total_segments", "minimum_gap")},
    }
    (args.output_root.resolve() / "comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
