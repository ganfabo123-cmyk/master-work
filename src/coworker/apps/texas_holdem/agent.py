"""LLM-backed poker player."""

from __future__ import annotations

from ...core.base_agent import Agent, PromptBuilder
from ...infra.client import LLMClient
from .action import PokerAction
from .policy import PokerPolicy


class PokerAgent(Agent):
    def __init__(self, llm: LLMClient, model: str, *, name: str) -> None:
        policy = PokerPolicy(name)
        action = PokerAction(name)
        super().__init__(
            name=name, model=model, llm=llm, policy=policy, action=action,
            temperature=0.4, policy_tools=(policy.tools,), action_tools=(action.tools,),
        )

    def get_prompt_builder(self) -> PromptBuilder:
        return self.policy.prompt_builder.build
