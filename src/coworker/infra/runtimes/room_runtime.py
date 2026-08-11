"""Generic Agent execution inside one or more ROOMs."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from ...core.models import AgentResult, Message, Task
from ..room import AgentProfile, Room, RoomTurnContext
from ..tool_registry import ToolRegistry
from ..trace import TraceRecorder
from .context import IncrementalContext, open_incremental_context

if TYPE_CHECKING:
    from ...core.base_agent import Agent


class RoomRuntime:
    """Own Agent registration and execute Agent turns from ROOM input."""

    def __init__(self, *, trace: TraceRecorder, max_turns: int = 8) -> None:
        self.trace = trace
        self.max_turns = max_turns
        self._agents: dict[str, Agent] = {}
        self._profiles: dict[str, AgentProfile] = {}

    def register_agent(self, agent: Agent, profile: AgentProfile) -> None:
        if agent.name != profile.name:
            raise ValueError(f"Agent name and profile name must match: {agent.name!r} != {profile.name!r}")
        if profile.name in self._agents:
            raise ValueError(f"Agent is already registered: {profile.name}")
        self._agents[profile.name] = agent
        self._profiles[profile.name] = profile

    def invite_agents(self, room: Room, names: Sequence[str], *, session_id: str) -> tuple[Agent, ...]:
        invited: list[Agent] = []
        for name in names:
            agent, profile = self._agents.get(name), self._profiles.get(name)
            if agent is None or profile is None:
                raise KeyError(f"Agent is not registered: {name}")
            room.register(profile)
            room.invite(name)
            self.trace.register_agent(session_id, name)
            invited.append(agent)
        return tuple(invited)

    def open_incremental_context(self, *, agent_name: str, task: Task, session_id: str) -> IncrementalContext:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent is not registered: {agent_name}")
        return open_incremental_context(
            agent=agent,
            task=task,
            session_id=session_id,
            trace=self.trace,
        )

    def run_turn(
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
            raise KeyError(f"Agent is not registered: {agent_name}")

        turn_context = RoomTurnContext.receive(
            session_id=session_id,
            room=room,
            additional_rooms=tuple(additional_rooms),
            agent_name=agent_name,
        )
        room_task = Task(
            task.description,
            {
                **task.inputs,
                **turn_context.task_inputs(),
                **(extra_inputs or {}),
            },
        )
        history: list[Message] | None = None
        if incremental_context is not None:
            appended = incremental_context.append((*events, *turn_context.room_message_events()))
            self.trace.record_messages(session_id, agent.name, appended)
            history = list(incremental_context.history())
        self.trace.record_room_inbox(
            session_id,
            agent.name,
            {
                room_id: tuple(message.message_id for message in inbox)
                for room_id, inbox in turn_context.inboxes.items()
            },
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
                message_sink=None if incremental_context is None else incremental_context.append_turn_messages,
            )
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            self.trace.record_agent_error(session_id, agent.name, stage="run_room_turn", error=str(error))
            return AgentResult("failed", None, str(error), session_id)
