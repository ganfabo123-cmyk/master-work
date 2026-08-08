"""Two role-specific Agents for the explicit release-incident ROOM scenario."""

from __future__ import annotations

from ..base_agent import LLMAgent
from ..llm import LLMClient
from ..prompts.release_incident_collaboration import IncidentPlannerPromptBuilder, RiskReviewerPromptBuilder
from ..tools import IncidentPlannerTools, RiskReviewerTools


class IncidentPlannerAgent(LLMAgent):
    """Proposes and revises release-incident actions using approved runbooks."""

    def __init__(self, llm: LLMClient, model: str) -> None:
        super().__init__(
            name="incident-planner",
            model=model,
            llm=llm,
            prompt_builder=IncidentPlannerPromptBuilder().build,
            tools=(IncidentPlannerTools("incident-planner"),),
        )


class RiskReviewerAgent(LLMAgent):
    """Independently checks a Planner proposal before it becomes a final recommendation."""

    def __init__(self, llm: LLMClient, model: str) -> None:
        super().__init__(
            name="risk-reviewer",
            model=model,
            llm=llm,
            prompt_builder=RiskReviewerPromptBuilder().build,
            tools=(RiskReviewerTools("risk-reviewer"),),
        )
