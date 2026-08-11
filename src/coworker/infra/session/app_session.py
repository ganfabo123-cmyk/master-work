"""Shared resources held by one synchronous App session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from ...core.base_agent import Agent
    from ...core.base_state import State
    from ..room import Room
    from ..runtimes.context import IncrementalContext
    from ..state_store import StateStore


StateT = TypeVar("StateT", bound="State")


@dataclass(slots=True)
class AppSession(Generic[StateT]):
    session_id: str
    state: StateT
    agents: dict[str, Agent]
    contexts: dict[str, IncrementalContext]
    rooms: dict[str, Room]
    state_store: StateStore
    state_kind: str

    def room(self, key: str) -> Room:
        try:
            return self.rooms[key]
        except KeyError as error:
            raise KeyError(f"App Session has no ROOM resource: {key}") from error

    def persist(self) -> None:
        self.state_store.update(self.session_id, self.state_kind, self.state)
