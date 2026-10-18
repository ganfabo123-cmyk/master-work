"""Find persistent multiscale embedding-change peaks without segmenting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_embedding_change_scores import (
    DEFAULT_INPUT,
    WINDOWS,
    calculate_scores,
    load_sessions,
    robust_standardize,
)


DEFAULT_OUTPUT = Path(__file__).parent / "persistent-embedding-peaks"


def moving_average(values: np.ndarray, width: int = 7) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=np.float32)
    valid = np.isfinite(values)
    if not np.any(valid):
        return result
    filled = np.nan_to_num(values, nan=0.0)
    weights = valid.astype(np.float32)
    kernel = np.ones(width, dtype=np.float32)
    total = np.convolve(filled, kernel, mode="same")
    count = np.convolve(weights, kernel, mode="same")
    result[count > 0] = total[count > 0] / count[count > 0]
    return result


def local_maxima(values: np.ndarray, radius: int = 8) -> np.ndarray:
    positions: list[int] = []
    for index in range(radius, len(values) - radius):
        if not np.isfinite(values[index]):
            continue
        neighborhood = values[index - radius : index + radius + 1]
        finite = neighborhood[np.isfinite(neighborhood)]
        if len(finite) and values[index] >= np.max(finite):
            positions.append(index)
    return np.asarray(positions, dtype=int)


def find_peaks(
    scores: dict[int, np.ndarray],
    composite: np.ndarray,
    threshold: float,
    min_distance: int,
    min_support: int,
) -> list[dict]:
    standardized = {window: robust_standardize(scores[window]) for window in WINDOWS}
    smoothed = moving_average(composite)
    candidates: list[dict] = []
    for position in local_maxima(smoothed):
        support_windows: list[int] = []
        support_values: list[float] = []
        for window in WINDOWS:
            values = standardized[window]
            tolerance = max(3, min_distance // 2, window // 4)
            start = max(0, position - tolerance)
            end = min(len(values), position + tolerance + 1)
            local = values[start:end]
            finite = local[np.isfinite(local)]
            best = float(np.max(finite)) if len(finite) else float("nan")
            if np.isfinite(best) and best >= threshold:
                support_windows.append(window)
                support_values.append(best)
        if len(support_windows) >= min_support:
            candidates.append(
                {
                    "event_index": int(position + 1),
                    "score": float(smoothed[position]),
                    "scale_support": len(support_windows),
                    "scale_support_ratio": len(support_windows) / len(WINDOWS),
                    "support_windows": support_windows,
                    "support_z_scores": support_values,
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    selected: list[dict] = []
    for candidate in candidates:
        if all(abs(candidate["event_index"] - chosen["event_index"]) >= min_distance for chosen in selected):
            selected.append(candidate)
    selected.sort(key=lambda item: item["event_index"])
    return selected


def plot_marked(session_id: str, composite: np.ndarray, peaks: list[dict], output: Path) -> None:
    x = np.arange(1, len(composite) + 1)
    positions = np.asarray([peak["event_index"] for peak in peaks], dtype=int)
    fig, ax = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    ax.plot(x, composite, color="black", linewidth=0.8)
    if len(positions):
        zero_based = positions - 1
        ax.scatter(positions, composite[zero_based], color="tab:red", s=30, zorder=3, label="persistent peak")
        for peak in peaks:
            ax.axvline(peak["event_index"], color="tab:red", alpha=0.12, linewidth=0.8)
    ax.axhline(0, color="gray", linewidth=0.5, alpha=0.6)
    ax.set_title(f"{session_id}: persistent multiscale peaks")
    ax.set_xlabel("Event index")
    ax.set_ylabel("standardized multiscale change")
    ax.grid(alpha=0.2)
    if len(positions):
        ax.legend()
    fig.savefig(output, dpi=170)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=1.0, help="minimum robust z-score on a supporting scale")
    parser.add_argument("--min-distance", type=int, default=15)
    parser.add_argument("--min-support", type=int, default=2, help="minimum number of supporting windows")
    args = parser.parse_args()

    sessions = load_sessions(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = args.output_dir / "sessions"
    plot_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, dict] = {}
    total = 0
    for session_id, (_rows, vectors) in sorted(sessions.items()):
        scores, composite = calculate_scores(vectors)
        peaks = find_peaks(scores, composite, args.threshold, args.min_distance, args.min_support)
        plot_marked(session_id, composite, peaks, plot_dir / f"{session_id}.png")
        result[session_id] = {"event_count": len(vectors), "peaks": peaks}
        total += len(peaks)
    payload = {
        "method": "local maxima of smoothed multiscale composite",
        "windows": WINDOWS,
        "threshold": args.threshold,
        "min_distance": args.min_distance,
        "min_support": args.min_support,
        "session_count": len(result),
        "total_peaks": total,
        "sessions": result,
    }
    (args.output_dir / "persistent-peaks.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"sessions: {len(result)}")
    print(f"persistent peaks: {total}")
    print(f"output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
