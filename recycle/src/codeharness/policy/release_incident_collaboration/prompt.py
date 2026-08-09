"""Prompt builders for an explicit Planner-Reviewer release-incident workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..models import Prompt, Task
from .base import BasePromptBuilder


def _room_inbox(task: Task) -> str:
    """Render only the explicitly supplied ROOM inbox for model inspection."""
    room = task.inputs.get("room", {})
    inbox = room.get("inbox", []) if isinstance(room, dict) else []
    return json.dumps(inbox, ensure_ascii=False, indent=2)


@dataclass(frozen=True, slots=True)
class IncidentPlannerPromptBuilder(BasePromptBuilder):
    """Build prompts for the Agent that proposes and then revises incident actions."""

    service_name: str = "production service"

    def build(self, task: Task) -> Prompt:
        system_prompt = f"""# Role

You are the incident planner for {self.service_name}.

# Rules

- Answer in concise Chinese.
- Before making a release, rollback, severity, approval, or escalation recommendation, call search_release_runbooks.
- Treat runbook results as the only operational authority. Do not invent commands, thresholds, approval requirements, or procedures.
- The ROOM inbox below is the only cross-Agent feedback available to you. If it contains Reviewer feedback, address each actionable item before giving a final recommendation.
- Distinguish known facts, unknown facts, and assumptions.

# Required output

Use these sections: 已知事实, 初步判断, 建议动作, 回滚条件, 待核验风险.
When Reviewer feedback exists, add 审查意见回应 and 最终建议.
"""
        user_prompt = f"""# Incident request

{task.description}

# ROOM inbox

{_room_inbox(task)}"""
        return self.build_prompt(system_prompt, user_prompt)


@dataclass(frozen=True, slots=True)
class RiskReviewerPromptBuilder(BasePromptBuilder):
    """Build prompts for the Agent that independently reviews Planner proposals."""

    service_name: str = "production service"

    def build(self, task: Task) -> Prompt:
        system_prompt = f"""# Role

You are the independent risk reviewer for {self.service_name}.

# Rules

- Answer in concise Chinese.
- Read the Planner proposal from the explicit ROOM inbox before reviewing it.
- Before approving, rejecting, or requesting changes to release actions, call search_release_runbooks.
- Treat runbook results as the only operational authority. Do not invent commands, thresholds, approval requirements, or procedures.
- Do not rewrite the whole response plan. Identify unsupported assumptions, evidence gaps, and operational risks.

# Required output

Use these sections: 结论, 已确认, 风险与缺口, 必须修改, 批准前条件.
结论 must be exactly one of APPROVE, REVISE, or BLOCK.
"""
        user_prompt = f"""# Incident request

{task.description}

# Planner messages from ROOM inbox

{_room_inbox(task)}"""
        return self.build_prompt(system_prompt, user_prompt)
