from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from time import sleep
from uuid import uuid4

from ...core.models import Message, ToolCall
from ..room.models import RoomMessage
from .agent import record_agent_error, record_assistant_message, record_feedback, record_initial_messages, record_room_inbox, record_tool_message
from .room import record_room_message


def _json_default(value: object) -> object:
    return asdict(value) if is_dataclass(value) else str(value)


def _markdown_event(event: dict[str, object]) -> dict[str, object]:
    """Return a display-only projection with native tool arguments expanded."""
    rendered = json.loads(json.dumps(event, ensure_ascii=False, default=_json_default))

    def expand_arguments(value: object) -> object:
        if isinstance(value, list):
            return [expand_arguments(item) for item in value]
        if not isinstance(value, dict):
            return value
        expanded = {key: expand_arguments(item) for key, item in value.items()}
        arguments = expanded.get("arguments")
        if isinstance(arguments, str):
            try:
                decoded = json.loads(arguments)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(decoded, (dict, list)):
                    expanded["arguments"] = decoded
        return expanded

    return expand_arguments(rendered)


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
        """Link one durable ROOM without replacing other ROOMs in the session."""
        data = self.session_data(session_id)
        if data.get("mode") in {None, "agent", "room"}:
            data["mode"] = "multi-room"
        rooms = data.setdefault("rooms", [])
        descriptor = {"room_id": room_id, "session_id": room_session_id}
        if descriptor not in rooms:
            rooms.append(descriptor)
        # Kept for old Web clients and old single-ROOM session readers.
        if "room" not in data:
            data["room"] = descriptor
        self._write_json(self.root / session_id / "session.json", data)

    def update_session_metadata(self, session_id: str, **metadata: object) -> None:
        """Store workflow-owned metadata without changing generic trace semantics."""
        data = self.session_data(session_id)
        data.update(metadata)
        self._write_json(self.root / session_id / "session.json", data)

    def record_room_message(self, session_id: str, room_id: str, message: RoomMessage) -> None:
        """Append the canonical ROOM message to its sender's Agent trace."""
        record_room_message(self, session_id, room_id, message)

    def record_messages(self, session_id: str, agent_name: str, messages: Sequence[Message]) -> None:
        """Append newly created model messages without re-recording prior history."""
        for message in messages:
            trace_message = message.as_dict()
            event_type = "system" if message.role == "developer" else message.role
            self.record(session_id, agent_name, event_type, message=trace_message)

    def record_initial_messages(self, session_id: str, agent_name: str, messages: Sequence[Message]) -> None:
        """Record the stable prompt prefix sent to one Agent."""
        record_initial_messages(self, session_id, agent_name, messages)

    def record_assistant_message(self, session_id: str, agent_name: str, message: Message, **metadata: object) -> None:
        record_assistant_message(self, session_id, agent_name, message, **metadata)

    def record_tool_message(self, session_id: str, agent_name: str, message: Message, *, duration_ms: float, success: bool = True) -> None:
        record_tool_message(self, session_id, agent_name, message, duration_ms=duration_ms, success=success)

    def record_feedback(self, session_id: str, agent_name: str, message: Message) -> None:
        record_feedback(self, session_id, agent_name, message)

    def record_room_inbox(self, session_id: str, agent_name: str, rooms: dict[str, tuple[str, ...]]) -> None:
        record_room_inbox(self, session_id, agent_name, rooms)

    def record_agent_error(self, session_id: str, agent_name: str, *, stage: str, error: str) -> None:
        record_agent_error(self, session_id, agent_name, stage=stage, error=error)

    def room_message(self, session_id: str, message_id: str) -> RoomMessage:
        for message in self.room_messages(session_id):
            if message.message_id == message_id:
                return message
        raise KeyError(f"ROOM message does not exist: {message_id}")

    def room_messages(self, session_id: str, room_id: str | None = None) -> tuple[RoomMessage, ...]:
        """Read canonical ROOM messages from every Agent JSONL trace in event order."""
        directory = self._agents_directory(session_id)
        messages: list[RoomMessage] = []
        paths = sorted(directory.glob("*.jsonl")) if directory.exists() else []
        if not paths:
            paths = sorted((self.root / session_id).glob("*.jsonl"))
        for path in paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event_type") != "room_message_sent" or (room_id is not None and event.get("room_id") != room_id):
                    continue
                raw = event.get("message")
                if isinstance(raw, dict):
                    messages.append(RoomMessage.model_validate(raw))
        return tuple(sorted(messages, key=lambda message: (message.created_at, message.message_id)))

    def messages(self, session_id: str, agent_name: str) -> tuple[Message, ...]:
        """Restore the message stream recorded for one Agent, in append order."""
        path = self._agent_jsonl_path(session_id, agent_name)
        if not path.exists():
            path = self.root / session_id / f"{agent_name}.jsonl"
        if not path.exists():
            raise KeyError(f"No trace messages exist for agent '{agent_name}' in session '{session_id}'")
        messages: list[Message] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            raw_message = event.get("message")
            if isinstance(raw_message, dict) and raw_message.get("role") in {"system", "developer", "user", "assistant", "tool"}:
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
        agent_jsonl = self._agent_jsonl_path(session_id, agent_name)
        agent_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with agent_jsonl.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, default=_json_default) + "\n")
        with self._agent_markdown_path(session_id, agent_name).open("a", encoding="utf-8") as file:
            readable_event = _markdown_event(event)
            file.write(f"## {event_type}\n\n```json\n{json.dumps(readable_event, ensure_ascii=False, indent=2)}\n```\n\n")

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
            for attempt in range(8):
                try:
                    temporary.replace(path)
                    break
                except PermissionError:
                    if attempt == 7:
                        raise
                    sleep(0.025)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _agents_directory(self, session_id: str) -> Path:
        return self.root / session_id / "agents"

    def _agent_jsonl_path(self, session_id: str, agent_name: str) -> Path:
        return self._agents_directory(session_id) / f"{agent_name}.jsonl"

    def _agent_markdown_path(self, session_id: str, agent_name: str) -> Path:
        return self._agents_directory(session_id) / f"{agent_name}.md"


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
