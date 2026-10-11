#!/usr/bin/env python3
"""Create exploratory smoothed plots and statistics for tool trajectories."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median, pstdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def rolling(values: list[float], window: int) -> tuple[list[float], list[float]]:
    means: list[float] = []
    deviations: list[float] = []
    radius = window // 2
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        sample = values[start:end]
        means.append(mean(sample))
        deviations.append(pstdev(sample) if len(sample) > 1 else 0.0)
    return means, deviations


def rolling_discrete(values: list[int], window: int, metric: str) -> list[float]:
    result: list[float] = []
    radius = window // 2
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        sample = values[start:end]
        if metric == "switch_rate":
            result.append(sum(a != b for a, b in zip(sample, sample[1:])) / max(1, len(sample) - 1))
        elif metric == "entropy":
            counts = Counter(sample)
            total = len(sample)
            entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
            result.append(entropy)
        else:
            raise ValueError(metric)
    return result


def run_lengths(values: list[int]) -> list[int]:
    if not values:
        return []
    runs: list[int] = []
    current = 1
    for previous, value in zip(values, values[1:]):
        if value == previous:
            current += 1
        else:
            runs.append(current)
            current = 1
    runs.append(current)
    return runs


def plot_session(session: dict, mapping: dict[str, int], output_dir: Path, window: int) -> dict:
    values = list(session.get("trajectory", []))
    names = list(session.get("tool_names", []))
    label = f"{session.get('harness', 'unknown')} / {session.get('session_id', 'unknown')}"
    figure, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True, constrained_layout=True)

    if values:
        x_values = list(range(1, len(values) + 1))
        mean_values, std_values = rolling(values, window)
        switch_values = rolling_discrete(values, window, "switch_rate")
        entropy_values = rolling_discrete(values, window, "entropy")

        axes[0].plot(x_values, values, linewidth=0.6, alpha=0.25, label="raw tool ID")
        axes[0].plot(x_values, mean_values, linewidth=1.5, label=f"rolling mean (w={window})")
        extrema_x = []
        extrema_y = []
        for index in range(1, len(values) - 1):
            before = values[index] - values[index - 1]
            after = values[index + 1] - values[index]
            if before * after < 0:
                extrema_x.append(index + 1)
                extrema_y.append(values[index])
        axes[0].scatter(extrema_x, extrema_y, s=18, zorder=3, label="raw local extrema")
        lower = [value - deviation for value, deviation in zip(mean_values, std_values)]
        upper = [value + deviation for value, deviation in zip(mean_values, std_values)]
        axes[0].fill_between(x_values, lower, upper, alpha=0.18, label="rolling ±1 std")
        axes[0].set_ylabel("Tool ID")
        axes[0].set_ylim(min(mapping.values()) - 0.05, max(mapping.values()) + 0.05)
        axes[0].set_yticks(list(mapping.values()))
        axes[0].set_yticklabels([name for name, _ in sorted(mapping.items(), key=lambda item: item[1])], fontsize=8)
        axes[0].legend(loc="upper right")

        axes[1].plot(x_values, switch_values, linewidth=1.1)
        axes[1].set_ylabel("Switch rate")
        axes[1].set_ylim(-0.02, 1.02)

        axes[2].plot(x_values, entropy_values, linewidth=1.1)
        axes[2].set_ylabel("Entropy")
        axes[2].set_xlabel("Tool-call index")
    else:
        for axis in axes:
            axis.text(0.5, 0.5, "No tool calls", ha="center", va="center", transform=axis.transAxes)
        axes[2].set_xlabel("Tool-call index")

    for axis in axes:
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle(f"Smoothed tool trajectory: {label}")
    filename = f"{session.get('harness', 'unknown')}__{session.get('session_id', 'unknown')}.png"
    figure.savefig(output_dir / filename, dpi=150)
    plt.close(figure)

    runs = run_lengths(values)
    transitions = Counter(zip(values, values[1:]))
    return {
        "harness": session.get("harness"),
        "session_id": session.get("session_id"),
        "tool_call_count": len(values),
        "unique_tool_count": len(set(values)),
        "switch_count": sum(a != b for a, b in zip(values, values[1:])),
        "switch_rate": sum(a != b for a, b in zip(values, values[1:])) / max(1, len(values) - 1),
        "mean_run_length": mean(runs) if runs else 0.0,
        "median_run_length": median(runs) if runs else 0.0,
        "max_run_length": max(runs) if runs else 0,
        "tool_entropy": -sum(
            (count / len(values)) * math.log(count / len(values))
            for count in Counter(values).values()
        ) if values else 0.0,
        "top_transitions": [
            {"from_id": source, "to_id": target, "count": count}
            for (source, target), count in transitions.most_common(10)
        ],
        "tool_names": names,
        "trajectory": values,
        "plot_file": filename,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().with_name("session-trajectories.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().with_name("smoothed-trajectory-plots"),
    )
    parser.add_argument(
        "--statistics-output",
        type=Path,
        default=Path(__file__).resolve().with_name("trajectory-statistics.json"),
    )
    parser.add_argument("--window", type=int, default=9, help="Odd rolling window size (default: 9)")
    args = parser.parse_args()

    if args.window < 1 or args.window % 2 == 0:
        parser.error("--window must be a positive odd integer")

    source = load_json(args.input.resolve())
    mapping = source.get("mapping", {})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = [plot_session(session, mapping, args.output_dir, args.window) for session in source.get("trajectories", [])]

    tool_counts = Counter(name for item in metrics for name in item["tool_names"])
    transition_counts: Counter[tuple[int, int]] = Counter()
    for item in metrics:
        transition_counts.update(zip(item["trajectory"], item["trajectory"][1:]))

    output = {
        "mapping": mapping,
        "window": args.window,
        "session_count": len(metrics),
        "global": {
            "tool_call_count": sum(item["tool_call_count"] for item in metrics),
            "switch_count": sum(item["switch_count"] for item in metrics),
            "switch_rate": sum(item["switch_count"] for item in metrics) / max(
                1,
                sum(max(0, item["tool_call_count"] - 1) for item in metrics),
            ),
            "tool_counts": dict(tool_counts.most_common()),
            "top_transitions": [
                {"from_id": source_id, "to_id": target_id, "count": count}
                for (source_id, target_id), count in transition_counts.most_common(25)
            ],
        },
        "sessions": metrics,
    }
    args.statistics_output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"window={args.window}")
    print(f"sessions={len(metrics)}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"statistics={args.statistics_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
