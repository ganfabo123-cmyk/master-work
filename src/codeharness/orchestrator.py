from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path

from .agents import Agent, WerewolfPlayerAgent
from .llm import LLMClient, OpenAICompatibleClient
from .models import AgentResult, Message, Task
from .room import AgentProfile, Room, RoomMessage
from .tools import ToolRegistry
from .trace import TraceRecorder
from .util.werewolf_actions import latest_valid_actions
from .util.werewolf_rules import GameEvent, finish_as_draw, resolve_phase
from .util.werewolf_state import Phase, Role, WerewolfGameState, actors_for_phase, load_state, phase_announcement, player_visible_state, save_state
from .util.werewolf_tools import tools_for_player

AgentFactory = Callable[[AgentProfile], Agent]
_PLAYER_FACTORY = "werewolf-player"
_ENGINE_NAME = "game-engine"


@dataclass(slots=True)
class WerewolfSession:
    session_id: str
    room: Room
    agents: dict[str, Agent]
    messages: dict[str, list[Message]]
    state: WerewolfGameState


class Orchestrator:
    """Owns session lifecycle and deterministic orchestration for one AI werewolf game."""

    def __init__(
        self,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 8,
        max_game_rounds: int = 12,
        llm: LLMClient | None = None,
        model: str | None = None,
    ) -> None:
        self.trace = TraceRecorder(traces_root)
        self.room_data_root = room_data_root
        self.max_turns = max_turns
        self.max_game_rounds = max_game_rounds
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
        orchestrator = cls(traces_root=traces_root, room_data_root=room_data_root, max_turns=max_turns, llm=client, model=model)
        orchestrator.register_agent_factory(
            _PLAYER_FACTORY,
            lambda profile: WerewolfPlayerAgent(client, model, name=profile.name, role=Role(str(profile.kwargs["identity"]))),
        )
        return orchestrator

    def run(
        self,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: Callable[[str], None] | None = None,
    ) -> AgentResult:
        """Open or restore one game, then directly drive its deterministic phase loop."""
        game = self._open_or_restore_werewolf_session(task=task, session_id=session_id)
        if on_session_opened is not None:
            on_session_opened(game.session_id)
        try:
            while game.state.phase is not Phase.FINISHED:
                self._publish_game_events(game.room, (GameEvent(phase_announcement(game.state)),))
                for player_name in actors_for_phase(game.state):
                    agent = game.agents[player_name]
                    registry, tools = tools_for_player(room=game.room, actor=player_name, state=game.state)
                    self.run_room_turn(
                        room=game.room,
                        agent_name=player_name,
                        task=task,
                        session_id=game.session_id,
                        messages=game.messages[player_name] or None,
                        tools=tools,
                        tool_registry=registry,
                        extra_inputs={"werewolf": player_visible_state(game.state)},
                    )
                    game.messages[player_name] = self._messages_or_empty(game.session_id, agent.name)

                engine_inbox = game.room.receive(_ENGINE_NAME)
                actions, rejected = latest_valid_actions(engine_inbox, game.state)
                for action, reason in rejected:
                    game.room.send(RoomMessage(name=_ENGINE_NAME, at=action.actor, txt=f"动作无效：{reason}"))
                    game.state.consumed_action_ids.add(action.message_id)
                game.state.consumed_action_ids.update(action.message_id for action in actions.values())
                game.state, events = resolve_phase(game.state, actions)
                if game.state.round_no > self.max_game_rounds and game.state.phase is not Phase.FINISHED:
                    game.state, draw_events = finish_as_draw(game.state)
                    events = (*events, *draw_events)
                self._publish_game_events(game.room, events)
                self._persist_game_state(game.session_id, game.state)

            self.trace.finish_session(game.session_id, "completed")
            winner = game.state.winner.value if game.state.winner is not None else "unknown"
            return AgentResult("completed", Message("assistant", f"狼人杀游戏结束，结果：{winner}。"), None, game.session_id)
        except Exception as error:
            self._persist_game_state(game.session_id, game.state)
            self.trace.finish_session(game.session_id, "failed", str(error))
            return AgentResult("failed", None, str(error), game.session_id)

    def _open_or_restore_werewolf_session(self, *, task: Task, session_id: str | None) -> WerewolfSession:
        if session_id is None:
            if self.llm is None or self.model is None:
                raise RuntimeError("Orchestrator needs llm and model to create a werewolf game")
            state = WerewolfGameState.random_eight_players()
            root_session_id = self.trace.create_session(task.description, "player-1", mode="werewolf")
            room = self.create_room(f"werewolf-{root_session_id}", session_id=root_session_id)
            self.trace.attach_room(root_session_id, room_id=room.room_id, room_session_id=room.session_id)
            self._register_engine(room)
            agents: dict[str, Agent] = {}
            for name, player in state.players.items():
                agent = WerewolfPlayerAgent(self.llm, self.model, name=name, role=player.role)
                profile = _player_profile(name, player.role)
                self.register_agent(agent, profile)
                agents[name] = agent
            self.invite_agents(room, tuple(agents), session_id=root_session_id)
            self._persist_game_state(root_session_id, state)
            return WerewolfSession(root_session_id, room, agents, {name: [] for name in agents}, state)

        data = self.trace.session_data(session_id)
        room_data = data.get("room")
        if data.get("mode") != "werewolf" or not isinstance(room_data, dict):
            raise ValueError(f"Session is not a resumable werewolf session: {session_id}")
        room_id, room_session_id = room_data.get("room_id"), room_data.get("session_id")
        if not isinstance(room_id, str) or not isinstance(room_session_id, str):
            raise ValueError(f"Session has invalid ROOM metadata: {session_id}")
        self.trace.resume_session_state(session_id)
        room = self.resume_room(room_id, session_id=room_session_id)
        profiles = {profile.name: profile for profile in room.registered_agents()}
        if _ENGINE_NAME not in room.participants():
            raise ValueError(f"Werewolf session is missing game-engine: {session_id}")
        agents: dict[str, Agent] = {}
        for name in room.participants():
            if name == _ENGINE_NAME:
                continue
            profile = profiles.get(name)
            if profile is None:
                raise ValueError(f"Werewolf session has no Profile for {name}")
            factory_name = profile.kwargs.get("factory")
            factory = self._agent_factories.get(factory_name) if isinstance(factory_name, str) else None
            if factory is None:
                raise ValueError(f"Werewolf session has no factory for {name}")
            agent = factory(profile)
            self.register_agent(agent, profile)
            agents[name] = agent
        state = load_state(self._game_state_path(session_id))
        if set(agents) != set(state.players):
            raise ValueError(f"Werewolf session players do not match persisted state: {session_id}")
        return WerewolfSession(session_id, room, agents, {name: self._messages_or_empty(session_id, name) for name in agents}, state)

    def _register_engine(self, room: Room) -> None:
        profile = AgentProfile(
            name=_ENGINE_NAME,
            introduction="Deterministic werewolf rules engine and public adjudicator.",
            skill=("werewolf-rules",),
            role="deterministic-rule-engine",
        )
        room.register(profile)
        room.invite(profile.name)

    def _publish_game_events(self, room: Room, events: Sequence[GameEvent]) -> None:
        for event in events:
            room.send(RoomMessage(name=_ENGINE_NAME, at=event.recipient, txt=event.text))

    def _game_state_path(self, session_id: str) -> Path:
        return self.trace.root / session_id / "werewolf_state.json"

    def _persist_game_state(self, session_id: str, state: WerewolfGameState) -> None:
        save_state(self._game_state_path(session_id), state)

    def _messages_or_empty(self, session_id: str, agent_name: str) -> list[Message]:
        try:
            return list(self.trace.messages(session_id, agent_name))
        except KeyError:
            return []

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
            agent, profile = self._agents.get(name), self._profiles.get(name)
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
        tools: tuple[Callable[..., object], ...] | None = None,
        tool_registry: ToolRegistry | None = None,
        extra_inputs: dict[str, object] | None = None,
    ) -> AgentResult:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent is not registered with Orchestrator: {agent_name}")
        inbox = room.receive(agent_name)
        werewolf = (extra_inputs or {}).get("werewolf")
        if isinstance(werewolf, dict):
            werewolf = {**werewolf, "inbox": [message.model_dump(mode="json") for message in inbox]}
        room_task = Task(
            task.description,
            {
                **task.inputs,
                "room": {"room_id": room.room_id, "session_id": room.session_id, "inbox": [message.model_dump(mode="json") for message in inbox]},
                **(extra_inputs or {}),
                **({"werewolf": werewolf} if werewolf is not None else {}),
            },
        )
        history = list(messages) if messages else None
        if history is not None:
            history.append(_user_message_for_task(agent, room_task))
        self.trace.record(session_id, agent.name, "room_inbox", room_id=room.room_id, room_session_id=room.session_id, message_ids=tuple(message.message_id for message in inbox))
        try:
            output = agent.run(
                room_task,
                messages=history,
                tools=tools,
                tool_registry=tool_registry,
                max_turns=self.max_turns,
                trace=self.trace,
                session_id=session_id,
                record_initial_messages=history is None,
            )
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            return AgentResult("failed", None, str(error), session_id)


def _player_profile(name: str, role: Role) -> AgentProfile:
    return AgentProfile(
        name=name,
        introduction="AI participant in a classic eight-player werewolf game.",
        skill=(f"werewolf-{role.value}",),
        role="werewolf-player",
        kwargs={"factory": _PLAYER_FACTORY, "identity": role.value},
    )


def _user_message_for_task(agent: Agent, task: Task) -> Message:
    messages = agent.initial_messages(task)
    user_messages = [message for message in messages if message.role == "user"]
    if len(user_messages) != 1:
        raise ValueError(f"Agent '{agent.name}' must build exactly one user message per request")
    return user_messages[0]
