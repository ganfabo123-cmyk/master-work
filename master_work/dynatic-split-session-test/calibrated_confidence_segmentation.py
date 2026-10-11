#!/usr/bin/env python3
"""Unsupervised, statistically calibrated confidence-first segmentation.

This is an experimental successor to best_first_confidence_segmentation.py.
It deliberately removes category-to-number distances.  Boundary evidence is
computed from message embeddings, calibrated against the session's own null
distribution, and filtered by Benjamini-Hochberg FDR plus multiscale stability.

The resulting q-values are statistical evidence under the local null model;
they are not a claim that the boundary is semantically correct with probability
1-q.  Human-readable text boundaries remain a structural constraint so that
the completeness-first policy is preserved.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

import frozen_message_segmentation as frozen


def load_embeddings(path: Path) -> dict[str, np.ndarray]:
    grouped: dict[str, list[tuple[int, list[float]]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            grouped.setdefault(row["session_id"], []).append((row["event_index"], row["embedding"]))
    result = {}
    for session_id, rows in grouped.items():
        rows.sort(key=lambda item: item[0])
        vectors = np.asarray([item[1] for item in rows], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        result[session_id] = vectors / np.maximum(norms, 1e-12)
    return result


def robust_location_scale(values: np.ndarray) -> tuple[float, float]:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(1.4826 * mad, 1e-6)


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    order = np.argsort(p_values)
    ordered = p_values[order]
    n = len(ordered)
    adjusted = np.minimum(1.0, ordered * n / np.arange(1, n + 1))
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


def parse_length_bands(spec: str) -> list[tuple[int, float]]:
    """Parse lower-bound:FDR bands, for example 0:0.10,500:0.30,800:0.45."""
    bands = []
    for item in spec.split(","):
        lower, threshold = item.split(":", 1)
        bands.append((int(lower), float(threshold)))
    bands.sort()
    if not bands or bands[0][0] != 0 or any(threshold <= 0 or threshold >= 1 for _, threshold in bands):
        raise ValueError("length bands must start at 0 and use FDR values in (0, 1)")
    if any(left[0] == right[0] for left, right in zip(bands, bands[1:])):
        raise ValueError("length band lower bounds must be unique")
    return bands


def fdr_for_length(interval_length: int, bands: list[tuple[int, float]]) -> float:
    applicable = [threshold for lower, threshold in bands if interval_length >= lower]
    return applicable[-1]


def boundary_evidence(
    events: list[dict],
    vectors: np.ndarray,
    windows: tuple[int, ...],
    min_segment: int,
) -> list[dict]:
    """Compute embedding divergence, null-calibrated p/q, and stability."""
    n = len(events)
    if len(vectors) != n or n < 2 * max(windows) + min_segment:
        return []
    prefix = np.vstack([np.zeros((1, vectors.shape[1]), dtype=np.float32), np.cumsum(vectors, axis=0)])
    positions = list(range(max(windows), n - max(windows) + 1))
    rows = []
    for position in positions:
        by_window = {}
        for window in windows:
            left = prefix[position] - prefix[position - window]
            right = prefix[position + window] - prefix[position]
            left /= max(float(np.linalg.norm(left)), 1e-12)
            right /= max(float(np.linalg.norm(right)), 1e-12)
            by_window[str(window)] = float(np.clip(1.0 - np.dot(left, right), 0.0, 2.0))
        values = np.asarray(list(by_window.values()), dtype=np.float64)
        rows.append({
            "boundary_after_event": position,
            "by_window": by_window,
            "embedding_divergence": float(values.mean()),
            "window_std": float(values.std()),
            "safe_text_boundary": frozen.is_safe_text_boundary(events, position),
        })

    all_scores = np.asarray([row["embedding_divergence"] for row in rows], dtype=np.float64)
    location, scale = robust_location_scale(all_scores)
    z_scores = (all_scores - location) / scale
    p_values = 0.5 * np.vectorize(math.erfc)(z_scores / math.sqrt(2.0))
    q_values = benjamini_hochberg(p_values)

    per_window_z = {}
    for window in windows:
        values = np.asarray([row["by_window"][str(window)] for row in rows], dtype=np.float64)
        window_location, window_scale = robust_location_scale(values)
        per_window_z[window] = (values - window_location) / window_scale

    for index, row in enumerate(rows):
        positive = [float(per_window_z[window][index] >= 1.0) for window in windows]
        stability = float(np.mean(positive))
        # q is the multiple-testing-adjusted tail probability.  Stability is
        # deliberately a multiplier, not another hand-picked event category.
        confidence = (1.0 - float(q_values[index])) * (0.5 + 0.5 * stability)
        row.update({
            "robust_z": float(z_scores[index]),
            "p_value": float(p_values[index]),
            "q_value": float(q_values[index]),
            "multiscale_stability": stability,
            "confidence": confidence,
            "is_local_maximum": False,
        })

    for index, row in enumerate(rows):
        score = row["embedding_divergence"]
        left = rows[index - 1]["embedding_divergence"] if index else -math.inf
        right = rows[index + 1]["embedding_divergence"] if index + 1 < len(rows) else -math.inf
        row["is_local_maximum"] = score >= left and score >= right
    return rows


def choose_boundaries(
    evidence: list[dict],
    event_count: int,
    fdr: float,
    min_stability: float,
    min_gap: int,
    min_segment: int,
    max_splits: int,
    length_bands: list[tuple[int, float]],
) -> tuple[list[dict], list[dict]]:
    candidates = [
        row for row in evidence
        if row["safe_text_boundary"]
        and row["is_local_maximum"]
        and row["multiscale_stability"] >= min_stability
    ]
    active = [(0, event_count)]
    selected = []
    decisions = []
    while active and len(selected) < max_splits:
        available = []
        for start, end in active:
            available.extend(
                row for row in candidates
                if start + min_segment <= row["boundary_after_event"] <= end - min_segment
            )
        if not available:
            break
        available = [
            row for row in available
            if all(abs(row["boundary_after_event"] - other["boundary_after_event"]) >= min_gap for other in selected)
        ]
        if not available:
            break
        chosen = max(available, key=lambda row: row["confidence"])
        position = chosen["boundary_after_event"]
        interval = next(
            interval for interval in active
            if interval[0] + min_segment <= position <= interval[1] - min_segment
        )
        interval_length = interval[1] - interval[0]
        effective_fdr = fdr_for_length(interval_length, length_bands)
        accepted = chosen["q_value"] <= effective_fdr and chosen["multiscale_stability"] >= min_stability
        decisions.append({
            "iteration": len(decisions) + 1,
            "boundary_after_event": position,
            "interval_start": interval[0],
            "interval_end": interval[1],
            "confidence": chosen["confidence"],
            "q_value": chosen["q_value"],
            "multiscale_stability": chosen["multiscale_stability"],
            "interval_length": interval_length,
            "effective_fdr": effective_fdr,
            "accepted": accepted,
            "stop_reason": None if accepted else "calibrated_evidence_below_threshold",
        })
        if not accepted:
            break
        active.remove(interval)
        active.extend([(interval[0], position), (position, interval[1])])
        selected.append(chosen)
    selected.sort(key=lambda row: row["boundary_after_event"])
    return selected, decisions


def materialize_segments(events: list[dict], boundaries: list[int], overlap: int) -> list[dict]:
    ranges = list(zip([0, *boundaries], [*boundaries, len(events)]))
    result = []
    for index, (core_start, core_end) in enumerate(ranges, start=1):
        start = max(0, core_start - overlap)
        end = min(len(events), core_end + overlap)
        part = events[start:end]
        counts = Counter(event.get("category", "") for event in part)
        result.append({
            "segment_index": index,
            "start_event": start + 1,
            "end_event": end,
            "core_start_event": core_start + 1,
            "core_end_event": core_end,
            "overlap_before": core_start - start,
            "overlap_after": end - core_end,
            "length": len(part),
            "category_counts": dict(counts.most_common()),
            "events": part,
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--embeddings", type=Path, default=base / "message-embeddings.jsonl")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--windows", default="13,25,37")
    parser.add_argument("--fdr", type=float, default=0.10)
    parser.add_argument("--min-stability", type=float, default=2 / 3)
    parser.add_argument("--min-gap", type=int, default=30)
    parser.add_argument("--min-segment", type=int, default=30)
    parser.add_argument("--overlap-events", type=int, default=25)
    parser.add_argument("--max-splits", type=int, default=100)
    parser.add_argument("--length-bands", default="0:0.10,500:0.30,800:0.45")
    args = parser.parse_args()
    windows = tuple(sorted({int(item) for item in args.windows.split(",") if item.strip()}))
    if (
        not windows or min(windows) < 1 or not 0 < args.fdr < 1
        or not 0 <= args.min_stability <= 1
    ):
        parser.error("invalid parameters")
    try:
        length_bands = parse_length_bands(args.length_bands)
    except ValueError as error:
        parser.error(str(error))

    source = json.loads(args.input.resolve().read_text(encoding="utf-8"))
    embeddings = load_embeddings(args.embeddings.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions = []
    for session in source["trajectories"]:
        session_id = session["session_id"]
        events = session.get("events", [])
        evidence = boundary_evidence(events, embeddings[session_id], windows, args.min_segment)
        selected, decisions = choose_boundaries(
            evidence, len(events), args.fdr, args.min_stability,
            args.min_gap, args.min_segment, args.max_splits,
            length_bands,
        )
        boundaries = [row["boundary_after_event"] for row in selected]
        segments = materialize_segments(events, boundaries, args.overlap_events)
        session_dir = args.output_dir / f"{session.get('harness', 'unknown')}__{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        for segment in segments:
            segment_path = session_dir / f"segment-{segment['segment_index']:02d}.json"
            segment_path.write_text(json.dumps(segment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (session_dir / "index.json").write_text(
            json.dumps({
                "session_id": session_id,
                "event_count": len(events),
                "boundaries_after_event": boundaries,
                "segment_count": len(segments),
                "formula_version": "calibrated-confidence-length-banded-v3",
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sessions.append({
            "harness": session.get("harness"),
            "session_id": session_id,
            "event_count": len(events),
            "candidate_count": len(evidence),
            "selected_boundary_count": len(boundaries),
            "boundaries_after_event": boundaries,
            "split_decisions": decisions,
            "evidence": evidence,
            "segments": segments,
        })

    output = {
        "formula": {
            "version": "calibrated-confidence-length-banded-v3",
            "representation": "normalized message embeddings; no category-to-number distance",
            "divergence": "mean multi-window cosine distance between left/right embedding centroids",
            "calibration": "session-local robust z-score + normal upper-tail p-value + Benjamini-Hochberg q-value",
            "confidence": "(1-q_value) * (0.5 + 0.5*multiscale_stability)",
            "acceptance": "safe text boundary, q_value <= FDR band selected by interval length, "
            f"stability >= {args.min_stability}",
            "selection": "best-first recursive splitting with minimum segment and gap constraints",
            "parameters": {
                "windows": windows,
                "fdr": args.fdr,
                "min_stability": args.min_stability,
                "min_gap": args.min_gap,
                "min_segment": args.min_segment,
                "overlap_events": args.overlap_events,
                "max_splits": args.max_splits,
                "length_bands": length_bands,
            },
            "caveat": "q-values are calibrated statistical evidence under a local robust-normal null, not semantic correctness probabilities",
        },
        "session_count": len(sessions),
        "total_event_count": sum(item["event_count"] for item in sessions),
        "total_selected_boundaries": sum(item["selected_boundary_count"] for item in sessions),
        "total_segments": sum(len(item["segments"]) for item in sessions),
        "sessions": sessions,
    }
    args.output.resolve().write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"formula_version={output['formula']['version']}")
    print(f"sessions={output['session_count']}")
    print(f"events={output['total_event_count']}")
    print(f"selected_boundaries={output['total_selected_boundaries']}")
    print(f"segments={output['total_segments']}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
