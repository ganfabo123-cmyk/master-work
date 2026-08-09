"""Generic environment contract for State-Observation-Agent workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from ...protocol.base_observation import BaseObservation
from ...protocol.base_state import BaseState


class BaseEnvironment(ABC):
    """Own the concrete Agents, State, and Observation of one environment."""

    def __init__(self, agents: Sequence[Any], state: BaseState, observation: BaseObservation) -> None:
        self.agents = tuple(agents)
        self.state = state
        self.observation = observation

    @abstractmethod
    def orchestrate_agents(self) -> Any:
        """Coordinate the Agents participating in this environment."""
        raise NotImplementedError

    @abstractmethod
    def execute_action(self, action: Any) -> Any:
        """Validate and execute one Action, then return its result."""
        raise NotImplementedError
