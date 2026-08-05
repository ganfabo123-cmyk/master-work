from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from .agents import Agent
from .models import AgentResult, Message, Task
from .room import AgentProfile, Room
from .trace import TraceRecorder


class Orchestrator:
    """Schedules an Agent run and owns its Trace session lifecycle."""

    def __init__(
        self,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 8,
    ) -> None:
        self.trace = TraceRecorder(traces_root)
        self.room_data_root = room_data_root
        self.max_turns = max_turns
        self._agents: dict[str, Agent] = {}
        self._profiles: dict[str, AgentProfile] = {}
        self._rooms: dict[str, Room] = {}

    def register_agent(self, agent: Agent, profile: AgentProfile) -> None:
        """Make one Agent available for later ROOM invitations."""
        if agent.name != profile.name:
            raise ValueError(f"Agent name and profile name must match: {agent.name!r} != {profile.name!r}")
        if profile.name in self._agents:
            raise ValueError(f"Agent is already registered with Orchestrator: {profile.name}")
        self._agents[profile.name] = agent
        self._profiles[profile.name] = profile

    def create_room(self, room_id: str, *, session_id: str | None = None) -> Room:
        """Create and retain one ROOM; no Agent is invited automatically."""
        if room_id in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id}")
        room = Room(room_id, session_id=session_id, data_root=self.room_data_root)
        self._rooms[room_id] = room
        return room

    def invite_agents(self, room: Room, agent_names: Sequence[str]) -> tuple[Agent, ...]:
        """Persist profiles for this ROOM session and invite the selected registered Agents."""
        invited: list[Agent] = []
        for name in agent_names:
            if name not in self._agents:
                raise KeyError(f"Agent is not registered with Orchestrator: {name}")
            room.register(self._profiles[name])
            room.invite(name)
            invited.append(self._agents[name])
        return tuple(invited)

    def registered_agents(self) -> tuple[AgentProfile, ...]:
        """Return profiles that Orchestrator may invite into a ROOM."""
        return tuple(self._profiles[name] for name in sorted(self._profiles))

    def run(self, *, agent: Agent, task: Task) -> AgentResult:
        session_id = self.start_session(agent=agent, task=task)
        try:
            output = self.run_turn(agent=agent, task=task, session_id=session_id)
            self.finish_session(session_id, "completed")
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            self.finish_session(session_id, "failed", str(error), agent_name=agent.name)
            return AgentResult("failed", None, str(error), session_id)

    def start_session(self, *, agent: Agent, task: Task) -> str:
        return self.trace.create_session(task.description, agent.name)

    def run_turn(
        self,
        *,
        agent: Agent,
        task: Task,
        session_id: str,
        messages: tuple[Message, ...] | list[Message] | None = None,
        record_initial_messages: bool = True,
    ) -> BaseModel:
        return agent.run(
            task,
            messages=messages,
            max_turns=self.max_turns,
            trace=self.trace,
            session_id=session_id,
            record_initial_messages=record_initial_messages,
        )

    def finish_session(self, session_id: str, status: str, error: str | None = None, *, agent_name: str | None = None) -> None:
        if error is not None and agent_name is not None:
            self.trace.record(session_id, agent_name, "error", error_type="RuntimeError", error_message=error)
        self.trace.finish_session(session_id, status, error)
