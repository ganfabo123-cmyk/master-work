"""Minimal State contract for RL-style workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class State(ABC):
    """State carrying task identity and terminal-state information."""

    task_id: str
    session_id: str

    @classmethod
    @abstractmethod
    def initial(cls, task_id: str, session_id: str) -> "State":
        """Create the initial state for one task session."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_terminal(self) -> bool:
        """Return whether this state is terminal."""
        raise NotImplementedError
