"""Write readable raw-event slices from embedding-DP segment boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
DEFAULT_RAW = ROOT / "message-trajectories.json"
DEFAULT_SEGMENTS = ROOT / "embedding-dp-penalty-3" / "embedding-dp-segments.json"
DEFAULT_OUTPUT = ROOT / "embedding-dp-penalty-3" / "sliced-sessions"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    segment_data = json.loads(args.segments.read_text(encoding="utf-8"))
    trajectories = {item["session_id"]: item for item in raw["trajectories"]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {
        "method": segment_data["method"],
        "source_segments": str(args.segments),
        "session_count": 0,
        "total_segments": 0,
        "sessions": {},
    }

    for session_id, result in segment_data["sessions"].items():
        trajectory = trajectories[session_id]
        events = trajectory["events"]
        session_dir = args.output_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        output_segments = []
        for segment_index, segment in enumerate(result["segments"], start=1):
            core_start = segment["core_start"]
            core_end = segment["core_end"]
            materialized_start = segment["materialized_start"]
            materialized_end = segment["materialized_end"]
            record = {
                "harness": trajectory.get("harness"),
                "session_id": session_id,
                "segment_index": segment_index,
                "core_start": core_start,
                "core_end": core_end,
                "materialized_start": materialized_start,
                "materialized_end": materialized_end,
                "core_event_count": core_end - core_start + 1,
                "materialized_event_count": materialized_end - materialized_start + 1,
                "boundary_after": segment.get("boundary_after"),
                "events": events[materialized_start - 1 : materialized_end],
            }
            filename = session_dir / f"segment-{segment_index:02d}.json"
            filename.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output_segments.append(
                {
                    key: record[key]
                    for key in (
                        "segment_index",
                        "core_start",
                        "core_end",
                        "materialized_start",
                        "materialized_end",
                        "core_event_count",
                        "materialized_event_count",
                    )
                }
            )
        index["sessions"][session_id] = {
            "event_count": len(events),
            "segment_count": len(output_segments),
            "segments": output_segments,
        }
        index["session_count"] += 1
        index["total_segments"] += len(output_segments)

    (args.output_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sessions: {index['session_count']}")
    print(f"segments: {index['total_segments']}")
    print(f"output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
