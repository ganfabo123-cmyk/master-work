from __future__ import annotations

from pydantic import BaseModel

from .base import Agent
from ..llm import LLMClient
from ..prompts.release_incident import ReleaseIncidentPromptBuilder
from ..tools import search_release_runbooks


class ReleaseIncidentOutput(BaseModel):
    recommendation: str


class ReleaseIncidentAgent(Agent):
    """Single Agent Harness for production release incident triage."""

    def __init__(self, llm: LLMClient, model: str) -> None:
        super().__init__(
            name="release-incident",
            model=model,
            llm=llm,
            prompt_builder=ReleaseIncidentPromptBuilder().build,
            tools=(search_release_runbooks,),
            output_format=ReleaseIncidentOutput,
        )
