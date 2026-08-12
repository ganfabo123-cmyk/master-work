"""Role-scoped investment research Observations."""

from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room
from .state import InvestmentRole, InvestmentState


class InvestmentObservation(Observation):
    def __init__(self, *, state_message: Message, available_tool_names: tuple[str, ...], room: Room, task_id: str, session_id: str) -> None:
        super().__init__("ai-berkshire-observation", task_id, session_id)
        self.state_message = state_message
        self.available_tool_names = available_tool_names
        self.room = room


def build_state_message(state: InvestmentState, role: InvestmentRole) -> Message:
    payload: dict[str, object] = {
        "type": "ai_berkshire_state",
        "company_name": state.company_name,
        "ticker": state.ticker,
        "data_cutoff": state.data_cutoff,
        "information_grade": state.information_grade,
        "phase": state.phase.value,
        "role": role.value,
    }
    if role is InvestmentRole.LEAD:
        payload["artifacts"] = [
            {
                "artifact_id": artifact.artifact_id,
                "author": artifact.author,
                "role": artifact.role.value,
                "title": artifact.title,
                "thesis": artifact.thesis,
                "content": artifact.content,
                "score": artifact.score,
                "confidence": artifact.confidence,
                "citations": artifact.citations,
            }
            for artifact in state.artifacts.values()
        ]
    else:
        payload["research_context"] = state.research_context
    return Message("user", json.dumps(payload, ensure_ascii=False))
