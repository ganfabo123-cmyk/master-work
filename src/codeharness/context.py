from __future__ import annotations

from .models import AgentState, Message, Prompt


class ContextBuilder:
    """Small policy point for deciding what a model sees in one turn."""

    def build(self, *, prompt: Prompt, state: AgentState, skill_content: str | None) -> list[Message]:
        messages = list(prompt.messages)
        if skill_content:
            messages.insert(1, Message("developer", skill_content))
        return [*messages, *state.messages]
