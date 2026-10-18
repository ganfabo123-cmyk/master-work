"""Plot multiscale semantic change scores for embedding trajectories.

This script only visualizes candidate boundary signals. It does not segment
sessions or select final boundaries.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).parent
DEFAULT_INPUT = ROOT / "message-embeddings.jsonl"
DEFAULT_OUTPUT = ROOT / "embedding-change-score-plots"
WINDOWS = (5, 15, 30, 60)


def load_sessions(path: Path) -> dict[str, tuple[list[dict], np.ndarray]]:
    rows: dict[str, list[dict]] = defaultdict(list)
    vectors: dict[str, list[list[float]]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            session_id = item["session_id"]
            rows[session_id].append(item)
            vectors[session_id].append(item["embedding"])
    return {
        session_id: (rows[session_id], np.asarray(vectors[session_id], dtype=np.float32))
        for session_id in rows
    }


def rolling_change(vectors: np.ndarray, window: int) -> np.ndarray:
    """Cosine distance between the normalized means on both sides of t."""
    n, _ = vectors.shape
    scores = np.full(n, np.nan, dtype=np.float32)
    if n < 2 * window + 1:
        return scores
    cumulative = np.vstack([np.zeros((1, vectors.shape[1]), dtype=np.float32), np.cumsum(vectors, axis=0)])
    for t in range(window - 1, n - window):
        left = (cumulative[t + 1] - cumulative[t + 1 - window]) / window
        right = (cumulative[t + 1 + window] - cumulative[t + 1]) / window
        left_norm = np.linalg.norm(left)
        right_norm = np.linalg.norm(right)
        if left_norm == 0 or right_norm == 0:
            continue
        scores[t] = 1.0 - float(np.dot(left, right) / (left_norm * right_norm))
    return scores


def robust_standardize(values: np.ndarray) -> np.ndarray:
    valid = values[np.isfinite(values)]
    result = np.full_like(values, np.nan)
    if len(valid) < 2:
        return result
    median = np.median(valid)
    mad = np.median(np.abs(valid - median))
    scale = 1.4826 * mad
    if scale < 1e-8:
        scale = np.std(valid)
    if scale < 1e-8:
        scale = 1.0
    result[np.isfinite(values)] = (values[np.isfinite(values)] - median) / scale
    return result


def calculate_scores(vectors: np.ndarray) -> tuple[dict[int, np.ndarray], np.ndarray]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / np.maximum(norms, 1e-8)
    by_window = {window: rolling_change(normalized, window) for window in WINDOWS}
    standardized = [robust_standardize(by_window[window]) for window in WINDOWS]
    stacked = np.stack(standardized)
    valid_count = np.sum(np.isfinite(stacked), axis=0)
    composite = np.divide(
        np.nansum(stacked, axis=0),
        valid_count,
        out=np.full(stacked.shape[1], np.nan, dtype=np.float32),
        where=valid_count > 0,
    )
    return by_window, composite


def plot_session(session_id: str, rows: list[dict], scores: dict[int, np.ndarray], composite: np.ndarray, output: Path) -> None:
    x = np.arange(1, len(rows) + 1)
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True, constrained_layout=True)
    colors = ("tab:blue", "tab:orange", "tab:green", "tab:red")
    for color, window in zip(colors, WINDOWS):
        axes[0].plot(x, scores[window], linewidth=0.8, alpha=0.85, color=color, label=f"window={window}")
    axes[0].set_title(f"Session {session_id}: raw multiscale semantic change")
    axes[0].set_ylabel("1 - cosine similarity")
    axes[0].legend(ncol=4, fontsize=8)
    axes[0].grid(alpha=0.2)

    axes[1].plot(x, composite, linewidth=0.9, color="black")
    axes[1].axhline(0, linewidth=0.6, color="gray", alpha=0.6)
    axes[1].set_title("Robust-standardized multiscale composite (visual signal only)")
    axes[1].set_xlabel("Event index")
    axes[1].set_ylabel("standardized score")
    axes[1].grid(alpha=0.2)
    fig.savefig(output, dpi=170)
    plt.close(fig)


def plot_grid(all_scores: dict[str, tuple[np.ndarray, int]], output: Path) -> None:
    sessions = sorted(all_scores)
    fig, axes = plt.subplots(5, 6, figsize=(18, 13), constrained_layout=True)
    for ax, session_id in zip(axes.flat, sessions):
        composite, length = all_scores[session_id]
        ax.plot(np.arange(1, length + 1), composite, linewidth=0.6, color="black")
        ax.axhline(0, linewidth=0.4, color="gray", alpha=0.6)
        ax.set_title(session_id[:8], fontsize=8)
        ax.tick_params(labelsize=6)
        ax.grid(alpha=0.15, linewidth=0.4)
    for ax in axes.flat[len(sessions):]:
        ax.axis("off")
    fig.supxlabel("Event index")
    fig.supylabel("standardized multiscale change")
    fig.suptitle("Embedding semantic-change signals across sessions")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    sessions = load_sessions(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    individual_dir = args.output_dir / "sessions"
    individual_dir.mkdir(parents=True, exist_ok=True)
    grid_data: dict[str, tuple[np.ndarray, int]] = {}
    summary: dict[str, dict] = {}
    for session_id, (rows, vectors) in sorted(sessions.items()):
        scores, composite = calculate_scores(vectors)
        plot_session(session_id, rows, scores, composite, individual_dir / f"{session_id}.png")
        grid_data[session_id] = (composite, len(rows))
        valid = composite[np.isfinite(composite)]
        summary[session_id] = {
            "event_count": len(rows),
            "valid_composite_points": int(len(valid)),
            "max_composite": float(np.max(valid)) if len(valid) else None,
            "mean_composite": float(np.mean(valid)) if len(valid) else None,
        }
    plot_grid(grid_data, args.output_dir / "all-session-composite-grid.png")
    (args.output_dir / "change-score-summary.json").write_text(
        json.dumps({"windows": WINDOWS, "sessions": summary}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"plotted {sum(item['event_count'] for item in summary.values())} events")
    print(f"sessions: {len(summary)}")
    print(f"windows: {WINDOWS}")
    print(f"output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
