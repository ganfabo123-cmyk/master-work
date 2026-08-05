from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["developer", "user", "assistant", "tool"]
    content: Any
    name: str | None = None
    tool_call_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            data["name"] = self.name
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


@dataclass(frozen=True, slots=True)
class Prompt:
    messages: tuple[Message, ...]


@dataclass(frozen=True, slots=True)
class Task:
    description: str
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    model: str
    system_prompt: str
    skill_path: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelResult:
    raw_content: Any
    parsed_content: Any = None
    tool_calls: tuple[ToolCall, ...] = ()
    parse_error: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    duration_ms: float | None = None
    finish_reason: str | None = None


@dataclass(slots=True)
class AgentState:
    task: Task
    messages: list[Message] = field(default_factory=list)
    turn_count: int = 0
    status: Literal["running", "completed", "failed"] = "running"
    final_result: Any = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AgentResult:
    status: Literal["completed", "failed"]
    content: Any
    error: str | None
    session_id: str
    artifact_paths: tuple[str, ...] = ()
