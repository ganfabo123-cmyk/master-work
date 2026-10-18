"""读取一个 JSONL mock session，执行动态检索并输出统一结果。"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dynamic_retrieval_test import PROGRAM


def load_mock_session(session_path: Path) -> list[Any]:
    """将 JSONL 文件中的每个非空行解析为一个 raw trace 事件。"""

    events: list[Any] = []
    with session_path.open("r", encoding="utf-8") as session_file:
        for line_number, line in enumerate(session_file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{session_path} 第 {line_number} 行不是合法 JSON"
                ) from error
    return events


def run_mock_session(session_path: Path) -> dict[str, Any]:
    """依次传入 session 事件，并收集每个事件对应的检索结果。"""

    results: list[dict[str, Any]] = []
    for event_index, raw_trace in enumerate(load_mock_session(session_path), start=1):
        retrieval_result = PROGRAM.handle_raw_trace(raw_trace)
        results.append(
            {
                "event_index": event_index,
                "raw_trace": raw_trace,
                "retrieval_result": asdict(retrieval_result),
            }
        )
    return {
        "session_file": str(session_path.resolve()),
        "event_count": len(results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 JSONL mock session 试跑动态检索"
    )
    parser.add_argument(
        "session_file",
        type=Path,
        help="包含 raw trace 事件的 JSONL 文件",
    )
    args = parser.parse_args()

    output = run_mock_session(args.session_file)
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
