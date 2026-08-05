from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from ..models import Message, Prompt, Task

PromptBuilder = Callable[..., Prompt]
F = TypeVar("F", bound=PromptBuilder)


def prompt(fn: F) -> F:
    """Marks a function as the single source of one logical prompt."""
    return fn


@prompt
def build_task_prompt(task: Task, system_prompt: str) -> Prompt:
    """Minimal generic prompt; domain templates can replace this builder."""
    inputs = "\n".join(f"- {key}: {value}" for key, value in task.inputs.items())
    user_content = f"# Task\n\n{task.description}"
    if inputs:
        user_content += f"\n\n# Inputs\n\n{inputs}"
    return Prompt((Message("developer", system_prompt), Message("user", user_content)))
