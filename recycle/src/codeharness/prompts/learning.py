from __future__ import annotations

from ..models import Prompt, Task
from .base import BasePromptBuilder


class LearningPromptBuilder(BasePromptBuilder):
    def build(self, task: Task) -> Prompt:
        return self.build_prompt(
            "You are a careful learning assistant.",
            f"# Task\n\n{task.description}",
        )
