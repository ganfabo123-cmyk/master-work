"""Base Agent contract for policy-driven task execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """An Agent binds a Policy and Action implementation to one model identity."""

    def __init__(self, name: str, model: str, policy: Any, action: Any) -> None:
        self.name = name
        self.model = model
        self.policy = policy
        self.action = action

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run one Agent decision cycle."""
        raise NotImplementedError
