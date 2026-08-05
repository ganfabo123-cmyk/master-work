from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4


def _json_default(value: object) -> object:
    return asdict(value) if is_dataclass(value) else str(value)


class TraceRecorder:
    """Append-only JSONL fact source plus a readable Markdown projection."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._starts: dict[str, float] = {}
        self._token_totals: dict[str, dict[str, int]] = {}

    def create_session(self, task: str, agent_name: str) -> str:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        directory = self.root / session_id
        directory.mkdir(parents=True, exist_ok=False)
        self._starts[session_id] = perf_counter()
        self._token_totals[session_id] = {"input": 0, "output": 0, "total": 0}
        self._write_json(
            directory / "session.json",
            {
                "session_id": session_id,
                "task": task,
                "status": "running",
                "agents": [agent_name],
                "tokens": self._token_totals[session_id],
            },
        )
        return session_id

    def record(self, session_id: str, agent_name: str, event_type: str, **payload: object) -> None:
        directory = self.root / session_id
        event = {"timestamp": datetime.now().astimezone().isoformat(), "event_type": event_type, **payload}
        if event_type == "assistant":
            totals = self._token_totals[session_id]
            totals["input"] += _token_value(payload.get("input_tokens"))
            totals["output"] += _token_value(payload.get("output_tokens"))
            totals["total"] += _token_value(payload.get("total_tokens"))
        with (directory / f"{agent_name}.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, default=_json_default) + "\n")
        with (directory / f"{agent_name}.md").open("a", encoding="utf-8") as file:
            file.write(f"## {event_type}\n\n```json\n{json.dumps(event, ensure_ascii=False, indent=2, default=_json_default)}\n```\n\n")

    def finish_session(self, session_id: str, status: str, error: str | None = None) -> None:
        path = self.root / session_id / "session.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(
            {
                "status": status,
                "error": error,
                "end_time": datetime.now().astimezone().isoformat(),
                "duration_ms": round((perf_counter() - self._starts[session_id]) * 1000, 2),
                "tokens": self._token_totals[session_id],
            }
        )
        self._write_json(path, data)

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _token_value(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0
