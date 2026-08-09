"""ROOM trace event writers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..room.models import RoomMessage

if TYPE_CHECKING:
    from .recorder import TraceRecorder


def record_room_message(recorder: TraceRecorder, session_id: str, room_id: str, message: RoomMessage) -> None:
    recorder.record(
        session_id,
        message.name,
        "room_message_sent",
        room_id=room_id,
        message_id=message.message_id,
        recipients=message.at,
        message=message.model_dump(mode="json"),
    )
