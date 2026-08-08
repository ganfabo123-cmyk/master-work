from __future__ import annotations

from pathlib import Path

from ..base_agent import LLMAgent, SkillSpec
from ..llm import LLMClient
from ..prompts.customer_service import CustomerServicePromptBuilder
from ..tools import CustomerServiceTools

_ROOT = Path(__file__).resolve().parents[3]

CUSTOMER_SERVICE_SKILL = SkillSpec(
    name="customer-service",
    path=_ROOT / "skills" / "customer-service" / "SKILL.md",
    description="Answer customer questions accurately using local knowledge when facts are needed.",
)


class CustomerServiceAgent(LLMAgent):
    """The complete declaration required to add the customer-service Agent."""

    def __init__(self, llm: LLMClient, model: str) -> None:
        super().__init__(
            name="customer-service",
            model=model,
            llm=llm,
            prompt_builder=CustomerServicePromptBuilder(
                brand_name="StarLink Home",
                response_language="Chinese",
            ).build,
            tools=(CustomerServiceTools("customer-service"),),
            skills=(CUSTOMER_SERVICE_SKILL,),
        )
