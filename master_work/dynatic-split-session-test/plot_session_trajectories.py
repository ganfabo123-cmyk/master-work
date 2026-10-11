#!/usr/bin/env python3
"""Map tool names to integers and plot every session as a tool trajectory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_report(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_tool_mapping(report: dict) -> dict[str, float]:
    names = {
        call["tool_name"]
        for session in report.get("sessions", [])
        for call in session.get("tool_calls", [])
        if call.get("tool_name")
    }
    # Keep the user's requested anchor stable, then use lexical order so the
    # remaining IDs are deterministic across repeated scans.
    ordered = ["Edit"] if "Edit" in names else []
    ordered.extend(sorted(names - {"Edit"}))
    return {name: round(1.0 + index * 0.1, 1) for index, name in enumerate(ordered)}


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "session"


def plot_session(session: dict, mapping: dict[str, int], output_dir: Path) -> dict:
    calls = [call for call in session.get("tool_calls", []) if call.get("tool_name")]
    values = [mapping[call["tool_name"]] for call in calls]
    session_label = f"{session.get('harness', 'unknown')} / {session.get('session_id', 'unknown')}"

    figure, axis = plt.subplots(figsize=(15, 5.5), constrained_layout=True)
    if values:
        x_values = list(range(1, len(values) + 1))
        axis.step(x_values, values, where="mid", linewidth=0.9, alpha=0.75)
        axis.scatter(x_values, values, s=9, alpha=0.7)
        axis.set_xlim(1, len(values))
        axis.set_ylim(min(mapping.values()) - 0.05, max(mapping.values()) + 0.05)
        axis.set_xticks([1, *range(10, len(values) + 1, 10)])
        axis.set_yticks(list(mapping.values()))
        axis.set_yticklabels([name for name, _ in sorted(mapping.items(), key=lambda item: item[1])])
    else:
        axis.text(0.5, 0.5, "No tool calls", ha="center", va="center", transform=axis.transAxes)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)

    axis.set_title(f"Tool trajectory: {session_label}")
    axis.set_xlabel("Tool-call index")
    axis.set_ylabel("Tool ID")
    axis.grid(axis="y", alpha=0.25)

    filename = safe_filename(f"{session.get('harness', 'unknown')}__{session.get('session_id', 'unknown')}.png")
    figure.savefig(output_dir / filename, dpi=150)
    plt.close(figure)

    return {
        "harness": session.get("harness"),
        "session_id": session.get("session_id"),
        "tool_call_count": len(values),
        "trajectory": values,
        "tool_names": [call["tool_name"] for call in calls],
        "plot_file": filename,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().with_name("toolcall-report.json"),
        help="JSON report produced by scan_toolcalls.py",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().with_name("trajectory-plots"),
        help="Directory for PNG plots",
    )
    parser.add_argument(
        "--mapping-output",
        type=Path,
        default=Path(__file__).resolve().with_name("tool-vector-map.json"),
        help="JSON file for the tool-to-integer mapping",
    )
    parser.add_argument(
        "--trajectory-output",
        type=Path,
        default=Path(__file__).resolve().with_name("session-trajectories.json"),
        help="JSON file for the integer trajectories",
    )
    args = parser.parse_args()

    report = load_report(args.report.resolve())
    mapping = build_tool_mapping(report)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trajectories = [
        plot_session(session, mapping, args.output_dir)
        for session in report.get("sessions", [])
    ]
    args.mapping_output.write_text(
        json.dumps(
            {"anchor": {"tool": "Edit", "id": 1}, "mapping": mapping},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    args.trajectory_output.write_text(
        json.dumps(
            {
                "mapping": mapping,
                "session_count": len(trajectories),
                "trajectories": trajectories,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"tool_types={len(mapping)}")
    print(f"sessions={len(trajectories)}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"mapping={args.mapping_output.resolve()}")
    print(f"trajectories={args.trajectory_output.resolve()}")
    print(f"plots_dir={args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
