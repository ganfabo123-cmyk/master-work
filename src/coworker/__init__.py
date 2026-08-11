"""Domain-neutral, learning-oriented Agent Harness template."""

from .core import Agent
from .core.models import AgentResult, Task

__all__ = ["Agent", "AgentResult", "Task"]
