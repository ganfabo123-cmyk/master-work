from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...core.models import Message
from .models import RoomMessage

if TYPE_CHECKING:
    from .room import Room


@dataclass(frozen=True, slots=True)
class RoomTurnContext:
    """Generic, one-turn view of all ROOM messages delivered to an Agent."""

    session_id: str
    room: Room
    additional_rooms: tuple[Room, ...]
    inboxes: dict[str, tuple[RoomMessage, ...]]

    @classmethod
    def receive(cls, *, session_id: str, room: Room, additional_rooms: tuple[Room, ...], agent_name: str) -> "RoomTurnContext":
        rooms = (room, *additional_rooms)
        return cls(
            session_id=session_id,
            room=room,
            additional_rooms=additional_rooms,
            inboxes={active_room.room_id: active_room.receive(agent_name) for active_room in rooms},
        )

    def task_inputs(self) -> dict[str, Any]:
        rooms = (self.room, *self.additional_rooms)
        room_inputs = {
            active_room.room_id: {
                "room_id": active_room.room_id,
                "session_id": active_room.session_id,
                "inbox": [message.model_dump(mode="json") for message in self.inboxes[active_room.room_id]],
            }
            for active_room in rooms
        }
        return {"room": room_inputs[self.room.room_id], "rooms": room_inputs}

    def room_message_events(self) -> tuple[Message, ...]:
        events: list[Message] = []
        for active_room in (self.room, *self.additional_rooms):
            for message in self.inboxes[active_room.room_id]:
                events.append(
                    Message(
                        "user",
                        json.dumps(
                            {
                                "type": "room_message",
                                "room_id": active_room.room_id,
                                "sender": message.name,
                                "recipients": message.at,
                                "content": {"txt": message.txt, "image": message.image, "audio": message.audio},
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
        return tuple(events)
