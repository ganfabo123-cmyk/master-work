from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path

from .agents import Agent, IncidentPlannerAgent, RiskReviewerAgent
from .llm import LLMClient, OpenAICompatibleClient
from .models import AgentResult, Message, Task
from .room import AgentProfile, Room, RoomMessage
from .trace import TraceRecorder

AgentFactory = Callable[[AgentProfile], Agent]
_PLANNER_NAME = "incident-planner"
_REVIEWER_NAME = "risk-reviewer"


@dataclass(slots=True)
class WorkflowSession:
    """All state needed to run one Planner-Reviewer workflow session."""

    session_id: str
    room: Room
    agents: dict[str, Agent]
    messages: dict[str, list[Message]]
    is_new: bool


class Orchestrator:
    """Owns the complete lifecycle and execution of one multi-Agent task session."""

    def __init__(
        self,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 8,
        llm: LLMClient | None = None,
        model: str | None = None,
    ) -> None:
        self.trace = TraceRecorder(traces_root)
        self.room_data_root = room_data_root
        self.max_turns = max_turns
        self.llm = llm
        self.model = model
        self._agents: dict[str, Agent] = {}
        self._profiles: dict[str, AgentProfile] = {}
        self._rooms: dict[str, Room] = {}
        self._agent_factories: dict[str, AgentFactory] = {}

    @classmethod
    def from_environment(
        cls,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 8,
    ) -> "Orchestrator":
        client = OpenAICompatibleClient.from_environment()
        model = os.getenv("CODEHARNESS_MODEL", "deepseek-v4-flash")
        orchestrator = cls(
            traces_root=traces_root,
            room_data_root=room_data_root,
            max_turns=max_turns,
            llm=client,
            model=model,
        )
        orchestrator.register_agent_factory(_PLANNER_NAME, lambda profile: IncidentPlannerAgent(client, model))
        orchestrator.register_agent_factory(_REVIEWER_NAME, lambda profile: RiskReviewerAgent(client, model))
        return orchestrator

    def run(
        self,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: Callable[[str], None] | None = None,
    ) -> AgentResult:
        """Create or restore one complete task session, then run Planner -> Reviewer -> Planner."""
        workflow = self._open_workflow_session(task=task, session_id=session_id)
        if on_session_opened is not None:
            on_session_opened(workflow.session_id)
        planner = workflow.agents[_PLANNER_NAME]
        reviewer = workflow.agents[_REVIEWER_NAME]
        try:
            initial_plan = self.run_room_turn(
                room=workflow.room,
                agent_name=planner.name,
                task=task,
                session_id=workflow.session_id,
                messages=workflow.messages[planner.name] or None,
            )
            plan_text = _result_text(initial_plan, "Planner initial plan")
            workflow.messages[planner.name] = list(self.trace.messages(workflow.session_id, planner.name))
            workflow.room.send(RoomMessage(name=planner.name, at=reviewer.name, txt=plan_text))

            review = self.run_room_turn(
                room=workflow.room,
                agent_name=reviewer.name,
                task=task,
                session_id=workflow.session_id,
                messages=workflow.messages[reviewer.name] or None,
            )
            review_text = _result_text(review, "Reviewer result")
            workflow.messages[reviewer.name] = list(self.trace.messages(workflow.session_id, reviewer.name))
            workflow.room.send(RoomMessage(name=reviewer.name, at=planner.name, txt=review_text))

            final = self.run_room_turn(
                room=workflow.room,
                agent_name=planner.name,
                task=task,
                session_id=workflow.session_id,
                messages=workflow.messages[planner.name],
            )
            workflow.messages[planner.name] = list(self.trace.messages(workflow.session_id, planner.name))
            message = _result_message(final, "Planner final recommendation")
            self.trace.finish_session(workflow.session_id, "completed")
            return AgentResult("completed", message, None, workflow.session_id)
        except Exception as error:
            self.trace.finish_session(workflow.session_id, "failed", str(error))
            return AgentResult("failed", None, str(error), workflow.session_id)

    def _open_workflow_session(self, *, task: Task, session_id: str | None) -> WorkflowSession:
        """Return every object needed by one workflow, either newly created or fully restored."""
        if session_id is None:
            planner, reviewer = self._new_workflow_agents()
            new_session_id = self.trace.create_session(task.description, planner.name, mode="room")
            room = self.create_room(f"release-incident-review-{new_session_id}", session_id=new_session_id)
            self.trace.attach_room(new_session_id, room_id=room.room_id, room_session_id=room.session_id)
            self._register_workflow_agents(planner, reviewer)
            self.invite_agents(room, (planner.name, reviewer.name), session_id=new_session_id)
            return WorkflowSession(
                session_id=new_session_id,
                room=room,
                agents={planner.name: planner, reviewer.name: reviewer},
                messages={planner.name: [], reviewer.name: []},
                is_new=True,
            )

        data = self.trace.session_data(session_id)
        room_data = data.get("room")
        if data.get("mode") != "room" or not isinstance(room_data, dict):
            raise ValueError(f"Session is not a resumable multi-Agent ROOM session: {session_id}")
        room_id = room_data.get("room_id")
        room_session_id = room_data.get("session_id")
        if not isinstance(room_id, str) or not isinstance(room_session_id, str):
            raise ValueError(f"Session has invalid ROOM metadata: {session_id}")
        self.trace.resume_session_state(session_id)
        room = self._rooms.get(room_id)
        if room is None:
            room = self.resume_room(room_id, session_id=room_session_id)
            restored = {agent.name: agent for agent in self.restore_room_agents(room)}
        else:
            restored = {name: self._agents[name] for name in room.participants() if name in self._agents}
        required = {_PLANNER_NAME, _REVIEWER_NAME}
        if not required.issubset(room.participants()) or not required.issubset(restored):
            raise ValueError(f"Session is missing required ROOM participants: {session_id}")
        messages = {name: list(self.trace.messages(session_id, name)) for name in required}
        return WorkflowSession(session_id=session_id, room=room, agents=restored, messages=messages, is_new=False)

    def _new_workflow_agents(self) -> tuple[IncidentPlannerAgent, RiskReviewerAgent]:
        if self.llm is None or self.model is None:
            raise RuntimeError("Orchestrator needs llm and model to create a new workflow session")
        return IncidentPlannerAgent(self.llm, self.model), RiskReviewerAgent(self.llm, self.model)

    def _register_workflow_agents(self, planner: Agent, reviewer: Agent) -> None:
        self.register_agent(
            planner,
            AgentProfile(
                name=planner.name,
                introduction="Release incident planner.",
                skill=("release-incident",),
                role="planner",
                kwargs={"factory": _PLANNER_NAME},
            ),
        )
        self.register_agent(
            reviewer,
            AgentProfile(
                name=reviewer.name,
                introduction="Release incident risk reviewer.",
                skill=("release-incident",),
                role="reviewer",
                kwargs={"factory": _REVIEWER_NAME},
            ),
        )

    def register_agent_factory(self, factory_name: str, factory: AgentFactory) -> None:
        if not factory_name.strip():
            raise ValueError("factory_name cannot be empty")
        if factory_name in self._agent_factories:
            raise ValueError(f"Agent factory is already registered: {factory_name}")
        self._agent_factories[factory_name] = factory

    def register_agent(self, agent: Agent, profile: AgentProfile) -> None:
        if agent.name != profile.name:
            raise ValueError(f"Agent name and profile name must match: {agent.name!r} != {profile.name!r}")
        if profile.name in self._agents:
            raise ValueError(f"Agent is already registered with Orchestrator: {profile.name}")
        self._agents[profile.name] = agent
        self._profiles[profile.name] = profile

    def create_room(self, room_id: str, *, session_id: str | None = None) -> Room:
        if room_id in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id}")
        room = Room(room_id, session_id=session_id, data_root=self.room_data_root)
        self._rooms[room_id] = room
        return room

    def resume_room(self, room_id: str, *, session_id: str) -> Room:
        if room_id in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id}")
        room = Room.resume(room_id, session_id=session_id, data_root=self.room_data_root)
        self._rooms[room_id] = room
        return room

    def invite_agents(self, room: Room, agent_names: Sequence[str], *, session_id: str | None = None) -> tuple[Agent, ...]:
        invited: list[Agent] = []
        for name in agent_names:
            agent = self._agents.get(name)
            profile = self._profiles.get(name)
            if agent is None or profile is None:
                raise KeyError(f"Agent is not registered with Orchestrator: {name}")
            room.register(profile)
            room.invite(name)
            if session_id is not None:
                self.trace.register_agent(session_id, name)
            invited.append(agent)
        return tuple(invited)

    def restore_room_agents(self, room: Room) -> tuple[Agent, ...]:
        restored: list[Agent] = []
        for profile in room.registered_agents():
            factory_name = profile.kwargs.get("factory")
            if not isinstance(factory_name, str) or not factory_name:
                raise ValueError(f"ROOM Agent '{profile.name}' has no profile.kwargs['factory']")
            factory = self._agent_factories.get(factory_name)
            if factory is None:
                raise KeyError(f"ROOM Agent factory is not registered: {factory_name}")
            agent = factory(profile)
            self.register_agent(agent, profile)
            restored.append(agent)
        return tuple(restored)

    def run_room_turn(
        self,
        *,
        room: Room,
        agent_name: str,
        task: Task,
        session_id: str,
        messages: list[Message] | None = None,
    ) -> AgentResult:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent is not registered with Orchestrator: {agent_name}")
        inbox = room.receive(agent_name)
        room_task = Task(
            task.description,
            {
                **task.inputs,
                "room": {
                    "room_id": room.room_id,
                    "session_id": room.session_id,
                    "inbox": [message.model_dump(mode="json") for message in inbox],
                },
            },
        )
        history = list(messages) if messages else None
        if history is not None:
            history.append(_user_message_for_task(agent, room_task))
        self.trace.record(
            session_id,
            agent.name,
            "room_inbox",
            room_id=room.room_id,
            room_session_id=room.session_id,
            message_ids=tuple(message.message_id for message in inbox),
        )
        try:
            output = agent.run(
                room_task,
                messages=history,
                max_turns=self.max_turns,
                trace=self.trace,
                session_id=session_id,
                record_initial_messages=history is None,
            )
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            return AgentResult("failed", None, str(error), session_id)


def _user_message_for_task(agent: Agent, task: Task) -> Message:
    messages = agent.initial_messages(task)
    user_messages = [message for message in messages if message.role == "user"]
    if len(user_messages) != 1:
        raise ValueError(f"Agent '{agent.name}' must build exactly one user message per request")
    return user_messages[0]


def _result_message(result: AgentResult, label: str) -> Message:
    if result.status != "completed" or not isinstance(result.content, Message):
        raise RuntimeError(f"{label} failed: {result.error or 'no assistant message returned'}")
    if not str(result.content.content).strip():
        raise RuntimeError(f"{label} returned an empty assistant message")
    return result.content


def _result_text(result: AgentResult, label: str) -> str:
    return str(_result_message(result, label).content)
