"""Persistent ROOM collaboration protocol and message routing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import AgentProfile, RoomMessage
from .registry import RoomAgentRegistry


class Room:
    """ROOM base: profiles, membership, durable history, and per-Agent inboxes."""

    def __init__(self, room_id: str, *, session_id: str | None = None, data_root: Path = Path("room/data")) -> None:
        self.room_id = _normalize_name(room_id, "room_id")
        self.session_id = _normalize_name(session_id or room_id, "session_id")
        self.registry = RoomAgentRegistry(data_root, self.session_id)
        self._participants: set[str] = set()
        self._messages: list[RoomMessage] = []
        self._inboxes: dict[str, list[RoomMessage]] = {}
        self._status = "open"
        if not self._state_path.exists():
            self._persist_state()
            self._record_event("room_created")

    @classmethod
    def resume(cls, room_id: str, *, session_id: str, data_root: Path = Path("room/data")) -> "Room":
        """Restore ROOM membership, history, and unconsumed inboxes from disk."""
        normalized_session_id = _normalize_name(session_id, "session_id")
        state_path = data_root / f"room_{normalized_session_id}.json"
        if not state_path.exists():
            raise KeyError(f"ROOM state does not exist: {room_id} ({normalized_session_id})")
        room = cls(room_id, session_id=session_id, data_root=data_root)
        data = json.loads(room._state_path.read_text(encoding="utf-8"))
        if data.get("room_id") != room.room_id or data.get("session_id") != room.session_id:
            raise ValueError("ROOM state identity does not match the requested room")
        room._participants = set(data.get("participants", []))
        room._messages = [RoomMessage.model_validate(message) for message in data.get("messages", [])]
        room._inboxes = {
            name: [RoomMessage.model_validate(message) for message in messages]
            for name, messages in data.get("inboxes", {}).items()
        }
        room._status = data.get("status", "open")
        room._record_event("room_resumed")
        return room

    def register(self, profile: AgentProfile) -> None:
        """Persist one Agent profile for this ROOM session without inviting it yet."""
        self._require_open()
        self.registry.save(profile)
        self._record_event("agent_registered", agent_name=profile.name)

    def invite(self, name: str) -> AgentProfile:
        """Invite one registered Agent into this ROOM and create its inbox."""
        self._require_open()
        profile = self.registry.load(name)
        self._participants.add(profile.name)
        self._inboxes.setdefault(profile.name, [])
        self._persist_state()
        self._record_event("agent_invited", agent_name=profile.name)
        return profile

    def leave(self, name: str) -> None:
        """Remove a participant; previously sent messages remain in history."""
        self._require_open()
        participant = _normalize_name(name, "participant name")
        self._participants.discard(participant)
        self._inboxes.pop(participant, None)
        self._persist_state()
        self._record_event("agent_left", agent_name=participant)

    def send(self, message: RoomMessage) -> None:
        """Append one valid message and route it into every addressed inbox."""
        self._require_open()
        if message.name not in self._participants:
            raise ValueError(f"participant is not in ROOM '{self.room_id}': {message.name}")
        recipients = self._recipients(message.at)
        self._messages.append(message)
        for recipient in recipients:
            self._inboxes[recipient].append(message)
        self._persist_state()
        self._record_event(
            "message_sent",
            message_id=message.message_id,
            sender=message.name,
            at=message.at,
            recipients=recipients,
        )

    def receive(self, name: str) -> tuple[RoomMessage, ...]:
        """Return and clear pending messages addressed to one ROOM participant."""
        participant = _normalize_name(name, "participant name")
        if participant not in self._participants:
            raise ValueError(f"participant is not in ROOM '{self.room_id}': {participant}")
        messages = tuple(self._inboxes[participant])
        self._inboxes[participant].clear()
        self._persist_state()
        self._record_event("messages_received", agent_name=participant, message_ids=tuple(message.message_id for message in messages))
        return messages

    def close(self) -> None:
        """Close this ROOM after its workflow has finished; persisted data remains readable."""
        self._status = "closed"
        self._persist_state()
        self._record_event("room_closed")

    @property
    def is_closed(self) -> bool:
        return self._status == "closed"

    def registered_agents(self) -> tuple[AgentProfile, ...]:
        """Return persisted profiles registered for this ROOM session."""
        return self.registry.list()

    def participants(self) -> tuple[str, ...]:
        """Return current participant names in a stable order."""
        return tuple(sorted(self._participants))

    def history(self) -> tuple[RoomMessage, ...]:
        """Return immutable history in delivery order."""
        return tuple(self._messages)

    def _recipients(self, at: str) -> tuple[str, ...]:
        if at == "all":
            return self.participants()
        if at not in self._participants:
            raise ValueError(f"recipient is not in ROOM '{self.room_id}': {at}")
        return (at,)

    @property
    def _state_path(self) -> Path:
        return self.registry.data_root / f"room_{self.session_id}.json"

    @property
    def _events_path(self) -> Path:
        return self.registry.data_root / f"room_{self.session_id}.events.jsonl"

    def _persist_state(self) -> None:
        state = {
            "schema_version": 1,
            "room_id": self.room_id,
            "session_id": self.session_id,
            "status": self._status,
            "participants": sorted(self._participants),
            "messages": [message.model_dump(mode="json") for message in self._messages],
            "inboxes": {
                name: [message.model_dump(mode="json") for message in messages]
                for name, messages in sorted(self._inboxes.items())
            },
        }
        self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _record_event(self, event_type: str, **payload: Any) -> None:
        event = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "event_type": event_type,
            "room_id": self.room_id,
            "session_id": self.session_id,
            **payload,
        }
        with self._events_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _require_open(self) -> None:
        if self.is_closed:
            raise RuntimeError(f"ROOM is closed: {self.room_id}")


def _normalize_name(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized
