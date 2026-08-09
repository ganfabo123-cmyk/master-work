"""Generic Agent and model-call trace event writers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...core.models import Message

if TYPE_CHECKING:
    from .recorder import TraceRecorder


def record_initial_messages(recorder: TraceRecorder, session_id: str, agent_name: str, messages: Sequence[Message]) -> None:
    for message in messages:
        if message.role not in {"developer", "user"}:
            continue
        payload = message.as_dict()
        payload["role"] = "system" if message.role == "developer" else "user"
        recorder.record(session_id, agent_name, payload["role"], message=payload)


def record_assistant_message(recorder: TraceRecorder, session_id: str, agent_name: str, message: Message, **metadata: object) -> None:
    recorder.record(session_id, agent_name, "assistant", message=message.as_dict(), **metadata)


def record_tool_message(recorder: TraceRecorder, session_id: str, agent_name: str, message: Message, *, duration_ms: float, success: bool = True) -> None:
    recorder.record(session_id, agent_name, "tool", message=message.as_dict(), success=success, duration_ms=duration_ms)


def record_feedback(recorder: TraceRecorder, session_id: str, agent_name: str, message: Message) -> None:
    recorder.record(session_id, agent_name, "user", message=message.as_dict())


def record_room_inbox(recorder: TraceRecorder, session_id: str, agent_name: str, rooms: dict[str, tuple[str, ...]]) -> None:
    recorder.record(session_id, agent_name, "room_inbox", rooms=rooms)


def record_agent_error(recorder: TraceRecorder, session_id: str, agent_name: str, *, stage: str, error: str) -> None:
    recorder.record(session_id, agent_name, "error", stage=stage, error=error)
