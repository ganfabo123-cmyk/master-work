"""Environment contract for LLM Agent workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from .base_agent import Agent
from .base_observation import Observation
from .base_rl import BaseRL
from .base_state import State
from ..infra.trace import TraceRecorder


class ActionManager(ABC):
    @abstractmethod
    def resolve_action(self, response: Any) -> Any:
        """Convert an Agent response into a structured environment action."""
        raise NotImplementedError

    @abstractmethod
    def validate_action(self, action: Any, state: State) -> bool:
        """Return whether an action is valid for the current State."""
        raise NotImplementedError

    @abstractmethod
    def available_actions(self, state: State, agent: Agent) -> Sequence[Any]:
        """Return the actions available to one Agent for the current State."""
        raise NotImplementedError


class Environment(BaseRL, ABC):
    """Own the LLM Agents, State, and Observation of one environment."""

    def __init__(self, agents: Sequence[Agent], state: State, observation: Observation, *, trace: TraceRecorder | None = None) -> None:
        self.agents = tuple(agents)
        self.state = state
        self.observation = observation
        self.trace = trace

    def record_trace(self, session_id: str, agent_name: str, event_type: str, **payload: object) -> None:
        if self.trace is not None:
            self.trace.record(session_id, agent_name, event_type, **payload)

    def record_trace_messages(self, session_id: str, agent_name: str, messages: Sequence[Any]) -> None:
        if self.trace is not None:
            self.trace.record_messages(session_id, agent_name, messages)

    def record_initial_trace(self, session_id: str, agent_name: str, messages: Sequence[Any]) -> None:
        if self.trace is not None:
            self.trace.record_initial_messages(session_id, agent_name, messages)

    def record_room_inbox(self, session_id: str, agent_name: str, rooms: dict[str, tuple[str, ...]]) -> None:
        if self.trace is not None:
            self.trace.record_room_inbox(session_id, agent_name, rooms)

    def record_agent_error(self, session_id: str, agent_name: str, *, stage: str, error: str) -> None:
        if self.trace is not None:
            self.trace.record_agent_error(session_id, agent_name, stage=stage, error=error)

    def finish_trace(self, session_id: str, status: str, error: str | None = None) -> None:
        if self.trace is not None:
            self.trace.finish_session(session_id, status, error)

    @abstractmethod
    def orchestrate_agents(self) -> Any:
        """Coordinate the Agents participating in this environment."""
        raise NotImplementedError
