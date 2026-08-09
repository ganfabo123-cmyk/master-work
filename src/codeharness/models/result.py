from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .tool import ToolCall


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


@dataclass(frozen=True, slots=True)
class AgentResult:
    status: Literal["completed", "failed"]
    content: Any
    error: str | None
    session_id: str
