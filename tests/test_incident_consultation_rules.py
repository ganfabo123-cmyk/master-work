from __future__ import annotations

from codeharness.apps.incident_consultation.action import IncidentAction
from codeharness.apps.incident_consultation.case_loader import Evidence, IncidentCase
from codeharness.apps.incident_consultation.environment import IncidentActionManager, IncidentActionValue
from codeharness.apps.incident_consultation.observation import build_state_message
from codeharness.apps.incident_consultation.state import ExpertRole, IncidentState
from codeharness.core.base_action import BaseAction
from codeharness.core.base_agent import Agent
from codeharness.core.base_environment import ActionManager, Environment
from codeharness.core.base_observation import Observation
from codeharness.core.base_policy import BasePolicy
from codeharness.core.base_state import State
from codeharness.infra.room import AgentProfile, Room


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


def test_app_types_inherit_existing_codeharness_bases() -> None:
    from codeharness.apps.incident_consultation.agent import IncidentExpertAgent
    from codeharness.apps.incident_consultation.environment import IncidentConsultationEnvironment
    from codeharness.apps.incident_consultation.observation import IncidentObservation
    from codeharness.apps.incident_consultation.policy import IncidentPolicy

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
    valid = IncidentActionValue("a1", "metrics-expert", "submit_finding", "checkoutservice", "CPU changed", ("metrics-1",), 80)
    invalid = IncidentActionValue("a2", "metrics-expert", "submit_finding", "checkoutservice", "log error", ("logs-1",), 80)

    assert manager.validate_action(valid, state)
    assert not manager.validate_action(invalid, state)
