from __future__ import annotations

from codeharness.core.models import Message, Prompt


class BasePromptBuilder:
    """Only turns already-built system and user prompts into a Prompt object."""
    def __init__(self):
        pass
    
    def build_prompt(self, system_prompt: str, user_prompt: str) -> Prompt:
        return Prompt((
            Message("developer", system_prompt),
            Message("user", user_prompt),
        ))
