"""Persistent ROOM collaboration protocol and message routing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Any, Callable
from uuid import uuid4

from codeharness.room.models import AgentProfile, RoomMessage
from codeharness.room.registry import RoomAgentRegistry


MessageRecorder = Callable[[str, RoomMessage], None]
MessageLoader = Callable[[str], RoomMessage]
MessageReplayer = Callable[[str], tuple[RoomMessage, ...]]


class Room:
    """A session ROOM whose messages are owned by Agent traces, not its snapshot."""

    def __init__(
        self,
        room_id: str,
        *,
        session_id: str | None = None,
        data_root: Path = Path("room/data"),
        message_recorder: MessageRecorder | None = None,
        message_loader: MessageLoader | None = None,
        message_replayer: MessageReplayer | None = None,
    ) -> None:
        self.room_id = _normalize_name(room_id, "room_id")
        self.session_id = _normalize_name(session_id or room_id, "session_id")
        self.registry = RoomAgentRegistry(data_root, self.session_id)
        self._data_root = data_root
        self._message_recorder = message_recorder
        self._message_loader = message_loader
        self._message_replayer = message_replayer
        (data_root / self.session_id / "rooms").mkdir(parents=True, exist_ok=True)
        self._participants: set[str] = set()
        self._message_ids: list[str] = []
        self._inboxes: dict[str, list[str]] = {}
        self._status = "open"
        if not self._state_path.exists():
            self._persist_state()
            self._record_event("room_created")

    @classmethod
    def resume(
        cls,
        room_id: str,
        *,
        session_id: str,
        data_root: Path = Path("room/data"),
        message_recorder: MessageRecorder | None = None,
        message_loader: MessageLoader | None = None,
        message_replayer: MessageReplayer | None = None,
    ) -> "Room":
        """Restore ROOM membership, history, and unconsumed inboxes from disk."""
        normalized_session_id = _normalize_name(session_id, "session_id")
        state_path = data_root / normalized_session_id / "rooms" / f"{_normalize_name(room_id, 'room_id')}.json"
        if not state_path.exists():
            raise KeyError(f"ROOM state does not exist: {room_id} ({normalized_session_id})")
        room = cls(
            room_id,
            session_id=session_id,
            data_root=data_root,
            message_recorder=message_recorder,
            message_loader=message_loader,
            message_replayer=message_replayer,
        )
        data = json.loads(room._state_path.read_text(encoding="utf-8"))
        if data.get("room_id") != room.room_id or data.get("session_id") != room.session_id:
            raise ValueError("ROOM state identity does not match the requested room")
        room._participants = set(data.get("participants", []))
        room._message_ids = list(data.get("message_ids", []))
        room._inboxes = {name: list(message_ids) for name, message_ids in data.get("inboxes", {}).items()}
        room._status = data.get("status", "open")
        room._reconcile_message_trace()
        room._record_event("room_resumed")
        return room

    def register(self, profile: AgentProfile) -> None:
        self._require_open()
        self.registry.save(profile)
        self._record_event("agent_registered", agent_name=profile.name)

    def invite(self, name: str) -> AgentProfile:
        self._require_open()
        profile = self.registry.load(name)
        self._participants.add(profile.name)
        self._inboxes.setdefault(profile.name, [])
        self._persist_state()
        self._record_event("agent_invited", agent_name=profile.name)
        return profile

    def leave(self, name: str) -> None:
        self._require_open()
        participant = _normalize_name(name, "participant name")
        self._participants.discard(participant)
        self._inboxes.pop(participant, None)
        self._persist_state()
        self._record_event("agent_left", agent_name=participant)

    def send(self, message: RoomMessage) -> None:
        self._require_open()
        if message.name not in self._participants:
            raise ValueError(f"participant is not in ROOM '{self.room_id}': {message.name}")
        recipients = self._recipients(message.at)
        self._persist_agent_message(message)
        self._message_ids.append(message.message_id)
        for recipient in recipients:
            self._inboxes[recipient].append(message.message_id)
        self._persist_state()
        self._record_event(
            "message_sent",
            message_id=message.message_id,
            sender=message.name,
            at=message.at,
            recipients=recipients,
        )

    def receive(self, name: str) -> tuple[RoomMessage, ...]:
        participant = _normalize_name(name, "participant name")
        if participant not in self._participants:
            raise ValueError(f"participant is not in ROOM '{self.room_id}': {participant}")
        message_ids = tuple(self._inboxes[participant])
        messages = tuple(self._load_message(message_id) for message_id in message_ids)
        self._inboxes[participant].clear()
        self._persist_state()
        self._record_event("messages_received", agent_name=participant, message_ids=message_ids)
        return messages

    def close(self) -> None:
        self._status = "closed"
        self._persist_state()
        self._record_event("room_closed")

    @property
    def is_closed(self) -> bool:
        return self._status == "closed"

    def registered_agents(self) -> tuple[AgentProfile, ...]:
        return self.registry.list()

    def participants(self) -> tuple[str, ...]:
        return tuple(sorted(self._participants))

    def history(self) -> tuple[RoomMessage, ...]:
        return tuple(self._load_message(message_id) for message_id in self._message_ids)

    def _recipients(self, at: str | tuple[str, ...]) -> tuple[str, ...]:
        if at == "all":
            return self.participants()
        recipients = (at,) if isinstance(at, str) else at
        missing = [recipient for recipient in recipients if recipient not in self._participants]
        if missing:
            raise ValueError(f"recipient is not in ROOM '{self.room_id}': {', '.join(missing)}")
        return recipients

    @property
    def _state_path(self) -> Path:
        return self._data_root / self.session_id / "rooms" / f"{self.room_id}.json"

    @property
    def _events_path(self) -> Path:
        return self._data_root / self.session_id / "rooms" / f"{self.room_id}.events.jsonl"

    def _persist_state(self) -> None:
        state = {
            "schema_version": 2,
            "room_id": self.room_id,
            "session_id": self.session_id,
            "status": self._status,
            "participants": sorted(self._participants),
            "message_ids": self._message_ids,
            "inboxes": {name: message_ids for name, message_ids in sorted(self._inboxes.items())},
        }
        _atomic_write_json(self._state_path, state)

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

    def _persist_agent_message(self, message: RoomMessage) -> None:
        if self._message_recorder is not None:
            self._message_recorder(self.room_id, message)
            return
        path = self._local_agent_messages_path(message.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = {"event_type": "room_message_sent", "room_id": self.room_id, "message": message.model_dump(mode="json")}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _load_message(self, message_id: str) -> RoomMessage:
        if self._message_loader is not None:
            return self._message_loader(message_id)
        for message in self._local_room_messages():
            if message.message_id == message_id:
                return message
        raise KeyError(f"ROOM message does not exist: {message_id}")

    def _reconcile_message_trace(self) -> None:
        source_messages = self._message_replayer(self.room_id) if self._message_replayer is not None else self._local_room_messages()
        known = set(self._message_ids)
        changed = False
        for message in source_messages:
            if message.message_id in known:
                continue
            recipients = self._recipients(message.at)
            self._message_ids.append(message.message_id)
            for recipient in recipients:
                self._inboxes.setdefault(recipient, []).append(message.message_id)
            known.add(message.message_id)
            changed = True
        if changed:
            self._persist_state()

    def _local_agent_messages_path(self, agent_id: str) -> Path:
        return self._data_root / self.session_id / "agents" / f"{agent_id}.messages.jsonl"

    def _local_room_messages(self) -> tuple[RoomMessage, ...]:
        messages: list[RoomMessage] = []
        agents_root = self._data_root / self.session_id / "agents"
        for path in sorted(agents_root.glob("*.messages.jsonl")) if agents_root.exists() else ():
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event_type") == "room_message_sent" and event.get("room_id") == self.room_id:
                    messages.append(RoomMessage.model_validate(event["message"]))
        return tuple(messages)


def _normalize_name(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _replace_with_retry(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _replace_with_retry(temporary: Path, destination: Path, *, attempts: int = 8) -> None:
    for attempt in range(attempts):
        try:
            temporary.replace(destination)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            sleep(0.025)
