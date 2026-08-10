"""Per-expert Observation projections for incident consultation."""

from __future__ import annotations

import json

from ...core.base_observation import Observation
from ...core.models import Message
from ...infra.room import Room
from .state import ExpertRole, IncidentState


class IncidentObservation(Observation):
    def __init__(self, *, state_message: Message, available_tool_names: tuple[str, ...], room: Room, task_id: str, session_id: str) -> None:
        super().__init__("incident-consultation-observation", task_id, session_id)
        self.state_message = state_message
        self.available_tool_names = available_tool_names
        self.room = room


def build_state_message(state: IncidentState, role: ExpertRole) -> Message:
    payload: dict[str, object] = {
        "type": "incident_consultation_state",
        "case_id": state.case_id,
        "injection_time": state.injection_time,
        "phase": state.phase.value,
        "role": role.value,
    }
    if role is ExpertRole.LEAD:
        payload["findings"] = [
            {
                "finding_id": item.finding_id,
                "expert": item.expert,
                "role": item.role.value,
                "component": item.component,
                "summary": item.summary,
                "evidence_ids": item.evidence_ids,
                "confidence": item.confidence,
            }
            for item in state.findings.values()
        ]
    else:
        payload["evidence"] = [item.to_dict() for item in state.evidence_for(role)]
    return Message("user", json.dumps(payload, ensure_ascii=False))
