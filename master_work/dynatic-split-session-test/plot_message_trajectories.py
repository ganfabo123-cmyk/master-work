#!/usr/bin/env python3
"""Map every trace message/part category to a numeric trajectory."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "session"


def role_text_category(role: str, part_type: str) -> str:
    if part_type == "text":
        return f"{role}_text"
    if part_type in {"thinking", "reasoning"}:
        return f"{role}_{part_type}"
    if part_type == "image":
        return f"{role}_image"
    return f"{role}_part:{part_type}"


def parse_jsonl(path: Path, report_session: dict) -> list[dict]:
    events = []
    for source_index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), list):
            role = message.get("role", "unknown")
            for part_index, part in enumerate(message["content"]):
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type", "unknown")
                if part_type == "tool_use":
                    category = f"tool_call:{part.get('name', 'unknown')}"
                    detail = {"tool_name": part.get("name"), "arguments": part.get("input")}
                elif part_type == "tool_result":
                    category = "tool_result"
                    detail = {"tool_use_id": part.get("tool_use_id")}
                else:
                    category = role_text_category(role, part_type)
                    detail = {"text": part.get("text")} if isinstance(part.get("text"), str) else {}
                events.append({
                    "category": category,
                    "role": role,
                    "part_type": part_type,
                    "source_index": source_index,
                    "source_part_index": part_index,
                    **detail,
                })
        else:
            record_type = record.get("type")
            if record_type:
                events.append({
                    "category": f"record:{record_type}",
                    "role": "metadata",
                    "part_type": record_type,
                    "source_index": source_index,
                })
    return events


def parse_opencode(path: Path, report_session: dict) -> list[dict]:
    data = load_json(path)
    events = []
    for message_index, message in enumerate(data.get("messages", [])):
        role = message.get("info", {}).get("role", "unknown")
        for part_index, part in enumerate(message.get("parts", [])):
            part_type = part.get("type", "unknown")
            if part_type == "tool":
                category = f"tool_call:{part.get('tool', 'unknown')}"
                detail = {"tool_name": part.get("tool"), "arguments": part.get("state", {}).get("input")}
            else:
                category = role_text_category(role, part_type)
                detail = {"text": part.get("text")} if isinstance(part.get("text"), str) else {}
            events.append({
                "category": category,
                "role": role,
                "part_type": part_type,
                "source_index": message_index,
                "source_part_index": part_index,
                **detail,
            })
    return events


def parse_session(root: Path, report_session: dict) -> list[dict]:
    path = root / report_session["source_file"]
    if path.suffix == ".jsonl":
        return parse_jsonl(path, report_session)
    return parse_opencode(path, report_session)


def build_mapping(events_by_session: list[list[dict]]) -> dict[str, float]:
    categories = {event["category"] for events in events_by_session for event in events}
    preferred = [
        "assistant_text",
        "user_text",
        "assistant_thinking",
        "assistant_reasoning",
        "tool_result",
        "assistant_image",
        "user_image",
    ]
    ordered = [category for category in preferred if category in categories]
    ordered.extend(sorted(categories - set(ordered)))
    return {category: round(1.0 + index * 0.1, 1) for index, category in enumerate(ordered)}


def plot_session(session: dict, events: list[dict], mapping: dict[str, float], output_dir: Path) -> dict:
    values = [mapping[event["category"]] for event in events]
    names = [event["category"] for event in events]
    figure, axis = plt.subplots(figsize=(16, 6), constrained_layout=True)
    if values:
        x_values = list(range(1, len(values) + 1))
        axis.step(x_values, values, where="mid", linewidth=0.75, alpha=0.75)
        axis.scatter(x_values, values, s=5, alpha=0.5)
        axis.set_xlim(1, len(values))
        axis.set_ylim(min(mapping.values()) - 0.05, max(mapping.values()) + 0.05)
        axis.set_yticks(list(mapping.values()))
        axis.set_yticklabels([name for name, _ in sorted(mapping.items(), key=lambda item: item[1])], fontsize=7)
        axis.set_xticks([1, *range(10, len(values) + 1, 10)])
    else:
        axis.text(0.5, 0.5, "No messages", ha="center", va="center", transform=axis.transAxes)
    label = f"{session.get('harness', 'unknown')} / {session.get('session_id', 'unknown')}"
    axis.set_title(f"Full message trajectory: {label}")
    axis.set_xlabel("Message-part/event index")
    axis.set_ylabel("Message category ID")
    axis.grid(axis="y", alpha=0.25)
    filename = safe_filename(f"{session.get('harness', 'unknown')}__{session.get('session_id', 'unknown')}.png")
    figure.savefig(output_dir / filename, dpi=150)
    plt.close(figure)
    return {
        "harness": session.get("harness"),
        "session_id": session.get("session_id"),
        "event_count": len(events),
        "category_counts": dict(Counter(names).most_common()),
        "trajectory": values,
        "message_categories": names,
        "events": events,
        "plot_file": filename,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--report", type=Path, default=base / "toolcall-report.json")
    parser.add_argument("--trace-root", type=Path, default=base.parent / "agent-traces" / "sessions")
    parser.add_argument("--output-dir", type=Path, default=base / "message-trajectory-plots")
    parser.add_argument("--mapping-output", type=Path, default=base / "message-vector-map.json")
    parser.add_argument("--trajectory-output", type=Path, default=base / "message-trajectories.json")
    args = parser.parse_args()

    report = load_json(args.report.resolve())
    parsed = [parse_session(args.trace_root.resolve(), session) for session in report.get("sessions", [])]
    mapping = build_mapping(parsed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trajectories = [plot_session(session, events, mapping, args.output_dir) for session, events in zip(report.get("sessions", []), parsed)]
    args.mapping_output.write_text(json.dumps({"mapping": mapping, "spacing": 0.1}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.trajectory_output.write_text(json.dumps({"mapping": mapping, "session_count": len(trajectories), "trajectories": trajectories}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"message_categories={len(mapping)}")
    print(f"events={sum(item['event_count'] for item in trajectories)}")
    print(f"sessions={len(trajectories)}")
    print(f"plots={len(list(args.output_dir.glob('*.png')))}")
    print(f"mapping={args.mapping_output.resolve()}")
    print(f"trajectories={args.trajectory_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
