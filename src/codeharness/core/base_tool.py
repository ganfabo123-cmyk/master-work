"""Parent class for Agent-owned tool sets."""

from __future__ import annotations

from typing import Any, Callable


class BaseAgentTools:
    """Injects one Agent identity into all tools owned by that Agent."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def tool_functions(self) -> tuple[Callable[..., Any], ...]:
        """Return the model-callable methods exposed by this tool instance."""
        return ()
