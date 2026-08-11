from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .tool import ToolCall


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["developer", "user", "assistant", "tool"]
    content: Any
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            data["name"] = self.name
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            data["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
                for call in self.tool_calls
            ]
        return data


@dataclass(frozen=True, slots=True)
class Prompt:
    messages: tuple[Message, ...]
