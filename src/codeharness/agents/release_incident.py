from __future__ import annotations

from ..base_agent import LLMAgent
from ..llm import LLMClient
from ..prompts.release_incident import ReleaseIncidentPromptBuilder
from ..tools import ReleaseIncidentTools


class ReleaseIncidentAgent(LLMAgent):
    """Single Agent Harness for production release incident triage."""

    def __init__(self, llm: LLMClient, model: str) -> None:
        super().__init__(
            name="release-incident",
            model=model,
            llm=llm,
            prompt_builder=ReleaseIncidentPromptBuilder().build,
            tools=(ReleaseIncidentTools("release-incident"),),
        )
