"""LLM-backed incident experts built from the shared Agent base."""

from __future__ import annotations

from ...core.base_agent import Agent, PromptBuilder
from ...infra.client import LLMClient
from ...infra.room import Room
from .action import IncidentAction
from .policy import IncidentPolicy
from .state import ExpertRole


class IncidentExpertAgent(Agent):
    def __init__(self, llm: LLMClient, model: str, *, name: str, role: ExpertRole, room: Room) -> None:
        policy = IncidentPolicy(expert_name=name, role=role)
        action = IncidentAction(agent_name=name, room=room)
        super().__init__(name=name, model=model, llm=llm, policy=policy, action=action, temperature=0.2, action_tools=(action.tools,))

    def get_prompt_builder(self) -> PromptBuilder:
        return self.policy.prompt_builder.build
