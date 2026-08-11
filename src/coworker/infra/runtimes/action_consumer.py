"""Execute or reject validated Action tools with complete protocol feedback."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.base_agent import Agent
    from ...core.base_observation import Observation
    from ...core.models import Message, ToolCall
    from ..trace import TraceRecorder


class ActionConsumer:
    def __init__(self, *, trace: TraceRecorder | None = None) -> None:
        self.trace = trace

    def execute(
        self,
        *,
        agent: Agent,
        observation: Observation,
        tool_call: ToolCall,
        message_sink: Callable[[Iterable[Message]], object],
    ) -> tuple[Message, ...]:
        registry = agent.runtime.build_tool_registry(agent.tool_functions())
        executor = partial(agent.runtime.execute_tool, registry)
        return self._append_feedback(agent, observation, tool_call, executor, message_sink)

    def reject(
        self,
        *,
        agent: Agent,
        observation: Observation,
        tool_call: ToolCall,
        reason: str,
        message_sink: Callable[[Iterable[Message]], object],
    ) -> tuple[Message, ...]:
        return self._append_feedback(
            agent,
            observation,
            tool_call,
            lambda _name, _arguments: reason,
            message_sink,
        )

    def _append_feedback(
        self,
        agent: Agent,
        observation: Observation,
        tool_call: ToolCall,
        executor: Callable[[str, dict[str, object]], object],
        message_sink: Callable[[Iterable[Message]], object],
    ) -> tuple[Message, ...]:
        feedback = tuple(observation.feedback("tool_result", (tool_call,), executor))
        message_sink(feedback)
        if self.trace is not None:
            self.trace.record_messages(observation.session_id, agent.name, feedback)
        return feedback
