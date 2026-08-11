"""Deliver App events to ROOM resources without App-specific branches."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ...core.events import AppEvent, EventDelivery
from ..room import Room, RoomMessage


class RoomEventDispatcher:
    def dispatch(
        self,
        events: Iterable[AppEvent],
        deliveries: Iterable[EventDelivery],
        *,
        rooms: Mapping[str, Room],
    ) -> None:
        indexed = {event.event_id: event for event in events}
        for delivery in deliveries:
            event = indexed.get(delivery.event_id)
            if event is None:
                raise KeyError(f"Delivery references unknown event: {delivery.event_id}")
            room = rooms.get(delivery.room_key)
            if room is None:
                raise KeyError(f"Delivery references unknown ROOM key: {delivery.room_key}")
            room.send(RoomMessage(name=event.source, at=delivery.recipient, txt=event.content))
