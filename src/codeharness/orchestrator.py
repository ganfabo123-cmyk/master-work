from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import json
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
    public_room: Room
    wolf_room: Room
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
                self._publish_game_events(game.public_room, (GameEvent(phase_announcement(game.state)),))
                for player_name in actors_for_phase(game.state):
                    agent = game.agents[player_name]
                    is_wolf = game.state.role_of(player_name) is Role.WOLF
                    registry, tools = tools_for_player(
                        room=game.public_room,
                        wolf_room=game.wolf_room if is_wolf else None,
                        actor=player_name,
                        state=game.state,
                    )
                    turn = self.run_room_turn(
                        room=game.public_room,
                        additional_rooms=(game.wolf_room,) if is_wolf else (),
                        agent_name=player_name,
                        task=task,
                        session_id=game.session_id,
                        messages=game.messages[player_name] or None,
                        tools=tools,
                        tool_registry=registry,
                        extra_inputs={
                            "werewolf": {
                                **player_visible_state(game.state),
                                "available_actions": tuple(tool.__name__ for tool in tools if tool.__name__ != "think"),
                            }
                        },
                    )
                    if turn.status == "failed":
                        raise RuntimeError(f"Werewolf turn failed for {player_name}: {turn.error}")
                    game.messages[player_name] = self._messages_or_empty(game.session_id, agent.name)

                engine_inbox = game.public_room.receive(_ENGINE_NAME)
                actions, rejected = latest_valid_actions(engine_inbox, game.state)
                for action, reason in rejected:
                    game.public_room.send(RoomMessage(name=_ENGINE_NAME, at=action.actor, txt=f"动作无效：{reason}"))
                    game.state.consumed_action_ids.add(action.message_id)
                game.state.consumed_action_ids.update(action.message_id for action in actions.values())
                game.state, events = resolve_phase(game.state, actions)
                if game.state.round_no > self.max_game_rounds and game.state.phase is not Phase.FINISHED:
                    game.state, draw_events = finish_as_draw(game.state)
                    events = (*events, *draw_events)
                self._publish_game_events(game.public_room, events)
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
            public_room = self.create_room(f"werewolf-public-{root_session_id}", session_id=root_session_id)
            wolf_room = self.create_room(f"werewolf-wolves-{root_session_id}", session_id=root_session_id)
            self.trace.update_session_metadata(
                root_session_id,
                werewolf_rooms={"public_room_id": public_room.room_id, "wolf_room_id": wolf_room.room_id},
            )
            self._register_engine(public_room, wolf_room)
            agents: dict[str, Agent] = {}
            for name, player in state.players.items():
                agent = WerewolfPlayerAgent(self.llm, self.model, name=name, role=player.role)
                profile = _player_profile(name, player.role)
                self.register_agent(agent, profile)
                agents[name] = agent
            self.invite_agents(public_room, tuple(agents), session_id=root_session_id)
            self.invite_agents(wolf_room, tuple(name for name, player in state.players.items() if player.role is Role.WOLF), session_id=root_session_id)
            self._persist_game_state(root_session_id, state)
            return WerewolfSession(root_session_id, public_room, wolf_room, agents, {name: [] for name in agents}, state)

        data = self.trace.session_data(session_id)
        room_metadata = data.get("werewolf_rooms")
        if data.get("mode") != "werewolf" or not isinstance(room_metadata, dict):
            raise ValueError(f"Session is not a resumable werewolf session: {session_id}")
        public_room_id, wolf_room_id = room_metadata.get("public_room_id"), room_metadata.get("wolf_room_id")
        if not isinstance(public_room_id, str) or not isinstance(wolf_room_id, str):
            raise ValueError(f"Session has invalid werewolf ROOM metadata: {session_id}")
        self.trace.resume_session_state(session_id)
        public_room = self.resume_room(public_room_id, session_id=session_id)
        wolf_room = self.resume_room(wolf_room_id, session_id=session_id)
        profiles = {profile.name: profile for profile in public_room.registered_agents()}
        if _ENGINE_NAME not in public_room.participants():
            raise ValueError(f"Werewolf session is missing game-engine: {session_id}")
        agents: dict[str, Agent] = {}
        for name in public_room.participants():
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
        if set(wolf_room.participants()) != {_ENGINE_NAME, *(name for name, player in state.players.items() if player.role is Role.WOLF)}:
            raise ValueError(f"Werewolf private ROOM members do not match wolf identities: {session_id}")
        return WerewolfSession(session_id, public_room, wolf_room, agents, {name: self._messages_or_empty(session_id, name) for name in agents}, state)

    def _register_engine(self, *rooms: Room) -> None:
        profile = AgentProfile(
            name=_ENGINE_NAME,
            introduction="Deterministic werewolf rules engine and public adjudicator.",
            skill=("werewolf-rules",),
            role="deterministic-rule-engine",
        )
        for room in rooms:
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
        room_session_id = session_id or room_id
        key = (room_session_id, room_id)
        if key in self._rooms:
            raise ValueError(f"ROOM already exists: {room_id} ({room_session_id})")
        callbacks = self._room_message_callbacks(room_session_id)
        room = Room(room_id, session_id=room_session_id, data_root=self.room_data_root, **callbacks)
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
        """Return the ROOMs currently loaded for one root session."""
        return tuple(room for (loaded_session_id, _), room in self._rooms.items() if loaded_session_id == session_id)

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
        additional_rooms: Sequence[Room] = (),
        messages: list[Message] | None = None,
        tools: tuple[Callable[..., object], ...] | None = None,
        tool_registry: ToolRegistry | None = None,
        extra_inputs: dict[str, object] | None = None,
    ) -> AgentResult:
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent is not registered with Orchestrator: {agent_name}")
        rooms = (room, *additional_rooms)
        inboxes = {active_room.room_id: active_room.receive(agent_name) for active_room in rooms}
        inbox = inboxes[room.room_id]
        rooms_input = {
            room_id: {
                "room_id": active_room.room_id,
                "session_id": active_room.session_id,
                "inbox": [message.model_dump(mode="json") for message in inboxes[room_id]],
            }
            for room_id, active_room in ((active_room.room_id, active_room) for active_room in rooms)
        }
        werewolf = (extra_inputs or {}).get("werewolf")
        if isinstance(werewolf, dict):
            werewolf = {**werewolf, "inbox": [message.model_dump(mode="json") for message in inbox], "rooms": rooms_input}
        room_task = Task(
            task.description,
            {
                **task.inputs,
                "room": {"room_id": room.room_id, "session_id": room.session_id, "inbox": [message.model_dump(mode="json") for message in inbox]},
                "rooms": rooms_input,
                **(extra_inputs or {}),
                **({"werewolf": werewolf} if werewolf is not None else {}),
            },
        )
        history = list(messages) if messages else None
        is_werewolf_turn = isinstance(werewolf, dict)
        if is_werewolf_turn:
            if history is None:
                history = list(agent.initial_messages(Task(task.description)))
                _record_prompt_messages(self.trace, session_id, agent.name, history)
            turn_messages = _werewolf_turn_events(werewolf, rooms, inboxes)
            history.extend(turn_messages)
            _record_prompt_messages(self.trace, session_id, agent.name, turn_messages)
        elif history is not None:
            turn_messages = _turn_messages_for_task(agent, room_task)
            history.extend(turn_messages)
            _record_prompt_messages(self.trace, session_id, agent.name, turn_messages)
        self.trace.record(
            session_id,
            agent.name,
            "room_inbox",
            rooms={room_id: tuple(message.message_id for message in messages) for room_id, messages in inboxes.items()},
        )
        try:
            output = agent.run(
                room_task,
                messages=history,
                tools=tools,
                tool_registry=tool_registry,
                max_turns=self.max_turns,
                trace=self.trace,
                session_id=session_id,
                record_initial_messages=False if is_werewolf_turn else history is None,
            )
            return AgentResult("completed", output, None, session_id)
        except Exception as error:
            self.trace.record(session_id, agent.name, "error", stage="run_room_turn", error=str(error))
            return AgentResult("failed", None, str(error), session_id)


def _player_profile(name: str, role: Role) -> AgentProfile:
    return AgentProfile(
        name=name,
        introduction="AI participant in a classic eight-player werewolf game.",
        skill=(f"werewolf-{role.value}",),
        role="werewolf-player",
        kwargs={"factory": _PLAYER_FACTORY, "identity": role.value},
    )


def _turn_messages_for_task(agent: Agent, task: Task) -> tuple[Message, ...]:
    messages = agent.initial_messages(task)
    user_messages = [message for message in messages if message.role == "user"]
    if len(user_messages) != 1:
        raise ValueError(f"Agent '{agent.name}' must build exactly one user message per request")
    return messages


def _werewolf_turn_events(
    state: dict[str, object],
    rooms: Sequence[Room],
    inboxes: dict[str, tuple[RoomMessage, ...]],
) -> tuple[Message, ...]:
    game_state = {
        "type": "game_state",
        "round_no": state.get("round_no"),
        "phase": state.get("phase"),
        "alive_players": state.get("alive_players", ()),
        "available_actions": state.get("available_actions", ()),
    }
    events = [Message("user", json.dumps(game_state, ensure_ascii=False))]
    for room in rooms:
        for message in inboxes[room.room_id]:
            events.append(
                Message(
                    "user",
                    json.dumps(
                        {
                            "type": "room_message",
                            "room_id": room.room_id,
                            "sender": message.name,
                            "recipients": message.at,
                            "content": {"txt": message.txt, "image": message.image, "audio": message.audio},
                        },
                        ensure_ascii=False,
                    ),
                )
            )
    return tuple(events)


def _record_prompt_messages(trace: TraceRecorder, session_id: str, agent_name: str, messages: Sequence[Message]) -> None:
    for message in messages:
        trace_message = message.as_dict()
        event_type = "system" if message.role == "developer" else message.role
        trace.record(session_id, agent_name, event_type, message=trace_message)
