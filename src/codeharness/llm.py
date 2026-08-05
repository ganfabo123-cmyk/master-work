from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import Message, ModelResult, ToolCall


class LLMClient(Protocol):
    """Replace this boundary only when adopting a real model provider."""

    def generate(self, *, model: str, messages: Sequence[Message], tools: list[dict]) -> ModelResult: ...


class DemoLLMClient:
    """Deterministic local client that demonstrates one tool round-trip."""

    def generate(self, *, model: str, messages: Sequence[Message], tools: list[dict]) -> ModelResult:
        if not any(message.role == "tool" for message in messages):
            task = next(message.content for message in messages if message.role == "user")
            return ModelResult(raw_content={"tool": "inspect_task"}, tool_calls=(ToolCall("demo-call-1", "inspect_task", {"task": task}),), model=model, finish_reason="tool_calls")
        observation = next(message.content for message in reversed(messages) if message.role == "tool")
        return ModelResult(raw_content=observation, parsed_content=f"Completed demo run. {observation}", model=model, finish_reason="stop")
