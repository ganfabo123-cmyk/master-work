"""Domain-neutral event facts and delivery instructions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AppEvent:
    event_id: str
    event_type: str
    source: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EventDelivery:
    event_id: str
    room_key: str
    recipient: str | tuple[str, ...] = "all"
    private: bool = False
