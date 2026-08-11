"""Synchronous multi-expert software-incident consultation Environment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from ...core.action_envelope import ActionEnvelope
from ...core.base_agent import Agent
from ...core.base_environment import ActionManager, Environment
from ...core.base_observation import Observation
from ...core.base_state import State
from ...core.events import AppEvent, EventDelivery
from ...core.models import AgentResult, Message, Task
from ...core.session import SessionContext
from ...infra import StateStore
from ...infra.client import LLMClient, OpenAICompatibleClient
from ...infra.events import RoomEventDispatcher
from ...infra.room import AgentProfile
from ...infra.runtimes import SynchronousAppRuntime
from ...infra.runtimes.room_runtime import RoomRuntime
from ...infra.runtimes.session_runtime import SessionRuntime
from ...infra.session import AppSession, SessionManager
from .action import IncidentAction
from .agent import IncidentExpertAgent
from .case_loader import load_rcaeval_case
from .observation import IncidentObservation, build_state_message
from .state import ConsultationPhase, ExpertRole, FinalDiagnosis, Finding, IncidentState

ENGINE_NAME = "consultation-engine"
EXPERTS = {
    "metrics-expert": ExpertRole.METRICS,
    "logs-expert": ExpertRole.LOGS,
    "traces-expert": ExpertRole.TRACES,
    "lead-expert": ExpertRole.LEAD,
}


@dataclass(frozen=True, slots=True)
class IncidentActionPayload:
    component: str
    narrative: str
    evidence_ids: tuple[str, ...]
    confidence: int


class IncidentActionValue(ActionEnvelope[IncidentActionPayload]):
    @property
    def component(self) -> str:
        return self.payload.component

    @property
    def narrative(self) -> str:
        return self.payload.narrative

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return self.payload.evidence_ids

    @property
    def confidence(self) -> int:
        return self.payload.confidence


class IncidentActionManager(ActionManager):
    def __init__(self, actions: dict[str, IncidentAction]) -> None:
        self.actions = actions

    def resolve_action(self, response: Any) -> IncidentActionValue | None:
        if not isinstance(response, tuple) or len(response) != 3:
            return None
        actor, message, observation = response
        if not isinstance(actor, str) or not isinstance(message, Message) or not isinstance(observation, IncidentObservation):
            return None
        try:
            call = next(item for item in message.tool_calls if item.name in {"submit_finding", "submit_final_diagnosis"})
            payload = json.loads(call.arguments) if isinstance(call.arguments, str) else dict(call.arguments)
            mapped = self.actions[actor].get_action(call.name)
            narrative_key = "summary" if mapped.name == "submit_finding" else "root_cause"
            if not isinstance(payload, dict):
                return None
            return IncidentActionValue(
                f"{actor}:{call.id}", actor, mapped.name,
                IncidentActionPayload(
                    str(payload["component"]).strip(), str(payload[narrative_key]).strip(),
                    tuple(str(item) for item in payload["evidence_ids"]), int(payload["confidence"]),
                ),
                call, observation,
            )
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
            return None

    def validate_action(self, action: Any, state: State) -> bool:
        if not isinstance(action, IncidentActionValue) or not isinstance(state, IncidentState):
            return False
        if action.message_id in state.consumed_action_ids or action.actor not in EXPERTS or not action.component or not action.narrative:
            return False
        if not 0 <= action.confidence <= 100 or not action.evidence_ids:
            return False
        role = EXPERTS[action.actor]
        if state.phase is ConsultationPhase.INDEPENDENT_ANALYSIS:
            allowed = {item.evidence_id for item in state.evidence_for(role)}
            return role is not ExpertRole.LEAD and action.name == "submit_finding" and set(action.evidence_ids) <= allowed
        cited = {evidence_id for finding in state.findings.values() for evidence_id in finding.evidence_ids}
        return state.phase is ConsultationPhase.FINAL_DIAGNOSIS and role is ExpertRole.LEAD and action.name == "submit_final_diagnosis" and set(action.evidence_ids) <= cited

    def available_actions(self, state: State, agent: Agent) -> tuple[str, ...]:
        if not isinstance(state, IncidentState):
            return ()
        role = EXPERTS.get(agent.name)
        if state.phase is ConsultationPhase.INDEPENDENT_ANALYSIS and role is not ExpertRole.LEAD:
            return ("submit_finding",)
        if state.phase is ConsultationPhase.FINAL_DIAGNOSIS and role is ExpertRole.LEAD:
            return ("submit_final_diagnosis",)
        return ()

    def resolve_actions(self, state: State, actions: object) -> dict[str, IncidentActionValue]:
        if not isinstance(actions, dict) or not all(isinstance(key, str) and isinstance(value, IncidentActionValue) for key, value in actions.items()):
            raise TypeError("actions must be dict[str, IncidentActionValue]")
        return actions


@dataclass(slots=True)
class IncidentWorkflowConfig:
    case_root: Path = Path("data/software_incident/rcaeval_multi_source_sample/multi-source-data")


class IncidentConsultationEnvironment(Environment):
    session_mode = "incident-consultation"
    entry_agent = "lead-expert"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 5) -> None:
        self.session = session
        self.llm = llm
        self.model = model
        self.max_turns = max_turns
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.sync_runtime = SynchronousAppRuntime()
        self.event_dispatcher = RoomEventDispatcher()
        self.action_manager: IncidentActionManager | None = None
        self._active: AppSession[IncidentState] | None = None
        self._task: Task | None = None
        super().__init__((), IncidentState.initial("", ""), Observation("incident-placeholder", "", ""), trace=session.trace)

    @classmethod
    def from_environment(cls, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data"), max_turns: int = 5) -> "IncidentConsultationEnvironment":
        return cls(SessionManager(traces_root=traces_root, room_data_root=room_data_root), llm=OpenAICompatibleClient.from_environment(), model=os.getenv("COWORKER_MODEL", "deepseek-v4-flash"), max_turns=max_turns)

    def run(
        self,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: Callable[[str], None] | None = None,
        config: IncidentWorkflowConfig | None = None,
    ) -> AgentResult:
        """Compatibility entrypoint delegating session lifecycle to SessionRuntime."""
        return SessionRuntime(trace=self.session.trace).run(
            self,
            task=task,
            session_id=session_id,
            on_session_opened=on_session_opened,
            config=config,
        )

    def run_session(
        self,
        *,
        task: Task,
        context: SessionContext,
        config: IncidentWorkflowConfig | None = None,
        **_: Any,
    ) -> AgentResult:
        """Run the consultation domain workflow inside a Runtime-managed session."""
        self._active = None
        try:
            active = self._open(task, context, config or IncidentWorkflowConfig())
            self._active, self._task = active, task
            self.agents, self.state = tuple(active.agents.values()), active.state
            self.action_manager = IncidentActionManager({name: agent.action for name, agent in active.agents.items()})
            state = self.sync_runtime.run(self, active)
            diagnosis = state.final_diagnosis
            text = "会诊完成。" if diagnosis is None else f"会诊完成：疑似根因组件 {diagnosis.component}；{diagnosis.root_cause}"
            return AgentResult("completed", Message("assistant", text), None, active.session_id)
        except Exception:
            if self._active is not None:
                self._active.persist()
            raise

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        current, active = self._state(state), self._require_active()
        names = ("metrics-expert", "logs-expert", "traces-expert") if current.phase is ConsultationPhase.INDEPENDENT_ANALYSIS else ("lead-expert",) if current.phase is ConsultationPhase.FINAL_DIAGNOSIS else ()
        return tuple(active.agents[name] for name in names)

    def observe(self, state: State, agent: Agent) -> Observation:
        current, active, manager = self._state(state), self._require_active(), self._manager()
        role = EXPERTS[agent.name]
        return IncidentObservation(state_message=build_state_message(current, role), available_tool_names=manager.available_actions(current, agent), room=active.room("public"), task_id=current.task_id, session_id=current.session_id)

    def act(self, agent: Agent, observation: Observation) -> IncidentActionValue | None:
        if not isinstance(observation, IncidentObservation):
            raise TypeError("observation must be IncidentObservation")
        active = self._require_active()
        turn = self.room_runtime.run_turn(room=active.room("public"), agent_name=agent.name, task=self._require_task(), session_id=active.session_id, incremental_context=active.contexts[agent.name], events=(observation.state_message,), available_tool_names=observation.available_tool_names)
        if turn.status == "failed":
            raise RuntimeError(f"Incident expert turn failed for {agent.name}: {turn.error}")
        return self._manager().resolve_action((agent.name, turn.content, observation))

    def ready_to_step(self, state: State, actions: object) -> bool:
        current = self._state(state)
        expected = 3 if current.phase is ConsultationPhase.INDEPENDENT_ANALYSIS else 1
        return isinstance(actions, dict) and len(actions) == expected

    def step(self, state: State, action: Any) -> State:
        current, active = self._state(state), self._require_active()
        next_state = IncidentState.from_dict(current.to_dict())
        actions = self._manager().resolve_actions(next_state, action)
        for item in actions.values():
            if not self._manager().validate_action(item, next_state):
                self.reject_tool_action(
                    agent=active.agents[item.actor], observation=item.observation, tool_call=item.tool_call,
                    reason="Action 未通过当前会诊状态验证。",
                    message_sink=active.contexts[item.actor].append_turn_messages,
                )
                raise ValueError(f"Illegal incident action {item.name!r} from {item.actor!r}")
            self.execute_tool_action(
                agent=active.agents[item.actor],
                observation=item.observation,
                tool_call=item.tool_call,
                message_sink=active.contexts[item.actor].append_turn_messages,
            )
        next_state.consumed_action_ids.update(item.message_id for item in actions.values())
        if next_state.phase is ConsultationPhase.INDEPENDENT_ANALYSIS:
            for item in actions.values():
                next_state.findings[item.actor] = Finding(item.message_id, item.actor, EXPERTS[item.actor], item.component, item.narrative, item.evidence_ids, item.confidence)
            next_state.phase = ConsultationPhase.FINAL_DIAGNOSIS
        elif next_state.phase is ConsultationPhase.FINAL_DIAGNOSIS:
            item = next(iter(actions.values()))
            next_state.final_diagnosis = FinalDiagnosis(item.component, item.narrative, item.evidence_ids, item.confidence)
            next_state.phase = ConsultationPhase.FINISHED
        active.state = next_state
        self.state = next_state
        return next_state

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[AppEvent, ...]:
        before, after = self._state(old_state), self._state(new_state)
        if before.phase is ConsultationPhase.INDEPENDENT_ANALYSIS and after.phase is ConsultationPhase.FINAL_DIAGNOSIS:
            return (AppEvent(f"{after.session_id}:consultation:diagnosis", "phase_changed", ENGINE_NAME, "三位证据专家已提交 Finding，进入最终诊断阶段。"),)
        if after.phase is ConsultationPhase.FINISHED:
            return (AppEvent(f"{after.session_id}:consultation:finished", "workflow_finished", ENGINE_NAME, "主诊断专家已提交最终诊断，会诊结束。"),)
        return ()

    def dispatch_events(self, events: tuple[AppEvent, ...]) -> None:
        deliveries = tuple(EventDelivery(event.event_id, "public") for event in events)
        self.event_dispatcher.dispatch(events, deliveries, rooms=self._require_active().rooms)

    def orchestrate_agents(self) -> Any:
        return self.run

    def _open(self, task: Task, context: SessionContext, config: IncidentWorkflowConfig) -> AppSession[IncidentState]:
        store = StateStore(self.session.trace.root.parent / "state" / "data")
        session_id = context.session_id
        if not context.resumed:
            case = load_rcaeval_case(config.case_root)
            state = IncidentState.from_case(case, task_id=task.description, session_id=session_id)
            room = self.session.create_room(f"incident-consultation-{session_id}", session_id=session_id)
            self.session.trace.update_session_metadata(session_id, public_room_id=room.room_id, incident_room_id=room.room_id, incident_case_id=case.case_id)
            room.register(AgentProfile(name=ENGINE_NAME, introduction="Deterministic consultation state-transition engine.", role="consultation-engine"))
            room.invite(ENGINE_NAME)
        else:
            metadata = self.session.trace.session_data(session_id)
            if metadata.get("mode") != "incident-consultation" or not isinstance(metadata.get("incident_room_id"), str):
                raise ValueError(f"Session is not an incident consultation: {session_id}")
            room = self.session.resume_room(metadata["incident_room_id"], session_id=session_id)
            state = store.restore(session_id, "incident_consultation", IncidentState)
        agents = {name: IncidentExpertAgent(self.llm, self.model, name=name, role=role, room=room) for name, role in EXPERTS.items()}
        for name, agent in agents.items():
            role = EXPERTS[name]
            self.room_runtime.register_agent(agent, AgentProfile(name=name, introduction=f"Incident consultation expert for {role.value}.", role=role.value))
        if session_id is not None and not all(name in room.participants() for name in agents):
            self.room_runtime.invite_agents(room, tuple(agents), session_id=session_id)
        contexts = {name: self.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
        active = AppSession(session_id, state, agents, contexts, {"public": room}, store, "incident_consultation")
        active.persist()
        return active

    def _require_active(self) -> AppSession[IncidentState]:
        if self._active is None:
            raise RuntimeError("Incident consultation has not started")
        return self._active

    def _require_task(self) -> Task:
        if self._task is None:
            raise RuntimeError("Incident consultation has no Task")
        return self._task

    def _manager(self) -> IncidentActionManager:
        if self.action_manager is None:
            raise RuntimeError("Incident consultation has no ActionManager")
        return self.action_manager

    @staticmethod
    def _state(state: State) -> IncidentState:
        if not isinstance(state, IncidentState):
            raise TypeError("state must be IncidentState")
        return state
