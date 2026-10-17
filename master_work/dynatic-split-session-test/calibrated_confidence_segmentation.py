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
import copy
import hashlib
from collections import Counter
from pathlib import Path

def load_embeddings(path: Path) -> dict[str, np.ndarray]:
    import numpy as np
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
    import numpy as np
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(1.4826 * mad, 1e-6)


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    import numpy as np
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
    import numpy as np
    import frozen_message_segmentation as frozen
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


def load_raw_parts(path: Path) -> dict[tuple[int, int], dict]:
    """Index original parts without changing the segmentation event sequence."""
    parts = {}
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for index, message in enumerate(data["messages"]):
            for offset, part in enumerate(message.get("parts", [])):
                if isinstance(part, dict):
                    parts[index, offset] = part
    else:
        for index, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines()):
            if not line.strip():
                continue
            record = json.loads(line)
            message = record.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for offset, part in enumerate(content):
                    if isinstance(part, dict):
                        parts[index, offset] = part
    return parts


def restore_event_payload(event: dict, parts: dict[tuple[int, int], dict]) -> dict:
    """Restore hidden payloads after cutting; never insert or reorder events."""
    result = copy.deepcopy(event)
    category = event.get("category", "")
    target = category == "tool_result" or category.endswith(("_thinking", "_reasoning"))
    # OpenCode stores the call and its result together in a single tool part.
    target = target or (event.get("part_type") == "tool" and category.startswith("tool_call:"))
    if not target:
        return result
    key = (event.get("source_index"), event.get("source_part_index", 0))
    part = parts.get(key)
    if part is None or part.get("type") != event.get("part_type"):
        raise ValueError(f"Original part missing or mismatched: {key}, {category}")
    result["payload_restored"] = True
    if category == "tool_result":
        # Preserve result metadata without duplicating the long body.
        for field, value in part.items():
            if field not in {"type", "content", "output"}:
                result[field] = copy.deepcopy(value)
        result["content"] = copy.deepcopy(part.get("content", part.get("output", "")))
        if "is_error" in part:
            result["is_error"] = part["is_error"]
    elif category.endswith(("_thinking", "_reasoning")):
        result["text"] = part.get("thinking", part.get("text", ""))
        for field, value in part.items():
            if field not in {"type", "thinking", "text"}:
                result[field] = copy.deepcopy(value)
    else:
        # Keep this on the existing event rather than changing event coordinates.
        result["tool_result"] = copy.deepcopy(part.get("state", {}))
    return result


def restore_session_segments(session: dict, path: Path) -> dict:
    parts = load_raw_parts(path)
    restored = set()
    for segment in session["segments"]:
        events = []
        for event in segment["events"]:
            full = restore_event_payload(event, parts)
            if full.get("payload_restored"):
                restored.add((full["source_index"], full.get("source_part_index", 0), full["category"]))
            events.append(full)
        segment["events"] = events
    return {"source_path": str(path.resolve()), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "restored_unique_parts": len(restored)}


def source_paths(report_path: Path, raw_root: Path) -> dict[tuple[str, str], Path]:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    paths = {}
    root = raw_root.resolve()
    for source in report["sessions"]:
        path = (root / source["source_file"]).resolve()
        if root not in path.parents or not path.is_file():
            raise ValueError(f"Invalid or missing original trace: {path}")
        paths[source["harness"], source["session_id"]] = path
    return paths


def write_slices(session: dict, output_dir: Path) -> None:
    directory = output_dir / f"{session['harness']}__{session['session_id']}"
    directory.mkdir(parents=True, exist_ok=True)
    for segment in session["segments"]:
        (directory / f"segment-{segment['segment_index']:02d}.json").write_text(
            json.dumps(segment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "index.json").write_text(json.dumps({
        "session_id": session["session_id"], "event_count": session["event_count"],
        "boundaries_after_event": session["boundaries_after_event"],
        "segment_count": len(session["segments"]),
        "formula_version": "calibrated-confidence-length-banded-v3",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reuse_and_restore(segments_path: Path, report_path: Path, raw_root: Path,
                     output_path: Path, output_dir: Path) -> dict:
    """Export frozen boundaries with original payloads; no numeric dependencies."""
    if output_path.exists() or output_dir.exists():
        raise ValueError("Use new output paths; existing segmentation artifacts are preserved")
    data = json.loads(segments_path.read_text(encoding="utf-8-sig"))
    if data.get("formula", {}).get("version") != "calibrated-confidence-length-banded-v3":
        raise ValueError("Expected calibrated-confidence-length-banded-v3 segments")
    paths = source_paths(report_path, raw_root)
    stats = []
    for session in data["sessions"]:
        path = paths[session["harness"], session["session_id"]]
        stats.append({"harness": session["harness"], "session_id": session["session_id"],
                      **restore_session_segments(session, path)})
    data["payload_restoration"] = {"mode": "after_segmentation_original_parts",
        "source_segments": str(segments_path.resolve()), "source_report": str(report_path.resolve()),
        "embedding_calls": 0, "boundaries_recomputed": False,
        "restored_unique_parts": sum(s["restored_unique_parts"] for s in stats), "sessions": stats}
    for session in data["sessions"]:
        write_slices(session, output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "payload-restoration.json").write_text(
        json.dumps(data["payload_restoration"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(__file__).resolve().parent
    parser.add_argument("--input", type=Path, default=base / "message-trajectories.json")
    parser.add_argument("--embeddings", type=Path, default=base / "message-embeddings.jsonl")
    parser.add_argument("--reuse-segments", type=Path, help="Reuse saved v3 boundaries; no embeddings are read")
    parser.add_argument("--raw-sessions-root", type=Path, help="Restore original hidden payloads after cutting")
    parser.add_argument("--source-report", type=Path, help="toolcall-report.json mapping Session IDs to original files")
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
    if bool(args.raw_sessions_root) != bool(args.source_report):
        parser.error("--raw-sessions-root and --source-report must be supplied together")
    if args.reuse_segments:
        if not args.raw_sessions_root:
            parser.error("--reuse-segments requires --raw-sessions-root and --source-report")
        try:
            output = reuse_and_restore(args.reuse_segments, args.source_report, args.raw_sessions_root,
                                      args.output, args.output_dir)
        except (ValueError, OSError, KeyError) as error:
            parser.error(str(error))
        print(f"sessions={output['session_count']}")
        print(f"segments={output['total_segments']}")
        print(f"restored_parts={output['payload_restoration']['restored_unique_parts']}")
        print("embedding_calls=0; boundaries_recomputed=False")
        print(f"output={args.output.resolve()}")
        return 0
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
    originals = source_paths(args.source_report, args.raw_sessions_root) if args.raw_sessions_root else None
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
        if originals:
            restore_session_segments({"segments": segments}, originals[session.get("harness"), session_id])
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
