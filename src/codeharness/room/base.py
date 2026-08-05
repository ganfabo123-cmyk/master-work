"""The minimal ROOM collaboration protocol and in-memory message routing."""

from __future__ import annotations

from pathlib import Path

from .models import AgentProfile, RoomMessage
from .registry import RoomAgentRegistry


class Room:
    """ROOM base: registration, membership, append-only history, and inbox routing."""

    def __init__(self, room_id: str, *, session_id: str | None = None, data_root: Path = Path("room/data")) -> None:
        self.room_id = _normalize_name(room_id, "room_id")
        self.session_id = _normalize_name(session_id or room_id, "session_id")
        self.registry = RoomAgentRegistry(data_root, self.session_id)
        self._participants: set[str] = set()
        self._messages: list[RoomMessage] = []
        self._inboxes: dict[str, list[RoomMessage]] = {}

    def register(self, profile: AgentProfile) -> None:
        """Persist one Agent profile for this ROOM session without inviting it yet."""
        self.registry.save(profile)

    def invite(self, name: str) -> AgentProfile:
        """Invite one registered Agent into this ROOM and create its inbox."""
        profile = self.registry.load(name)
        self._participants.add(profile.name)
        self._inboxes.setdefault(profile.name, [])
        return profile

    def leave(self, name: str) -> None:
        """Remove a participant; previously sent messages remain in history."""
        self._participants.discard(_normalize_name(name, "participant name"))

    def send(self, message: RoomMessage) -> None:
        """Append one valid message and route it into every addressed inbox."""
        if message.name not in self._participants:
            raise ValueError(f"participant is not in ROOM '{self.room_id}': {message.name}")
        recipients = self._recipients(message.at)
        self._messages.append(message)
        for recipient in recipients:
            self._inboxes[recipient].append(message)

    def receive(self, name: str) -> tuple[RoomMessage, ...]:
        """Return and clear pending messages addressed to one ROOM participant."""
        participant = _normalize_name(name, "participant name")
        if participant not in self._participants:
            raise ValueError(f"participant is not in ROOM '{self.room_id}': {participant}")
        messages = tuple(self._inboxes[participant])
        self._inboxes[participant].clear()
        return messages

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


def _normalize_name(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized
