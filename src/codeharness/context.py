from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable

from .models import AgentState, Message, Prompt


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
