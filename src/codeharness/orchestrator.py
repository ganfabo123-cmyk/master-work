from __future__ import annotations

from collections.abc import Callable, Sequence
import os
from pathlib import Path

from .base_agent import LLMAgent as Agent
from .context import IncrementalContext
from .llm import LLMClient, OpenAICompatibleClient
from .models import AgentResult, Message, Task
from .room import AgentProfile, Room, RoomTurnContext
from .core.tool_registry import ToolRegistry
from .trace import TraceRecorder


AgentFactory = Callable[[AgentProfile], Agent]


class Orchestrator:
    """Owns generic Agent, ROOM, trace, and one-turn scheduling infrastructure."""

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
        self._rooms: dict[tuple[str, str], Room] = {}
        self._agent_factories: dict[str, AgentFactory] = {}

    @classmethod
    def from_environment(
        cls,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 8,
    ) -> "Orchestrator":
        return cls(
            traces_root=traces_root,
            room_data_root=room_data_root,
            max_turns=max_turns,
            llm=OpenAICompatibleClient.from_environment(),
            model=os.getenv("CODEHARNESS_MODEL", "deepseek-v4-flash"),
        )

    def run(
        self,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: Callable[[str], None] | None = None,
    ) -> AgentResult:
        """Run the currently configured application workflow.

        The harness default remains the werewolf demonstration; its domain logic
        is intentionally isolated from this generic scheduler.
        """
        from .util.werewolf_workflow import run_werewolf_workflow

        return run_werewolf_workflow(self, task=task, session_id=session_id, on_session_opened=on_session_opened)

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

    def open_incremental_context(self, *, agent_name: str, task: Task, session_id: str) -> IncrementalContext:
        """Restore one Agent's context or record its stable initial prefix once."""
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent is not registered with Orchestrator: {agent_name}")
        try:
            restored = self.trace.messages(session_id, agent_name)
        except KeyError:
            restored = ()
        context, initial = IncrementalContext.restore_or_initialize(
            restored_messages=restored,
            initial_messages=agent.initial_messages(Task(task.description)),
        )
        self.trace.record_messages(session_id, agent_name, initial)
        return context

    def create_room(self, room_id: str, *, session_id: str | None = None) -> Room:
        room_session_id = session_id or room_id
        key = (room_session_id, room_id)
        if key in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id} ({room_session_id})")
        room = Room(room_id, session_id=room_session_id, data_root=self.room_data_root, **self._room_message_callbacks(room_session_id))
        self._rooms[key] = room
        if self._has_trace_session(room_session_id):
            self.trace.attach_room(room_session_id, room_id=room.room_id, room_session_id=room.session_id)
        return room

    def resume_room(self, room_id: str, *, session_id: str) -> Room:
        key = (session_id, room_id)
        if key in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id} ({session_id})")
        room = Room.resume(room_id, session_id=session_id, data_root=self.room_data_root, **self._room_message_callbacks(session_id))
        self._rooms[key] = room
        return room

    def rooms_for_session(self, session_id: str) -> tuple[Room, ...]:
        return tuple(room for (loaded_session_id, _), room in self._rooms.items() if loaded_session_id == session_id)

    def invite_agents(self, room: Room, agent_names: Sequence[str], *, session_id: str | None = None) -> tuple[Agent, ...]:
        invited: list[Agent] = []
        for name in agent_names:
            agent, profile = self._agents.get(name), self._profiles.get(name)
            if agent is None or profile is None:
                raise KeyError(f"Agent is not registered with Orchestrator: {name}")
            room.register(profile)
            room.invite(name)
            if session_id is not None:
                self.trace.register_agent(session_id, name)
            invited.append(agent)
        return tuple(invited)

    def restore_room_agents(self, room: Room, *, agent_names: Sequence[str] | None = None) -> tuple[Agent, ...]:
        wanted = set(agent_names) if agent_names is not None else None
        restored: list[Agent] = []
        for profile in room.registered_agents():
            if wanted is not None and profile.name not in wanted:
                continue
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
        additional_rooms: Sequence[Room] = (),
        incremental_context: IncrementalContext | None = None,
        events: Sequence[Message] = (),
        tools: tuple[Callable[..., object], ...] | None = None,
        available_tool_names: Sequence[str] | None = None,
        tool_registry: ToolRegistry | None = None,
        extra_inputs: dict[str, object] | None = None,
    ) -> AgentResult:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent is not registered with Orchestrator: {agent_name}")
        turn_context = RoomTurnContext.receive(
            session_id=session_id,
            room=room,
            additional_rooms=tuple(additional_rooms),
            agent_name=agent_name,
        )
        room_task = Task(task.description, {**task.inputs, **turn_context.task_inputs(), **(extra_inputs or {})})
        history: list[Message] | None = None
        if incremental_context is not None:
            appended = incremental_context.append((*events, *turn_context.room_message_events()))
            self.trace.record_messages(session_id, agent.name, appended)
            history = list(incremental_context.history())
        self.trace.record(
            session_id,
            agent.name,
            "room_inbox",
            rooms={room_id: tuple(message.message_id for message in inbox) for room_id, inbox in turn_context.inboxes.items()},
        )
        try:
            output = agent.run(
                room_task,
                messages=history,
                tools=tools,
                available_tool_names=available_tool_names,
                tool_registry=tool_registry,
                max_turns=self.max_turns,
                trace=self.trace,
                session_id=session_id,
                record_initial_messages=history is None,
            )
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            self.trace.record(session_id, agent.name, "error", stage="run_room_turn", error=str(error))
            return AgentResult("failed", None, str(error), session_id)

    def _has_trace_session(self, session_id: str) -> bool:
        return (self.trace.root / session_id / "session.json").exists()

    def _room_message_callbacks(self, session_id: str) -> dict[str, Callable[..., object]]:
        if not self._has_trace_session(session_id):
            return {}
        return {
            "message_recorder": lambda room_id, message: self.trace.record_room_message(session_id, room_id, message),
            "message_loader": lambda message_id: self.trace.room_message(session_id, message_id),
            "message_replayer": lambda room_id: self.trace.room_messages(session_id, room_id),
        }
