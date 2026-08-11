"""Domain-neutral envelope for Actions produced by participants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .base_observation import Observation
from .models import ToolCall


PayloadT = TypeVar("PayloadT")


@dataclass(frozen=True, slots=True)
class ActionEnvelope(Generic[PayloadT]):
    """Protocol metadata plus an App-owned Action payload."""

    action_id: str
    actor: str
    name: str
    payload: PayloadT
    tool_call: ToolCall
    observation: Observation

    @property
    def message_id(self) -> str:
        """Compatibility alias for App states that track consumed message IDs."""
        return self.action_id
