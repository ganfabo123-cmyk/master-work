"""Stable direct entry for the AI Berkshire application."""

from __future__ import annotations

from ...core.models import AgentResult, Task
from ...infra.runtimes import SessionRuntime
from .environment import AIBerkshireEnvironment, InvestmentWorkflowConfig


def run_ai_berkshire(environment: AIBerkshireEnvironment, *, task: Task, config: InvestmentWorkflowConfig | None = None, session_id: str | None = None) -> AgentResult:
    return SessionRuntime(trace=environment.session.trace).run(environment, task=task, session_id=session_id, config=config)


__all__ = ["run_ai_berkshire"]
