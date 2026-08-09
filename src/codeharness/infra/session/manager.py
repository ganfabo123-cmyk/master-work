"""Generic session and trace lifecycle management."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..room import Room
from ..trace import TraceRecorder


class SessionManager:
    """Own durable session metadata, traces, and ROOM persistence roots."""

    def __init__(self, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data")) -> None:
        self.trace = TraceRecorder(traces_root)
        self.room_data_root = room_data_root
        self._rooms: dict[tuple[str, str], Room] = {}

    def has_session(self, session_id: str) -> bool:
        return (self.trace.root / session_id / "session.json").exists()

    def create_room(self, room_id: str, *, session_id: str) -> Room:
        key = (session_id, room_id)
        if key in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id} ({session_id})")
        room = Room(room_id, session_id=session_id, data_root=self.room_data_root, **self._room_callbacks(session_id))
        self._rooms[key] = room
        if self.has_session(session_id):
            self.trace.attach_room(session_id, room_id=room.room_id, room_session_id=room.session_id)
        return room

    def resume_room(self, room_id: str, *, session_id: str) -> Room:
        key = (session_id, room_id)
        if key in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id} ({session_id})")
        room = Room.resume(room_id, session_id=session_id, data_root=self.room_data_root, **self._room_callbacks(session_id))
        self._rooms[key] = room
        return room

    def _room_callbacks(self, session_id: str) -> dict[str, Callable[..., object]]:
        if not self.has_session(session_id):
            return {}
        return {
            "message_recorder": lambda room_id, message: self.trace.record_room_message(session_id, room_id, message),
            "message_loader": lambda message_id: self.trace.room_message(session_id, message_id),
            "message_replayer": lambda room_id: self.trace.room_messages(session_id, room_id),
        }
