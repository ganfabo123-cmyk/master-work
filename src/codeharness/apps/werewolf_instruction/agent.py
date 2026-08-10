"""LLM participants for the werewolf instruction discussion."""

from __future__ import annotations

from ...core.base_agent import Agent, PromptBuilder
from ...infra.client import LLMClient
from ...infra.room import Room
from .action import WerewolfInstructionAction
from .policy import WerewolfInstructionPolicy


class WerewolfInstructionAgent(Agent):
    def __init__(self, llm: LLMClient, model: str, *, name: str, room: Room) -> None:
        policy = WerewolfInstructionPolicy(name)
        action = WerewolfInstructionAction(agent_name=name, room=room)
        super().__init__(name=name, model=model, llm=llm, policy=policy, action=action, temperature=0.7, action_tools=(action.tools,))

    def get_prompt_builder(self) -> PromptBuilder:
        return self.policy.prompt_builder.build
