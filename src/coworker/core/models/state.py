from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .message import Message
from .task import Task


@dataclass(slots=True)
class AgentState:
    task: Task
    messages: list[Message] = field(default_factory=list)
    turn_count: int = 0
    status: Literal["running", "completed", "failed"] = "running"
    final_result: Any = None
    error: str | None = None
