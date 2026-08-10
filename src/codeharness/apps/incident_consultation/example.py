"""Stable direct entry for the incident-consultation application."""

from __future__ import annotations

from ...core.models import AgentResult, Task
from ...infra.runtimes import SessionRuntime
from .environment import IncidentConsultationEnvironment, IncidentWorkflowConfig


def run_incident_consultation(environment: IncidentConsultationEnvironment, *, task: Task, session_id: str | None = None, config: IncidentWorkflowConfig | None = None) -> AgentResult:
    return SessionRuntime(trace=environment.session.trace).run(
        environment,
        task=task,
        session_id=session_id,
        config=config,
    )


__all__ = ["run_incident_consultation"]
