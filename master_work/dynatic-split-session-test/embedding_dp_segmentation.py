"""Segment embedding trajectories with candidate peaks and global DP.

The input candidates come from find_persistent_embedding_peaks.py. This first
version keeps the algorithm label-free: it minimizes within-segment semantic
dispersion, penalizes extra segments, and rewards high-confidence candidates.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from plot_embedding_change_scores import load_sessions


ROOT = Path(__file__).parent
DEFAULT_INPUT = ROOT / "message-embeddings.jsonl"
DEFAULT_CANDIDATES = ROOT / "persistent-embedding-peaks-strict" / "persistent-peaks.json"
DEFAULT_OUTPUT = ROOT / "embedding-dp-segments"


def normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-8)


def segment_cost(prefix: np.ndarray, start: int, end: int) -> float:
    """Dispersion cost for 1-based half-open event range [start+1, end]."""
    total = prefix[end] - prefix[start]
    length = end - start
    return float(length - np.linalg.norm(total))


def candidate_positions(
    peaks: list[dict[str, Any]],
    event_count: int,
    min_segment: int,
) -> list[dict[str, Any]]:
    usable = [
        peak
        for peak in peaks
        if min_segment <= int(peak["event_index"]) <= event_count - min_segment
    ]
    return sorted(usable, key=lambda peak: int(peak["event_index"]))


def solve_dp(
    vectors: np.ndarray,
    peaks: list[dict[str, Any]],
    penalty: float,
    boundary_reward: float,
    min_segment: int,
) -> tuple[list[dict[str, Any]], float]:
    vectors = normalize(vectors)
    prefix = np.vstack([np.zeros((1, vectors.shape[1]), dtype=np.float32), np.cumsum(vectors, axis=0)])
    usable = candidate_positions(peaks, len(vectors), min_segment)
    points = [0] + [int(peak["event_index"]) for peak in usable] + [len(vectors)]
    point_peaks: list[dict[str, Any] | None] = [None] + usable + [None]
    count = len(points)
    infinity = float("inf")
    dp = [infinity] * count
    previous = [-1] * count
    dp[0] = 0.0

    for current in range(1, count):
        for prior in range(current):
            if points[current] - points[prior] < min_segment:
                continue
            value = dp[prior] + segment_cost(prefix, points[prior], points[current])
            if current < count - 1:
                peak = point_peaks[current]
                assert peak is not None
                value += penalty - boundary_reward * float(peak["score"])
            if value < dp[current]:
                dp[current] = value
                previous[current] = prior

    if previous[-1] < 0:
        return [{"core_start": 1, "core_end": len(vectors), "boundary_before": None}], dp[-1]

    selected_indexes: list[int] = []
    index = count - 1
    while index > 0:
        selected_indexes.append(index)
        index = previous[index]
    selected_indexes.reverse()
    boundaries = [points[index] for index in selected_indexes[:-1]]

    segments: list[dict[str, Any]] = []
    core_start = 1
    for boundary in boundaries + [len(vectors)]:
        peak = next((item for item in usable if int(item["event_index"]) == boundary), None)
        segments.append(
            {
                "core_start": core_start,
                "core_end": boundary,
                "boundary_after": peak,
            }
        )
        core_start = boundary + 1
    return segments, float(dp[-1])


def materialize(segments: list[dict[str, Any]], event_count: int, overlap: int) -> None:
    for index, segment in enumerate(segments):
        segment["materialized_start"] = max(1, segment["core_start"] - (overlap if index else 0))
        segment["materialized_end"] = min(
            event_count,
            segment["core_end"] + (overlap if index < len(segments) - 1 else 0),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--penalty", type=float, default=10.0)
    parser.add_argument("--boundary-reward", type=float, default=1.0)
    parser.add_argument("--min-segment", type=int, default=30)
    parser.add_argument("--overlap", type=int, default=25)
    args = parser.parse_args()

    sessions = load_sessions(args.input)
    candidate_data = json.loads(args.candidates.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict[str, Any]] = {}
    total_segments = 0
    total_boundaries = 0
    for session_id, (_rows, vectors) in sorted(sessions.items()):
        peaks = candidate_data["sessions"].get(session_id, {}).get("peaks", [])
        segments, objective = solve_dp(vectors, peaks, args.penalty, args.boundary_reward, args.min_segment)
        materialize(segments, len(vectors), args.overlap)
        total_segments += len(segments)
        total_boundaries += max(0, len(segments) - 1)
        result[session_id] = {
            "event_count": len(vectors),
            "segments": segments,
            "objective": objective,
        }

    payload = {
        "method": "candidate-peak constrained global dynamic programming",
        "input": str(args.input),
        "candidates": str(args.candidates),
        "penalty": args.penalty,
        "boundary_reward": args.boundary_reward,
        "min_segment": args.min_segment,
        "overlap": args.overlap,
        "session_count": len(result),
        "total_segments": total_segments,
        "total_boundaries": total_boundaries,
        "sessions": result,
    }
    output_path = args.output_dir / "embedding-dp-segments.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sessions: {len(result)}")
    print(f"segments: {total_segments}")
    print(f"boundaries: {total_boundaries}")
    print(f"output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
