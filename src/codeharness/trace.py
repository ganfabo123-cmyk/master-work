from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .models import Message, ToolCall


def _json_default(value: object) -> object:
    return asdict(value) if is_dataclass(value) else str(value)


class TraceRecorder:
    """Append-only JSONL fact source plus a readable Markdown projection."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._starts: dict[str, float] = {}
        self._elapsed_ms: dict[str, float] = {}
        self._token_totals: dict[str, dict[str, int]] = {}

    def create_session(
        self,
        task: str,
        agent_name: str,
        *,
        mode: str = "agent",
        room_id: str | None = None,
        room_session_id: str | None = None,
    ) -> str:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        directory = self.root / session_id
        directory.mkdir(parents=True, exist_ok=False)
        self._starts[session_id] = perf_counter()
        self._elapsed_ms[session_id] = 0.0
        self._token_totals[session_id] = {"input": 0, "output": 0, "total": 0}
        self._write_json(
            directory / "session.json",
            {
                "session_id": session_id,
                "task": task,
                "status": "running",
                "mode": mode,
                "entry_agent": agent_name,
                "agents": [agent_name],
                "tokens": self._token_totals[session_id],
                **({"room": {"room_id": room_id, "session_id": room_session_id}} if room_id and room_session_id else {}),
            },
        )
        return session_id

    def session_data(self, session_id: str) -> dict:
        """Load session metadata without changing its lifecycle state."""
        path = self.root / session_id / "session.json"
        if not path.exists():
            raise KeyError(f"Trace session does not exist: {session_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def resume_session(self, session_id: str, agent_name: str) -> tuple[Message, ...]:
        """Reopen one Agent trace session and restore its canonical message history."""
        data = self.session_data(session_id)
        if agent_name not in data.get("agents", []):
            raise ValueError(f"Agent '{agent_name}' does not belong to trace session '{session_id}'")
        self.resume_session_state(session_id)
        return self.messages(session_id, agent_name)

    def resume_session_state(self, session_id: str) -> dict:
        """Reopen the task root without choosing one of its participating Agents."""
        data = self.session_data(session_id)
        self._starts[session_id] = perf_counter()
        self._elapsed_ms[session_id] = float(data.get("duration_ms") or 0)
        stored_tokens = data.get("tokens") or {}
        self._token_totals[session_id] = {
            "input": _token_value(stored_tokens.get("input")),
            "output": _token_value(stored_tokens.get("output")),
            "total": _token_value(stored_tokens.get("total")),
        }
        data.update(
            {
                "status": "running",
                "error": None,
                "resumed_at": datetime.now().astimezone().isoformat(),
                "resume_count": int(data.get("resume_count") or 0) + 1,
            }
        )
        self._write_json(self.root / session_id / "session.json", data)
        return data

    def register_agent(self, session_id: str, agent_name: str) -> None:
        """Record one participating Agent under an existing task root session."""
        data = self.session_data(session_id)
        agents = data.setdefault("agents", [])
        if agent_name not in agents:
            agents.append(agent_name)
            self._write_json(self.root / session_id / "session.json", data)

    def attach_room(self, session_id: str, *, room_id: str, room_session_id: str) -> None:
        """Mark a task root as multi-Agent and link its durable ROOM state."""
        data = self.session_data(session_id)
        data["mode"] = data.get("mode", "room")
        data["room"] = {"room_id": room_id, "session_id": room_session_id}
        self._write_json(self.root / session_id / "session.json", data)

    def messages(self, session_id: str, agent_name: str) -> tuple[Message, ...]:
        """Restore the message stream recorded for one Agent, in append order."""
        path = self.root / session_id / f"{agent_name}.jsonl"
        if not path.exists():
            raise KeyError(f"No trace messages exist for agent '{agent_name}' in session '{session_id}'")
        messages: list[Message] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            raw_message = event.get("message")
            if isinstance(raw_message, dict):
                messages.append(_message_from_trace(raw_message))
        return tuple(messages)

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
                "duration_ms": round(self._elapsed_ms[session_id] + (perf_counter() - self._starts[session_id]) * 1000, 2),
                "tokens": self._token_totals[session_id],
            }
        )
        self._write_json(path, data)

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()


def _token_value(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _message_from_trace(raw: dict) -> Message:
    role = "developer" if raw.get("role") == "system" else raw.get("role")
    tool_calls = tuple(
        ToolCall(
            call["id"],
            call["function"]["name"],
            call["function"].get("arguments", "{}"),
        )
        for call in raw.get("tool_calls") or []
    )
    return Message(
        role=role,
        content=raw.get("content"),
        name=raw.get("name"),
        tool_call_id=raw.get("tool_call_id"),
        tool_calls=tool_calls,
    )
