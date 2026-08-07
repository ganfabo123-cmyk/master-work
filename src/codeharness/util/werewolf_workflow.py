"""The werewolf demonstration workflow built on the generic collaboration harness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ..agents import Agent, WerewolfPlayerAgent
from ..context import IncrementalContext
from ..models import AgentResult, Message, Task
from ..room import AgentProfile, Room, RoomMessage
from ..tools.utils import available_werewolf_actions
from .werewolf_actions import latest_valid_actions
from .werewolf_rules import GameEvent, finish_as_draw, resolve_phase
from .werewolf_state import Phase, Role, WerewolfGameState, actors_for_phase, load_state, phase_announcement, player_visible_state, save_state

if TYPE_CHECKING:
    from ..orchestrator import Orchestrator


_ENGINE_NAME = "game-engine"


@dataclass(slots=True)
class WerewolfWorkflowConfig:
    max_game_rounds: int = 12


@dataclass(slots=True)
class WerewolfSession:
    session_id: str
    public_room: Room
    wolf_room: Room
    agents: dict[str, Agent]
    contexts: dict[str, IncrementalContext]
    state: WerewolfGameState


def run_werewolf_workflow(
    orchestrator: Orchestrator,
    *,
    task: Task,
    session_id: str | None,
    on_session_opened: Callable[[str], None] | None,
    config: WerewolfWorkflowConfig | None = None,
) -> AgentResult:
    config = config or WerewolfWorkflowConfig()
    game = open_or_restore_werewolf_session(orchestrator, task=task, session_id=session_id)
    if on_session_opened is not None:
        on_session_opened(game.session_id)
    try:
        while game.state.phase is not Phase.FINISHED:
            _publish_game_events(game.public_room, (GameEvent(phase_announcement(game.state)),))
            for player_name in actors_for_phase(game.state):
                agent = game.agents[player_name]
                is_wolf = game.state.role_of(player_name) is Role.WOLF
                available_tool_names = _available_tool_names(game.state, player_name)
                turn = orchestrator.run_room_turn(
                    room=game.public_room,
                    additional_rooms=(game.wolf_room,) if is_wolf else (),
                    agent_name=player_name,
                    task=task,
                    session_id=game.session_id,
                    incremental_context=game.contexts[player_name],
                    events=(_game_state_event(game.state, available_tool_names),),
                    available_tool_names=available_tool_names,
                )
                if turn.status == "failed":
                    raise RuntimeError(f"Werewolf turn failed for {player_name}: {turn.error}")

            if game.state.phase is Phase.REVIEW:
                game.state.phase = Phase.FINISHED
                _persist_game_state(orchestrator, game.session_id, game.state)
                continue

            if game.state.phase is Phase.PREPARATION:
                game.state.phase = Phase.NIGHT_WOLF_DISCUSSION
                _persist_game_state(orchestrator, game.session_id, game.state)
                continue

            engine_inbox = game.public_room.receive(_ENGINE_NAME)
            actions, rejected = latest_valid_actions(engine_inbox, game.state)
            for action, reason in rejected:
                game.public_room.send(RoomMessage(name=_ENGINE_NAME, at=action.actor, txt=f"动作无效：{reason}"))
                game.state.consumed_action_ids.add(action.message_id)
            game.state.consumed_action_ids.update(action.message_id for action in actions.values())
            game.state, events = resolve_phase(game.state, actions)
            if game.state.round_no > config.max_game_rounds and game.state.phase not in {Phase.REVIEW, Phase.FINISHED}:
                game.state, draw_events = finish_as_draw(game.state)
                events = (*events, *draw_events)
            _publish_game_events(game.public_room, events)
            _persist_game_state(orchestrator, game.session_id, game.state)

        orchestrator.trace.finish_session(game.session_id, "completed")
        winner = game.state.winner.value if game.state.winner is not None else "unknown"
        return AgentResult("completed", Message("assistant", f"狼人杀游戏结束，结果：{winner}。"), None, game.session_id)
    except Exception as error:
        _persist_game_state(orchestrator, game.session_id, game.state)
        orchestrator.trace.finish_session(game.session_id, "failed", str(error))
        return AgentResult("failed", None, str(error), game.session_id)


def open_or_restore_werewolf_session(orchestrator: Orchestrator, *, task: Task, session_id: str | None) -> WerewolfSession:
    if session_id is None:
        if orchestrator.llm is None or orchestrator.model is None:
            raise RuntimeError("Werewolf workflow needs an llm and model")
        state = WerewolfGameState.random_eight_players()
        root_session_id = orchestrator.trace.create_session(task.description, "player-1", mode="werewolf")
        public_room = orchestrator.create_room(f"werewolf-public-{root_session_id}", session_id=root_session_id)
        wolf_room = orchestrator.create_room(f"werewolf-wolves-{root_session_id}", session_id=root_session_id)
        orchestrator.trace.update_session_metadata(
            root_session_id,
            public_room_id=public_room.room_id,
            werewolf_rooms={"public_room_id": public_room.room_id, "wolf_room_id": wolf_room.room_id},
        )
        _register_engine(public_room, wolf_room)
        agents: dict[str, Agent] = {}
        for name, player in state.players.items():
            agent = WerewolfPlayerAgent(
                orchestrator.llm,
                orchestrator.model,
                name=name,
                role=player.role,
                public_room=public_room,
                state=state,
                wolf_room=wolf_room,
            )
            profile = _player_profile(name, player.role)
            orchestrator.register_agent(agent, profile)
            agents[name] = agent
        orchestrator.invite_agents(public_room, tuple(agents), session_id=root_session_id)
        orchestrator.invite_agents(wolf_room, tuple(name for name, player in state.players.items() if player.role is Role.WOLF), session_id=root_session_id)
        _persist_game_state(orchestrator, root_session_id, state)
        contexts = {name: orchestrator.open_incremental_context(agent_name=name, task=task, session_id=root_session_id) for name in agents}
        return WerewolfSession(root_session_id, public_room, wolf_room, agents, contexts, state)

    data = orchestrator.trace.session_data(session_id)
    room_metadata = data.get("werewolf_rooms")
    if data.get("mode") != "werewolf" or not isinstance(room_metadata, dict):
        raise ValueError(f"Session is not a resumable werewolf session: {session_id}")
    public_room_id, wolf_room_id = room_metadata.get("public_room_id"), room_metadata.get("wolf_room_id")
    if not isinstance(public_room_id, str) or not isinstance(wolf_room_id, str):
        raise ValueError(f"Session has invalid werewolf ROOM metadata: {session_id}")
    orchestrator.trace.resume_session_state(session_id)
    public_room = orchestrator.resume_room(public_room_id, session_id=session_id)
    wolf_room = orchestrator.resume_room(wolf_room_id, session_id=session_id)
    if _ENGINE_NAME not in public_room.participants():
        raise ValueError(f"Werewolf session is missing game-engine: {session_id}")
    state = load_state(_game_state_path(orchestrator, session_id))
    if orchestrator.llm is None or orchestrator.model is None:
        raise RuntimeError("Werewolf workflow needs an llm and model")
    agent_names = tuple(name for name in public_room.participants() if name != _ENGINE_NAME)
    agents: dict[str, Agent] = {}
    for name in agent_names:
        player = state.players.get(name)
        if player is None:
            raise ValueError(f"Werewolf session is missing state for player: {name}")
        agent = WerewolfPlayerAgent(
            orchestrator.llm,
            orchestrator.model,
            name=name,
            role=player.role,
            public_room=public_room,
            state=state,
            wolf_room=wolf_room,
        )
        orchestrator.register_agent(agent, _player_profile(name, player.role))
        agents[name] = agent
    if set(agents) != set(state.players):
        raise ValueError(f"Werewolf session players do not match persisted state: {session_id}")
    wolves = {name for name, player in state.players.items() if player.role is Role.WOLF}
    if set(wolf_room.participants()) != {_ENGINE_NAME, *wolves}:
        raise ValueError(f"Werewolf private ROOM members do not match wolf identities: {session_id}")
    contexts = {name: orchestrator.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
    return WerewolfSession(session_id, public_room, wolf_room, agents, contexts, state)

def _register_engine(*rooms: Room) -> None:
    profile = AgentProfile(
        name=_ENGINE_NAME,
        introduction="Deterministic werewolf rules engine and public adjudicator.",
        skill=("werewolf-rules",),
        role="deterministic-rule-engine",
    )
    for room in rooms:
        room.register(profile)
        room.invite(profile.name)


def _player_profile(name: str, role: Role) -> AgentProfile:
    return AgentProfile(
        name=name,
        introduction="AI participant in a classic eight-player werewolf game.",
        skill=(f"werewolf-{role.value}",),
        role="werewolf-player",
        kwargs={"identity": role.value},
    )


def _publish_game_events(room: Room, events: tuple[GameEvent, ...]) -> None:
    for event in events:
        room.send(RoomMessage(name=_ENGINE_NAME, at=event.recipient, txt=event.text))


def _available_tool_names(state: WerewolfGameState, player_name: str) -> tuple[str, ...]:
    names = ["think", "list_experiences", "get_experience"]
    if state.phase is Phase.PREPARATION:
        return tuple(names)
    names.append("save_experience")
    if state.phase is Phase.NIGHT_WOLF_DISCUSSION and state.role_of(player_name) is Role.WOLF:
        names.append("wolf_message")
    if state.phase is Phase.DAY_DISCUSSION:
        names.append("speak")
    names.extend(action.value for action in available_werewolf_actions(state, player_name))
    return tuple(names)


def _game_state_event(state: WerewolfGameState, available_tool_names: tuple[str, ...]) -> Message:
    return Message(
        "user",
        json.dumps(
            {
                "type": "game_state",
                **player_visible_state(state),
                "available_actions": available_tool_names,
            },
            ensure_ascii=False,
        ),
    )


def _game_state_path(orchestrator: Orchestrator, session_id: str) -> Path:
    return orchestrator.trace.root / session_id / "werewolf_state.json"


def _persist_game_state(orchestrator: Orchestrator, session_id: str, state: WerewolfGameState) -> None:
    save_state(_game_state_path(orchestrator, session_id), state)
