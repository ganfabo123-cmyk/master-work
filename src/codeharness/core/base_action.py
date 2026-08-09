"""Base Action and Action type markers."""

from __future__ import annotations

from dataclasses import dataclass

from ..infra.tools import BaseAgentTools


class ToolAction:
    """Mark an Action produced by a Tool Call."""


class RawContentAction:
    """Mark an Action produced by raw model content."""


@dataclass(frozen=True, slots=True)
class Action:
    """Describe one named Action and how Environment should process it."""

    name: str
    type: type[ToolAction] | type[RawContentAction]


class BaseAction:
    """Contain Action tools and the explicit name-to-Action mapping."""

    def __init__(self, *, tools: BaseAgentTools) -> None:
        self.tools = tools
        self.tool_action_map: dict[str, Action] = {}

    def get_action(self, name: str) -> Action:
        """Return the Action mapped from a Tool name or ``raw content``."""
        return self.tool_action_map[name]
