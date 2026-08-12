from __future__ import annotations

from coworker.apps.incident_consultation.action import IncidentAction
from coworker.apps.incident_consultation.case_loader import Evidence, IncidentCase
from coworker.apps.incident_consultation.environment import IncidentActionManager, IncidentActionPayload, IncidentActionValue
from coworker.apps.incident_consultation.observation import build_state_message
from coworker.apps.incident_consultation.state import ExpertRole, IncidentState
from coworker.core.base_action import BaseAction
from coworker.core.base_agent import Agent
from coworker.core.base_environment import ActionManager, Environment
from coworker.core.base_observation import Observation
from coworker.core.base_policy import BasePolicy
from coworker.core.base_state import State
from coworker.core.models import ToolCall
from coworker.infra.room import AgentProfile, Room


def _state() -> IncidentState:
    case = IncidentCase(
        "case",
        1000,
        {
            role.value: (Evidence(f"{role.value}-1", role.value, "fact", f"{role.value}.csv", "row=1"),)
            for role in (ExpertRole.METRICS, ExpertRole.LOGS, ExpertRole.TRACES)
        },
    )
    return IncidentState.from_case(case, task_id="task", session_id="session")


def test_app_types_inherit_existing_coworker_bases() -> None:
    from coworker.apps.incident_consultation.agent import IncidentExpertAgent
    from coworker.apps.incident_consultation.environment import IncidentConsultationEnvironment
    from coworker.apps.incident_consultation.observation import IncidentObservation
    from coworker.apps.incident_consultation.policy import IncidentPolicy

    assert issubclass(IncidentState, State)
    assert issubclass(IncidentObservation, Observation)
    assert issubclass(IncidentPolicy, BasePolicy)
    assert issubclass(IncidentAction, BaseAction)
    assert issubclass(IncidentExpertAgent, Agent)
    assert issubclass(IncidentActionManager, ActionManager)
    assert issubclass(IncidentConsultationEnvironment, Environment)


def test_expert_observation_and_action_are_limited_to_owned_evidence(tmp_path) -> None:
    state = _state()
    metrics_message = build_state_message(state, ExpertRole.METRICS)
    lead_message = build_state_message(state, ExpertRole.LEAD)

    assert "metrics-1" in str(metrics_message.content)
    assert "logs-1" not in str(metrics_message.content)
    assert '"findings": []' in str(lead_message.content)

    room = Room("consultation", session_id="session", data_root=tmp_path)
    room.register(AgentProfile(name="metrics-expert", introduction="metrics", role="metrics"))
    room.invite("metrics-expert")
    action = IncidentAction(agent_name="metrics-expert", room=room)
    manager = IncidentActionManager({"metrics-expert": action})
    observation = Observation("obs", "task", "session")
    valid = IncidentActionValue(
        "a1", "metrics-expert", "submit_finding",
        IncidentActionPayload("checkoutservice", "CPU changed", ("metrics-1",), 80),
        ToolCall("call-1", "submit_finding", {}), observation,
    )
    invalid = IncidentActionValue(
        "a2", "metrics-expert", "submit_finding",
        IncidentActionPayload("checkoutservice", "log error", ("logs-1",), 80),
        ToolCall("call-2", "submit_finding", {}), observation,
    )

    assert manager.validate_action(valid, state)[0]
    assert not manager.validate_action(invalid, state)[0]
