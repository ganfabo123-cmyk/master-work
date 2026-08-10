from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable
from typing import TYPE_CHECKING

from ...core.models import AgentState, Message, Prompt
from ...core.models import Task
from ..trace import TraceRecorder

if TYPE_CHECKING:
    from ...core.base_agent import Agent


class ContextBuilder:
    """Small policy point for deciding what a model sees in one turn."""

    def build(self, *, prompt: Prompt, state: AgentState, skill_content: str | None) -> list[Message]:
        messages = list(prompt.messages)
        if skill_content:
            messages.insert(1, Message("developer", skill_content))
        return [*messages, *state.messages]


@dataclass(slots=True)
class IncrementalContext:
    """The append-only model message stream for one Agent session."""

    messages: list[Message] = field(default_factory=list)

    @classmethod
    def restore_or_initialize(
        cls,
        *,
        restored_messages: Iterable[Message],
        initial_messages: Iterable[Message],
    ) -> tuple["IncrementalContext", tuple[Message, ...]]:
        restored = list(restored_messages)
        if restored:
            return cls(restored), ()
        initial = tuple(initial_messages)
        return cls(list(initial)), initial

    def append(self, messages: Iterable[Message]) -> tuple[Message, ...]:
        appended = tuple(messages)
        self.messages.extend(appended)
        return appended

    def history(self) -> tuple[Message, ...]:
        return tuple(self.messages)


def open_incremental_context(
    *,
    agent: Agent,
    task: Task,
    session_id: str,
    trace: TraceRecorder,
) -> IncrementalContext:
    """Restore one Agent's message stream or initialize it from its Policy."""
    try:
        restored = trace.messages(session_id, agent.name)
    except KeyError:
        restored = ()
    context, initial = IncrementalContext.restore_or_initialize(
        restored_messages=restored,
        initial_messages=agent.initial_messages(Task(task.description)),
    )
    trace.record_initial_messages(session_id, agent.name, initial)
    return context
