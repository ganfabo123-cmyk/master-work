"""Observation helpers for LLM message and tool-call protocols."""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

from .models import Message


class SystemSignal:
    """A runtime signal carrying developer-defined keyword arguments."""

    def __init__(self, **kwargs: Any) -> None:
        self.payload = kwargs


class Observation:
    """Build LLM prompts, tool results, and system signals."""

    def __init__(self, observation_id: str, task_id: str, session_id: str) -> None:
        self.observation_id = observation_id
        self.task_id = task_id
        self.session_id = session_id
        self.feedback_types = ("user_prompt", "tool_result", "system_signal")

    def feedback(self, feedback_type: str, *args: object, **kwargs: object) -> object:
        """Dispatch one supported LLM feedback type."""
        if feedback_type not in self.feedback_types:
            available = ", ".join(self.feedback_types)
            raise ValueError(f"Unsupported feedback type {feedback_type!r}; 可用类型：{available}。")

        handler = getattr(self, f"_feedback_{feedback_type}", None)
        if handler is None:
            raise NotImplementedError(f"Feedback type {feedback_type!r} has no implementation")
        return handler(*args, **kwargs)

    def _feedback_user_prompt(self, text: str) -> Message:
        """Convert text into one user-role Message."""
        return Message("user", text)

    def _feedback_tool_result(
        self,
        tool_calls: Any,
        tool_executor: Callable[[str, dict[str, Any]], Any],
    ) -> list[Message]:
        """Execute Tool Calls and convert them into Tool Result messages."""
        results: list[Message] = []
        for raw_call in tool_calls or ():
            if isinstance(raw_call, dict):
                function = raw_call.get("function", raw_call)
                call_id = raw_call.get("id")
                tool_name = function.get("name")
                arguments = function.get("arguments", {})
            else:
                call_id = getattr(raw_call, "id")
                tool_name = getattr(raw_call, "name")
                arguments = getattr(raw_call, "arguments", {})

            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise TypeError(f"Tool arguments for {tool_name!r} must be a dictionary")

            try:
                value = tool_executor(tool_name, arguments)
            except Exception as error:
                value = str(error)

            results.append(Message("tool", value, name=tool_name, tool_call_id=call_id))
        return results

    def _feedback_system_signal(self, **kwargs: Any) -> SystemSignal:
        """Convert developer-defined keyword arguments into a system signal."""
        return SystemSignal(**kwargs)
