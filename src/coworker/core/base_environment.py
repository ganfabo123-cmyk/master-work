"""Environment contract for LLM Agent workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from .base_agent import Agent
from .base_observation import Observation
from .base_rl import BaseRL
from .base_state import State
from .models import Message, ToolCall
from ..infra.trace import TraceRecorder
from ..infra.runtimes.action_consumer import ActionConsumer


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

    @abstractmethod
    def resolve_actions(self, state: State, actions: object) -> Any:
        """Resolve collected Actions into the input consumed by Environment.step()."""
        raise NotImplementedError


class Environment(BaseRL, ABC):
    """Own the LLM Agents, State, and Observation of one environment."""

    def __init__(self, agents: Sequence[Agent], state: State, observation: Observation, *, trace: TraceRecorder | None = None) -> None:
        self.agents = tuple(agents)
        self.state = state
        self.observation = observation
        self.trace = trace
        self.action_consumer = ActionConsumer(trace=trace)

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

    def execute_tool_action(
        self,
        *,
        agent: Agent,
        observation: Observation,
        tool_call: ToolCall,
        message_sink: Callable[[Iterable[Message]], object],
    ) -> tuple[Message, ...]:
        """Execute one validated ToolAction and return its pure Observation feedback."""
        return self.action_consumer.execute(
            agent=agent,
            observation=observation,
            tool_call=tool_call,
            message_sink=message_sink,
        )

    def reject_tool_action(
        self,
        *,
        agent: Agent,
        observation: Observation,
        tool_call: ToolCall,
        reason: str,
        message_sink: Callable[[Iterable[Message]], object],
    ) -> tuple[Message, ...]:
        """Pair one rejected ToolAction without executing its Tool function."""
        return self.action_consumer.reject(
            agent=agent,
            observation=observation,
            tool_call=tool_call,
            reason=reason,
            message_sink=message_sink,
        )

    def before_cycle(self, state: State) -> Sequence[Any]:
        """Return events emitted before participants act in one cycle."""
        return ()

    def resolve_collected_actions(self, state: State, actions: dict[str, Any]) -> Any:
        """Resolve a domain-neutral actor-to-Action collection for step()."""
        manager = getattr(self, "action_manager", None)
        if manager is None:
            raise RuntimeError("Environment has no ActionManager")
        return manager.resolve_actions(state, actions)

    def after_transition(self, old_state: State, actions: Any, new_state: State) -> State:
        """Run optional App bookkeeping after step() and before persistence."""
        return new_state

    def dispatch_events(self, events: Sequence[Any]) -> None:
        """Deliver App-built events through its configured infrastructure."""
        if events:
            raise NotImplementedError("Environment must dispatch non-empty events")

    @abstractmethod
    def select_agents(self, state: State) -> Sequence[Agent]:
        """Return the Agents that act for the current State."""
        raise NotImplementedError

    @abstractmethod
    def ready_to_step(self, state: State, actions: object) -> bool:
        """Return whether the collected Actions are ready for one State transition."""
        raise NotImplementedError

    @abstractmethod
    def build_events(self, old_state: State, actions: object, new_state: State) -> Sequence[Any]:
        """Build feedback events from one completed State transition."""
        raise NotImplementedError

    @abstractmethod
    def orchestrate_agents(self) -> Any:
        """Coordinate the Agents participating in this environment."""
        raise NotImplementedError
