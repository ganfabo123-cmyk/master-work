"""LLM-backed AI Berkshire team members."""

from __future__ import annotations

from ...core.base_agent import Agent, PromptBuilder
from ...infra.client import LLMClient
from .action import InvestmentAction
from .policy import InvestmentPolicy
from .state import InvestmentRole
from .web_search import BaiduWebSearchClient, BaiduWebSearchTools


class InvestmentAgent(Agent):
    def __init__(self, llm: LLMClient, model: str, *, name: str, role: InvestmentRole, search_client: BaiduWebSearchClient) -> None:
        policy = InvestmentPolicy(agent_name=name, role=role)
        action = InvestmentAction(agent_name=name)
        web_tools = None if role is InvestmentRole.LEAD else BaiduWebSearchTools(name, search_client)
        object.__setattr__(self, "web_tools", web_tools)
        super().__init__(
            name=name,
            model=model,
            llm=llm,
            policy=policy,
            action=action,
            temperature=0.2,
            policy_tools=() if web_tools is None else (web_tools,),
            action_tools=(action.tools,),
        )

    def get_prompt_builder(self) -> PromptBuilder:
        return self.policy.prompt_builder.build
