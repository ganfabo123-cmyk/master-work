"""Base Policy composed from one Prompt Builder and one tool set."""

from __future__ import annotations

from ..infra.prompt import BasePromptBuilder
from ..infra.tools import BaseAgentTools


class BasePolicy:
    """Contain one replaceable Prompt Builder and one Policy tool set."""

    def __init__(
        self,
        *,
        prompt_builder: BasePromptBuilder,
        tools: BaseAgentTools,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.tools = tools
