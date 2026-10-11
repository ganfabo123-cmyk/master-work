#!/usr/bin/env python3
"""Expand tool-based slices with surrounding ordinary trace messages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def text_from_part(part: dict) -> str:
    value = part.get("text")
    return value if isinstance(value, str) else ""


def parse_jsonl_trace(path: Path, report_session: dict) -> list[dict]:
    events: list[dict] = []
    call_index = 0
    report_calls = report_session.get("tool_calls", [])
    for event_index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message", {})
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, list):
            continue
        for part_index, part in enumerate(content):
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and text_from_part(part).strip():
                events.append({
                    "kind": "text",
                    "role": role,
                    "text_type": "text",
                    "text": text_from_part(part),
                    "source_event_index": event_index,
                    "source_part_index": part_index,
                })
            elif role == "assistant" and part.get("type") == "tool_use":
                call_index += 1
                call = report_calls[call_index - 1] if call_index <= len(report_calls) else {
                    "tool_name": part.get("name"),
                    "actual_arguments": part.get("input"),
                }
                events.append({
                    "kind": "tool_call",
                    "role": role,
                    "call_index": call_index,
                    "tool_call": call,
                    "source_event_index": event_index,
                    "source_part_index": part_index,
                })
    return events


def parse_opencode_trace(path: Path, report_session: dict) -> list[dict]:
    data = load_json(path)
    events: list[dict] = []
    call_index = 0
    report_calls = report_session.get("tool_calls", [])
    for message_index, message in enumerate(data.get("messages", [])):
        role = message.get("info", {}).get("role")
        for part_index, part in enumerate(message.get("parts", [])):
            part_type = part.get("type")
            if part_type in {"text", "reasoning"} and text_from_part(part).strip():
                events.append({
                    "kind": "text",
                    "role": role,
                    "text_type": part_type,
                    "text": text_from_part(part),
                    "source_message_index": message_index,
                    "source_part_index": part_index,
                })
            elif role == "assistant" and part_type == "tool":
                call_index += 1
                call = report_calls[call_index - 1] if call_index <= len(report_calls) else {
                    "tool_name": part.get("tool"),
                    "actual_arguments": part.get("state", {}).get("input"),
                }
                events.append({
                    "kind": "tool_call",
                    "role": role,
                    "call_index": call_index,
                    "tool_call": call,
                    "source_message_index": message_index,
                    "source_part_index": part_index,
                })
    return events


def parse_trace(root: Path, report_session: dict) -> list[dict]:
    path = root / report_session["source_file"]
    if path.suffix == ".jsonl":
        return parse_jsonl_trace(path, report_session)
    if path.suffix == ".json":
        return parse_opencode_trace(path, report_session)
    return []


def text_context_start(events: list[dict], first_tool_position: int) -> int:
    for position in range(first_tool_position - 1, -1, -1):
        if events[position]["kind"] == "text":
            return position
    return first_tool_position


def text_context_end(events: list[dict], last_tool_position: int) -> int:
    for position in range(last_tool_position + 1, len(events)):
        if events[position]["kind"] == "text":
            return position
    return last_tool_position


def expand_interval(events: list[dict], first_call: int, last_call: int) -> tuple[int, int]:
    tool_positions = [
        index for index, event in enumerate(events)
        if event.get("kind") == "tool_call" and first_call <= event.get("call_index", -1) <= last_call
    ]
    if not tool_positions:
        return (0, len(events) - 1)
    return text_context_start(events, tool_positions[0]), text_context_end(events, tool_positions[-1])


def compact_event(event: dict) -> dict:
    if event["kind"] == "text":
        return {key: event[key] for key in ("kind", "role", "text_type", "text", "source_event_index", "source_part_index") if key in event}
    return {key: event[key] for key in ("kind", "role", "call_index", "tool_call", "source_event_index", "source_part_index") if key in event}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--report", type=Path, default=base / "toolcall-report.json")
    parser.add_argument("--boundaries", type=Path, default=base / "sliced-sessions" / "strict-all-windows" / "index.json")
    parser.add_argument("--output", type=Path, default=base / "context-expanded-sessions")
    args = parser.parse_args()

    report = load_json(args.report.resolve())
    boundary_index = load_json(args.boundaries.resolve())
    report_by_key = {(item["harness"], item["session_id"]): item for item in report["sessions"]}
    args.output.mkdir(parents=True, exist_ok=True)
    session_summaries = []

    for slice_session in boundary_index["sessions"]:
        key = (slice_session["harness"], slice_session["session_id"])
        report_session = report_by_key[key]
        events = parse_trace(Path("../agent-traces/sessions").resolve(), report_session)
        boundaries = slice_session["boundary_after_calls"]
        total_calls = report_session["tool_call_count"]
        starts = [1, *[boundary + 1 for boundary in boundaries]]
        ends = [*boundaries, total_calls]
        slices = []
        for segment_index, (first_call, last_call) in enumerate(zip(starts, ends), start=1):
            event_start, event_end = expand_interval(events, first_call, last_call)
            selected_events = [compact_event(event) for event in events[event_start:event_end + 1]] if events else []
            text_events = [event for event in selected_events if event["kind"] == "text"]
            tool_events = [event for event in selected_events if event["kind"] == "tool_call"]
            slice_record = {
                "harness": slice_session["harness"],
                "session_id": slice_session["session_id"],
                "source_file": report_session["source_file"],
                "segment_index": segment_index,
                "anchor_call_range": {"first_call": first_call, "last_call": last_call},
                "expanded_event_range": {"first_event": event_start, "last_event": event_end},
                "expanded_by_text": bool(text_events),
                "text_event_count": len(text_events),
                "tool_call_count": len(tool_events),
                "events": selected_events,
            }
            filename = f"{slice_session['harness']}__{slice_session['session_id']}__segment-{segment_index:02d}.json"
            (args.output / filename).write_text(json.dumps(slice_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            slices.append({
                "segment_index": segment_index,
                "anchor_call_range": slice_record["anchor_call_range"],
                "expanded_event_range": slice_record["expanded_event_range"],
                "text_event_count": len(text_events),
                "tool_call_count": len(tool_events),
                "first_text": text_events[0]["text"][:180] if text_events else None,
                "last_text": text_events[-1]["text"][:180] if text_events else None,
            })
        session_summaries.append({
            "harness": slice_session["harness"],
            "session_id": slice_session["session_id"],
            "segment_count": len(slices),
            "segments": slices,
        })

    output = {
        "method": {
            "anchor_boundaries": "strict-all-windows boundaries",
            "start_rule": "include the contiguous text block immediately before the first anchor tool call",
            "end_rule": "include the contiguous text block immediately after the last anchor tool call",
            "overlap_semantics": "neighboring slices may share boundary-adjacent text context",
            "text_types": ["text", "reasoning"],
        },
        "session_count": len(session_summaries),
        "total_segments": sum(item["segment_count"] for item in session_summaries),
        "total_text_events": sum(segment["text_event_count"] for session in session_summaries for segment in session["segments"]),
        "sessions": session_summaries,
    }
    (args.output / "index.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: output[key] for key in ("session_count", "total_segments", "total_text_events")}, ensure_ascii=False))
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
