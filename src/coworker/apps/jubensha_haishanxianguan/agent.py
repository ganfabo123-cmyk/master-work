from __future__ import annotations

from ...core.base_agent import Agent
from ...infra.client import LLMClient
from .action import HaishanAction, HaishanActionTools
from .data_loader import ROLE_NAMES
from .policy import HaishanPolicy, HaishanPromptBuilder


class HaishanAgent(Agent):
    pass


def build_agents(*, llm: LLMClient, model: str, temperature: float = 0.2) -> tuple[Agent, ...]:
    agents: list[Agent] = []
    for role_id, role_name in ROLE_NAMES.items():
        tools = HaishanActionTools(role_id)
        action = HaishanAction(tools)
        policy = HaishanPolicy(prompt_builder=HaishanPromptBuilder(role_name), tools=tools)
        agents.append(
            HaishanAgent(
                name=role_id,
                model=model,
                llm=llm,
                policy=policy,
                action=action,
                temperature=temperature,
                action_tools=(tools,),
            )
        )
    return tuple(agents)
