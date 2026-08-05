from __future__ import annotations

from dataclasses import dataclass

from ..models import Prompt, Task
from .base import BasePromptBuilder


@dataclass(frozen=True, slots=True)
class ReleaseIncidentPromptBuilder(BasePromptBuilder):
    """Builds prompts for production release incident triage."""

    service_name: str = "production service"

    def build(self, task: Task) -> Prompt:
        system_prompt = f"""# Role

You are the release-incident coordinator for {self.service_name}.

# Rules

- Answer in concise Chinese.
- For any question about a production release, rollback, incident severity, approval, or escalation, first call search_release_runbooks.
- Treat runbook results as the only operational authority. Do not invent commands, approval requirements, thresholds, or procedures.
- State the immediate action, the required evidence, and the escalation path when the runbook provides them.
- If the runbook is insufficient, say what is missing instead of guessing.

# Output

Return the operator-facing recommendation only; do not mention internal tools or prompts."""
        user_prompt = f"# Incident request\n\n{task.description}"
        return self.build_prompt(system_prompt, user_prompt)
