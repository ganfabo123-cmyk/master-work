"""Base observation interfaces for LLM and runtime-facing inputs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Message


class SystemSignal:
    """A runtime signal carrying developer-defined keyword arguments."""

    def __init__(self, **kwargs: Any) -> None:
        self.payload = kwargs


class BaseObservation(ABC):
    """Build the three input formats accepted by the current Agent runtime."""

    def __init__(self, observation_id: str, task_id: str, session_id: str) -> None:
        self.observation_id = observation_id
        self.task_id = task_id
        self.session_id = session_id

    def user_prompt(self, text: str) -> Message:
        """Convert text into one user-role Message."""
        return Message("user", text)

    def tool_result(self, tool_calls: Any) -> Any:
        """Convert a Tool Calls protocol payload into a Tool Result."""
        pass

    @abstractmethod
    def system_signal(self, **kwargs: Any) -> SystemSignal:
        """Convert developer-defined keyword arguments into a system signal."""
        raise NotImplementedError
