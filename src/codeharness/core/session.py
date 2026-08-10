"""Stable protocol for environments executed inside a durable session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .models import AgentResult, Task


@dataclass(frozen=True, slots=True)
class SessionContext:
    """Generic session facts supplied by the runtime to an Environment."""

    session_id: str
    resumed: bool


@runtime_checkable
class SessionEnvironment(Protocol):
    """Environment boundary consumed by the synchronous SessionRuntime."""

    session_mode: str
    entry_agent: str

    def run_session(
        self,
        *,
        task: Task,
        context: SessionContext,
        **options: Any,
    ) -> AgentResult:
        """Run the domain workflow inside an already-opened session."""
        ...
