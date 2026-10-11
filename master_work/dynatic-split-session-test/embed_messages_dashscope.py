"""Embed every message event in the trajectory dataset with DashScope.

This is intentionally only an embedding step. It does not segment sessions,
calculate change points, or reduce vectors for visualization.

The script uses DashScope's OpenAI-compatible embeddings endpoint and the
standard library only, so no extra Python package is required.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-text-embedding"
DEFAULT_INPUT = Path(__file__).with_name("message-trajectories.json")
DEFAULT_OUTPUT = Path(__file__).with_name("message-embeddings.jsonl")
DEFAULT_META = Path(__file__).with_name("message-embeddings.meta.json")


def load_dotenv(path: Path) -> None:
    """Load a small .env file without requiring python-dotenv."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def event_to_text(event: dict[str, Any]) -> str:
    """Serialize one event without dropping tool arguments or message text."""
    # Keep the complete event payload. These two fields are only positions in
    # the source trace and would make the embedding learn event numbering.
    payload = {
        key: value
        for key, value in event.items()
        if key not in {"source_index", "source_part_index"} and value is not None
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_events(input_path: Path) -> list[dict[str, Any]]:
    dataset = json.loads(input_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for trajectory in dataset["trajectories"]:
        events = trajectory.get("events", [])
        for event_index, event in enumerate(events):
            rows.append(
                {
                    "session_id": trajectory["session_id"],
                    "harness": trajectory.get("harness"),
                    "event_index": event_index,
                    "source_index": event.get("source_index"),
                    "category": event.get("category"),
                    "input_text": event_to_text(event),
                }
            )
    return rows


def request_embeddings(
    base_url: str,
    api_key: str,
    model: str,
    inputs: list[str],
    dimensions: int | None,
    timeout: int,
) -> list[list[float]]:
    body: dict[str, Any] = {"model": model, "input": inputs}
    if dimensions is not None:
        body["dimensions"] = dimensions
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/embeddings",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = sorted(payload["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--meta-output", type=Path, default=DEFAULT_META)
    parser.add_argument("--model", default=os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL))
    parser.add_argument("--dimensions", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("EMBEDDING_BATCH_SIZE", "20")))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--resume", action="store_true", help="reuse existing JSONL rows by position")
    args = parser.parse_args()

    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        print("DASHSCOPE_API_KEY is empty; fill dynatic-split-session-test/.env first.", file=sys.stderr)
        return 2

    base_url = os.getenv("DASHSCOPE_BASE_URL", DEFAULT_BASE_URL)
    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")

    rows = read_events(args.input)
    existing: list[dict[str, Any]] = []
    if args.resume and args.output.exists():
        with args.output.open(encoding="utf-8") as handle:
            existing = [json.loads(line) for line in handle if line.strip()]
        if len(existing) > len(rows):
            raise RuntimeError("existing output has more rows than the input dataset")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if existing else "w"
    completed = len(existing)
    with args.output.open(mode, encoding="utf-8") as output:
        for start in range(completed, len(rows), args.batch_size):
            batch = rows[start : start + args.batch_size]
            last_error: Exception | None = None
            for attempt in range(args.retries + 1):
                try:
                    vectors = request_embeddings(
                        base_url, api_key, args.model,
                        [row["input_text"] for row in batch],
                        args.dimensions, args.timeout,
                    )
                    if len(vectors) != len(batch):
                        raise RuntimeError("API returned a different number of vectors")
                    for row, vector in zip(batch, vectors):
                        output.write(json.dumps({**row, "embedding": vector}, ensure_ascii=False) + "\n")
                    output.flush()
                    completed += len(batch)
                    print(f"embedded {completed}/{len(rows)}", flush=True)
                    last_error = None
                    break
                except (
                    urllib.error.HTTPError,
                    urllib.error.URLError,
                    http.client.IncompleteRead,
                    ConnectionError,
                    TimeoutError,
                    RuntimeError,
                ) as exc:
                    last_error = exc
                    if attempt < args.retries:
                        time.sleep(args.sleep_seconds * (attempt + 1))
            if last_error is not None:
                raise RuntimeError(f"embedding batch starting at {start} failed") from last_error

    meta = {
        "input": str(args.input),
        "output": str(args.output),
        "model": args.model,
        "dimensions": args.dimensions,
        "event_count": len(rows),
        "session_count": len({row["session_id"] for row in rows}),
        "batch_size": args.batch_size,
        "representation": "serialized complete event fields; no category-to-number mapping",
    }
    args.meta_output.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"done: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
