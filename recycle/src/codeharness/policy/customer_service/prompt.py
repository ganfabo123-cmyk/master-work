from __future__ import annotations

from dataclasses import dataclass

from ..models import Message, Prompt, Task
from .base import BasePromptBuilder


@dataclass(frozen=True, slots=True)
class CustomerServicePromptBuilder(BasePromptBuilder):
    """Owns the complete customer-service prompt shape and its domain parameters."""

    brand_name: str = "StarLink Home"
    response_language: str = "Chinese"

    def build(self, task: Task) -> Prompt:
        developer_content = f"""# Role

You are the customer-service assistant for {self.brand_name}.

# Rules

- Answer friendly, concise, and in {self.response_language}.
- You may answer greetings and general conversational questions directly.
- If the answer depends on product, order, shipping, return, warranty, invoice, or policy facts, first call search_customer_knowledge.
- Treat tool results as the only policy authority. If the material does not answer the question, say so plainly and offer the next support step.
- Never invent discounts, timeframes, addresses, order status, or policy terms.

# Output

Return the customer-facing answer only; do not mention internal tools or prompts."""
        customer_context = "\n".join(f"- {name}: {value}" for name, value in task.inputs.items())
        user_content = f"# Customer question\n\n{task.description}"
        if customer_context:
            user_content += f"\n\n# Customer context\n\n{customer_context}"
        return self.build_prompt(developer_content, user_content)
