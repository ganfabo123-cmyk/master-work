#!/usr/bin/env python3
"""Build a human-review boundary annotation set from existing segmenters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def event_preview(event: dict, limit: int = 500) -> dict:
    text = event.get("text", "") or ""
    return {
        "category": event.get("category"),
        "text": text[:limit],
        "tool_name": event.get("tool_name"),
        "event_index": event.get("event_index"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--trajectories", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--best-first", type=Path, required=True)
    parser.add_argument("--recall-first", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-events", type=int, default=8)
    args = parser.parse_args()

    source = load(args.trajectories)
    best = load(args.best_first)
    recall = load(args.recall_first)
    source_by_id = {(x["harness"], x["session_id"]): x for x in source["trajectories"]}
    boundaries = {}
    for algorithm, data in (("best_first", best), ("recall_first", recall)):
        for session in data["sessions"]:
            key = (session["harness"], session["session_id"])
            boundaries.setdefault(key, {})
            for position in session["boundaries_after_event"]:
                boundaries[key].setdefault(position, set()).add(algorithm)

    items = []
    for key in sorted(boundaries):
        source_session = source_by_id[key]
        events = source_session["events"]
        for position in sorted(boundaries[key]):
            left = max(0, position - args.context_events)
            right = min(len(events), position + args.context_events)
            items.append({
                "annotation_id": f"{key[0]}:{key[1]}:{position}",
                "harness": key[0],
                "session_id": key[1],
                "boundary_after_event": position,
                "source_algorithms": sorted(boundaries[key][position]),
                "left_context": [event_preview(event) for event in events[left:position]],
                "right_context": [event_preview(event) for event in events[position:right]],
                "label": None,
                "move_to_event": None,
                "reason": None,
            })
    output = {
        "schema_version": "boundary-review-v1",
        "label_definitions": {
            "keep": "The boundary separates two understandable task units.",
            "move": "The boundary is near a real task boundary but should move; set move_to_event.",
            "remove": "The two sides are one continuous task or the boundary is noise.",
        },
        "annotation_note": "Labels require direct review of the stored context and should not be inferred from algorithm membership.",
        "candidate_count": len(items),
        "items": items,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidates={len(items)}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
