"""Minimal task-state contract for state-action-environment workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BaseState(ABC):
    """Base state carrying task identity and state-transition interfaces."""

    task_id: str
    session_id: str

    @classmethod
    @abstractmethod
    def initial(cls, task_id: str, session_id: str) -> "BaseState":
        """Create the initial state for one task session."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_terminal(self) -> bool:
        """Return whether this state is terminal."""
        raise NotImplementedError

    @abstractmethod
    def process(self, action: object) -> "BaseState":
        """Process one action and return the resulting state."""
        raise NotImplementedError
