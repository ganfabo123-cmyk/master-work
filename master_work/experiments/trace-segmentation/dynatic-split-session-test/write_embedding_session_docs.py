"""Write complete Markdown records for embedding-DP sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
DEFAULT_RAW = ROOT / "message-trajectories.json"
DEFAULT_SEGMENTS = ROOT / "embedding-dp-penalty-3" / "embedding-dp-segments.json"
DEFAULT_OUTPUT = ROOT / "embedding-dp-penalty-3" / "session-documents"


def short_text(value: Any, limit: int = 160) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def event_body(event: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in event.items()
        if key not in {"source_index", "source_part_index"}
    }
    if "text" in payload:
        return str(payload.pop("text"))
    return json.dumps(payload, ensure_ascii=False, indent=2)


def segment_for_event(segments: list[dict], event_index: int) -> tuple[int | None, str | None]:
    for segment in segments:
        if segment["core_start"] <= event_index <= segment["core_end"]:
            return segment["segment_index"], "core"
        if segment["materialized_start"] <= event_index <= segment["materialized_end"]:
            return segment["segment_index"], "context"
    return None, None


def build_document(trajectory: dict, segment_data: dict) -> str:
    session_id = trajectory["session_id"]
    events = trajectory["events"]
    segments = []
    for index, segment in enumerate(segment_data["segments"], start=1):
        segments.append(
            {
                **segment,
                "segment_index": index,
                "core_event_count": segment["core_end"] - segment["core_start"] + 1,
                "materialized_event_count": segment["materialized_end"] - segment["materialized_start"] + 1,
            }
        )
    lines = [
        f"# Session `{session_id}`",
        "",
        f"- Harness: `{trajectory.get('harness', '')}`",
        f"- Event count: {len(events)}",
        f"- Segment count: {len(segments)}",
        "- This document preserves the complete raw event sequence; JSON slices remain the machine-readable source.",
        "",
        "## Segment map",
        "",
        "| Segment | Core range | Materialized range | Core events | Materialized events |",
        "|---:|---:|---:|---:|---:|",
    ]
    for segment in segments:
        lines.append(
            f"| {segment['segment_index']} | {segment['core_start']}-{segment['core_end']} | "
            f"{segment['materialized_start']}-{segment['materialized_end']} | "
            f"{segment['core_event_count']} | {segment['materialized_event_count']} |"
        )
    lines.extend(["", "## Complete event record", ""])

    starts = {segment["core_start"]: segment for segment in segments}
    for event_number, event in enumerate(events, start=1):
        if event_number in starts:
            segment = starts[event_number]
            lines.extend(
                [
                    f"## Segment {segment['segment_index']} · core starts at event {event_number}",
                    "",
                    f"Core range: `{segment['core_start']}-{segment['core_end']}`; "
                    f"materialized range: `{segment['materialized_start']}-{segment['materialized_end']}`.",
                    "",
                ]
            )
        category = event.get("category", "unknown")
        role = event.get("role", "")
        tool_name = event.get("tool_name", "")
        label = " / ".join(str(item) for item in (category, role, tool_name) if item)
        segment_index, scope = segment_for_event(segments, event_number)
        scope_label = f"; segment={segment_index}, scope={scope}" if segment_index else ""
        lines.extend(
            [
                f"### Event {event_number}: `{label}`{scope_label}",
                "",
                "```text",
                event_body(event),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    segments = json.loads(args.segments.read_text(encoding="utf-8"))
    trajectories = {item["session_id"]: item for item in raw["trajectories"]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index_lines = [
        "# Embedding-DP session documents",
        "",
        f"- Session count: {len(trajectories)}",
        f"- Segmentation result: `{args.segments}`",
        "- Each linked Markdown file preserves the complete event sequence and marks core/materialized ranges.",
        "",
        "| Session | Events | Segments | Document |",
        "|---|---:|---:|---|",
    ]
    for session_id in sorted(trajectories):
        trajectory = trajectories[session_id]
        session_segments = segments["sessions"][session_id]
        filename = f"{session_id}.md"
        (args.output_dir / filename).write_text(
            build_document(trajectory, session_segments), encoding="utf-8"
        )
        index_lines.append(
            f"| `{session_id}` | {len(trajectory['events'])} | {len(session_segments['segments'])} | [{filename}]({filename}) |"
        )
    (args.output_dir / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"session documents: {len(trajectories)}")
    print(f"output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
