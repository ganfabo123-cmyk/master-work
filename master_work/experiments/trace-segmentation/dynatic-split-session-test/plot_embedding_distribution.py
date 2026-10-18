"""Visualize message embeddings with one shared two-dimensional PCA space."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.decomposition import PCA


ROOT = Path(__file__).parent
DEFAULT_INPUT = ROOT / "message-embeddings.jsonl"
DEFAULT_OUTPUT = ROOT / "embedding-visualizations"


def load_embeddings(path: Path) -> tuple[list[dict], np.ndarray]:
    rows: list[dict] = []
    vectors: list[list[float]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows.append(row)
            vectors.append(row["embedding"])
    if not rows:
        raise ValueError(f"no embeddings found in {path}")
    return rows, np.asarray(vectors, dtype=np.float32)


def configure_axes(ax: plt.Axes, title: str, explained: np.ndarray) -> None:
    ax.set_title(title)
    ax.set_xlabel(f"PC1 ({explained[0] * 100:.2f}% variance)")
    ax.set_ylabel(f"PC2 ({explained[1] * 100:.2f}% variance)")
    ax.grid(alpha=0.18, linewidth=0.6)


def plot_global(rows: list[dict], coords: np.ndarray, output: Path, explained: np.ndarray) -> None:
    sessions = sorted({row["session_id"] for row in rows})
    session_index = {session_id: index for index, session_id in enumerate(sessions)}
    colors = plt.get_cmap("tab20", max(len(sessions), 20))

    fig, ax = plt.subplots(figsize=(14, 9), constrained_layout=True)
    for session_id in sessions:
        indexes = [i for i, row in enumerate(rows) if row["session_id"] == session_id]
        ax.scatter(
            coords[indexes, 0],
            coords[indexes, 1],
            s=5,
            alpha=0.42,
            color=colors(session_index[session_id] % 20),
            label=session_id[:8],
            rasterized=True,
        )
    configure_axes(ax, "All message embeddings in shared PCA space", explained)
    ax.legend(title="session", fontsize=7, ncol=3, markerscale=2, loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_grid(rows: list[dict], coords: np.ndarray, output: Path, explained: np.ndarray) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["session_id"]].append(index)
    sessions = sorted(grouped)
    fig, axes = plt.subplots(5, 6, figsize=(18, 14), constrained_layout=True)
    for ax, session_id in zip(axes.flat, sessions):
        indexes = grouped[session_id]
        points = coords[indexes]
        ax.plot(points[:, 0], points[:, 1], linewidth=0.45, alpha=0.5, color="tab:blue")
        ax.scatter(points[:, 0], points[:, 1], s=3, alpha=0.55, color="tab:blue", rasterized=True)
        ax.set_title(session_id[:8], fontsize=8)
        ax.tick_params(labelsize=6)
        ax.grid(alpha=0.15, linewidth=0.4)
    for ax in axes.flat[len(sessions):]:
        ax.axis("off")
    fig.supxlabel(f"PC1 ({explained[0] * 100:.2f}% variance)")
    fig.supylabel(f"PC2 ({explained[1] * 100:.2f}% variance)")
    fig.suptitle("Message embedding trajectories by session (shared PCA axes)")
    fig.savefig(output, dpi=180)
    plt.close(fig)


def plot_individual(rows: list[dict], coords: np.ndarray, output_dir: Path, explained: np.ndarray) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[row["session_id"]].append(index)
    single_dir = output_dir / "sessions"
    single_dir.mkdir(parents=True, exist_ok=True)
    for session_id, indexes in grouped.items():
        points = coords[indexes]
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(points[:, 0], points[:, 1], linewidth=0.7, alpha=0.65, color="tab:blue")
        ax.scatter(points[:, 0], points[:, 1], s=7, alpha=0.65, color="tab:blue", rasterized=True)
        ax.scatter(points[0, 0], points[0, 1], s=42, color="tab:green", label="start", zorder=3)
        ax.scatter(points[-1, 0], points[-1, 1], s=42, color="tab:red", label="end", zorder=3)
        configure_axes(ax, f"Session {session_id}", explained)
        ax.legend()
        fig.tight_layout()
        fig.savefig(single_dir / f"{session_id}.png", dpi=170)
        plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows, vectors = load_embeddings(args.input)
    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(vectors)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.save(args.output_dir / "message-embeddings-pca2.npy", coords)
    (args.output_dir / "pca-summary.json").write_text(
        json.dumps(
            {
                "input": str(args.input),
                "event_count": len(rows),
                "session_count": len({row["session_id"] for row in rows}),
                "input_dimension": int(vectors.shape[1]),
                "output_dimension": 2,
                "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    plot_global(rows, coords, args.output_dir / "global-pca-by-session.png", pca.explained_variance_ratio_)
    plot_grid(rows, coords, args.output_dir / "session-trajectory-grid.png", pca.explained_variance_ratio_)
    plot_individual(rows, coords, args.output_dir, pca.explained_variance_ratio_)
    print(f"plotted {len(rows)} embeddings from {len({row['session_id'] for row in rows})} sessions")
    print(f"explained variance: {pca.explained_variance_ratio_.tolist()}")
    print(f"output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
