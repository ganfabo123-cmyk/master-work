"""LLM-backed characters assembled from shared Agent bases."""

from __future__ import annotations

from ...core.base_agent import Agent, PromptBuilder
from ...infra.client import LLMClient
from ...infra.room import Room
from .action import ScriptMurderAction
from .case_loader import Character
from .policy import ScriptMurderPolicy


class ScriptMurderAgent(Agent):
    def __init__(self, llm: LLMClient, model: str, *, name: str, character: Character, public_room: Room, private_room: Room) -> None:
        policy = ScriptMurderPolicy(name, character)
        action = ScriptMurderAction(agent_name=name, public_room=public_room, private_room=private_room)
        super().__init__(name=name, model=model, llm=llm, policy=policy, action=action, temperature=0.7, policy_tools=(policy.tools,), action_tools=(action.tools,))

    def get_prompt_builder(self) -> PromptBuilder:
        return self.policy.prompt_builder.build
