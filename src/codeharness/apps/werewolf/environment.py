"""狼人杀环境：会话编排、动作结算和状态推进。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from .agent import WerewolfPlayerAgent
from .action import ActionName, WerewolfAction
from ...infra.runtimes import IncrementalContext
from ...core.base_agent import Agent
from ...core.base_environment import ActionManager, Environment
from ...core.base_observation import Observation
from ...core.base_state import State
from ...infra import StateStore
from ...infra.tool_registry import ToolRegistry
from ...core.models import AgentResult, Message, Task
from ...infra.client import LLMClient, OpenAICompatibleClient
from .observation import WerewolfObservation, WerewolfTurnObservation
from ...infra.room import AgentProfile, Room, RoomMessage, RoomTurnContext
from ...infra.session import SessionManager
from .state import Death, Phase, Role, WerewolfGameState, Winner

ENGINE_NAME = "game-engine"


@dataclass(frozen=True, slots=True)
class GameEvent:
    text: str
    recipient: str = "all"
    private: bool = False


@dataclass(frozen=True, slots=True)
class GameAction:
    message_id: str
    actor: str
    action: ActionName
    target: str | None
    round_no: int
    phase: Phase


class WerewolfActionManager(ActionManager):
    def __init__(self, action: WerewolfAction) -> None:
        self.action = action

    def resolve_action(self, response: Any) -> GameAction | None:
        if not isinstance(response, RoomMessage) or not isinstance(response.txt, str):
            return None
        try:
            payload = json.loads(response.txt)
            if not isinstance(payload, dict) or payload.get("type") != "werewolf.action":
                return None
            mapped_action = self.action.get_action(str(payload["action"]))
            target = payload.get("target")
            return GameAction(
                message_id=response.message_id,
                actor=response.name,
                action=ActionName(mapped_action.name),
                target=target if isinstance(target, str) else None,
                round_no=int(payload["round"]),
                phase=Phase(payload["phase"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def validate_action(self, action: GameAction, state: WerewolfGameState) -> bool:
        return self._validation_error(action, state) is None

    def available_actions(self, state: WerewolfGameState, agent: Agent) -> tuple[ActionName, ...]:
        agent_name = agent.name
        role = state.role_of(agent_name)
        if state.phase is Phase.NIGHT_WOLF_KILL and role is Role.WOLF:
            return (ActionName.WOLF_KILL,)
        if state.phase is Phase.NIGHT_SEER and role is Role.SEER:
            return (ActionName.INSPECT,)
        if state.phase is Phase.NIGHT_WITCH and role is Role.WITCH:
            return tuple(
                action
                for action, enabled in (
                    (ActionName.SAVE, state.witch_has_antidote),
                    (ActionName.POISON, state.witch_has_poison),
                )
                if enabled
            )
        if state.phase is Phase.DAY_VOTE:
            return (ActionName.VOTE,)
        if state.phase is Phase.HUNTER_SHOT and agent_name == state.hunter_name:
            return (ActionName.SHOOT, ActionName.SKIP_SHOT)
        return ()

    def latest_valid_actions(
        self,
        messages: tuple[RoomMessage, ...],
        state: WerewolfGameState,
    ) -> tuple[dict[str, GameAction], list[tuple[GameAction, str]]]:
        accepted: dict[str, GameAction] = {}
        rejected: list[tuple[GameAction, str]] = []
        for message in messages:
            action = self.resolve_action(message)
            if action is None:
                continue
            reason = self._validation_error(action, state)
            if reason is not None:
                rejected.append((action, reason))
                continue
            accepted[action.actor] = action
        return accepted, rejected

    def majority_target(self, actions: dict[str, GameAction], expected: ActionName) -> str | None:
        targets = [action.target for action in actions.values() if action.action is expected and action.target is not None]
        if not targets:
            return None
        counts = Counter(targets)
        highest = max(counts.values())
        winners = [target for target, count in counts.items() if count == highest]
        return winners[0] if len(winners) == 1 else None

    def first_action(self, actions: dict[str, GameAction], expected: ActionName) -> GameAction | None:
        return next((action for action in actions.values() if action.action is expected), None)

    @staticmethod
    def _validation_error(action: GameAction, state: WerewolfGameState) -> str | None:
        if action.message_id in state.consumed_action_ids:
            return "该动作已经结算。"
        hunter_final_action = action.action in {ActionName.SHOOT, ActionName.SKIP_SHOT} and state.hunter_name == action.actor
        if not state.is_alive(action.actor) and not hunter_final_action:
            return "死亡玩家不能行动。"
        if action.round_no != state.round_no or action.phase is not state.phase:
            return "动作不属于当前回合或阶段。"
        role = state.role_of(action.actor)
        target_actions = {ActionName.WOLF_KILL, ActionName.INSPECT, ActionName.POISON, ActionName.VOTE, ActionName.SHOOT}
        if action.action in target_actions and (action.target is None or not state.is_alive(action.target)):
            return "目标必须是存活玩家。"
        if action.action is ActionName.WOLF_KILL:
            if state.phase is not Phase.NIGHT_WOLF_KILL or role is not Role.WOLF:
                return "当前无权发动狼人击杀。"
            if action.target is not None and state.role_of(action.target) is Role.WOLF:
                return "狼人不能击杀狼人。"
        elif action.action is ActionName.INSPECT:
            if state.phase is not Phase.NIGHT_SEER or role is not Role.SEER:
                return "当前无权查验。"
            if action.target == action.actor:
                return "不能查验自己。"
        elif action.action is ActionName.SAVE:
            if state.phase is not Phase.NIGHT_WITCH or role is not Role.WITCH or not state.witch_has_antidote:
                return "当前无权使用解药。"
            if state.wolf_target is None:
                return "今晚无人被狼刀，不能使用解药。"
        elif action.action is ActionName.POISON:
            if state.phase is not Phase.NIGHT_WITCH or role is not Role.WITCH or not state.witch_has_poison:
                return "当前无权使用毒药。"
        elif action.action is ActionName.VOTE:
            if state.phase is not Phase.DAY_VOTE:
                return "当前不是投票阶段。"
            if action.target == action.actor:
                return "不能投票给自己。"
        elif action.action in {ActionName.SHOOT, ActionName.SKIP_SHOT}:
            if state.phase is not Phase.HUNTER_SHOT or role is not Role.HUNTER or state.hunter_name != action.actor:
                return "当前无权发动猎人技能。"
        return None


@dataclass(slots=True)
class WerewolfWorkflowConfig:
    max_game_rounds: int = 12


@dataclass(slots=True)
class WerewolfSession:
    session_id: str
    public_room: Room
    wolf_room: Room
    agents: dict[str, WerewolfPlayerAgent]
    contexts: dict[str, IncrementalContext]
    state: WerewolfGameState
    state_store: StateStore


class WerewolfEnvironment(Environment):
    """Run one complete werewolf game through the generic ROOM services."""

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 8) -> None:
        self.session = session
        self.trace = session.trace
        self.llm = llm
        self.model = model
        self.max_turns = max_turns
        self.action_manager: WerewolfActionManager | None = None
        self._rl_game: WerewolfSession | None = None
        self._rl_task: Task | None = None
        self._agents: dict[str, Agent] = {}
        self._profiles: dict[str, AgentProfile] = {}
        placeholder = WerewolfGameState.initial("", "")
        super().__init__(agents=(), state=placeholder, observation=WerewolfObservation(), trace=session.trace)

    @classmethod
    def from_environment(
        cls,
        *,
        traces_root: Path = Path("traces"),
        room_data_root: Path = Path("room/data"),
        max_turns: int = 8,
    ) -> "WerewolfEnvironment":
        return cls(
            SessionManager(traces_root=traces_root, room_data_root=room_data_root),
            llm=OpenAICompatibleClient.from_environment(),
            model=os.getenv("CODEHARNESS_MODEL", "deepseek-v4-flash"),
            max_turns=max_turns,
        )

    def run(
        self,
        *,
        task: Task,
        session_id: str | None = None,
        on_session_opened: Callable[[str], None] | None = None,
        config: WerewolfWorkflowConfig | None = None,
    ) -> AgentResult:
        game = open_or_restore_session(self, task=task, session_id=session_id)
        self._rl_game = game
        self._rl_task = task
        self.agents = tuple(game.agents.values())
        self.state = game.state
        self.observation = WerewolfObservation()
        self.action_manager = WerewolfActionManager(next(iter(game.agents.values())).action)
        if on_session_opened:
            on_session_opened(game.session_id)
        config = config or WerewolfWorkflowConfig()
        try:
            state = game.state
            while state.phase is not Phase.FINISHED:
                publish_events(game.public_room, (GameEvent(phase_announcement(state)),))

                actions: dict[str, GameAction] = {}
                for player_name in actors_for_phase(state):
                    agent = game.agents[player_name]

                    # State → Observation
                    observation = self.observe(state, agent)

                    # Observation → Policy → Action
                    action = self.act(agent, observation)
                    if action is not None:
                        actions[action.actor] = action

                # Action → Environment → New State
                state = self.step(state, actions)

                if state.round_no > config.max_game_rounds and state.phase not in {Phase.REVIEW, Phase.FINISHED}:
                    state, events = finish_as_draw(state)
                    publish_events(game.public_room, events)
                    persist(game.state_store, game.session_id, state)
                    game.state = state
                    self.state = state
            self.finish_trace(game.session_id, "completed")
            winner = state.winner.value if state.winner else "unknown"
            return AgentResult("completed", Message("assistant", f"狼人杀游戏结束，结果：{winner}。"), None, game.session_id)
        except Exception as error:
            persist(game.state_store, game.session_id, game.state)
            self.finish_trace(game.session_id, "failed", str(error))
            return AgentResult("failed", None, str(error), game.session_id)

    def observe(self, state: State, agent: Agent) -> Observation:
        """Create one Agent-visible Observation from the current State."""
        game = self._require_rl_game()
        current = self._require_werewolf_state(state)
        manager = self._require_action_manager()
        names = available_tool_names(current, agent, manager)
        return WerewolfTurnObservation(
            state_message=WerewolfObservation().game_state_message(current, names),
            available_tool_names=names,
            public_room=game.public_room,
            additional_rooms=(game.wolf_room,) if current.role_of(agent.name) is Role.WOLF else (),
            task_id=current.task_id,
            session_id=current.session_id,
        )

    def act(self, agent: Agent, observation: Observation) -> GameAction | None:
        """Run the Agent Policy on an Observation and resolve its structured Action."""
        game = self._require_rl_game()
        task = self._require_rl_task()
        manager = self._require_action_manager()
        if not isinstance(observation, WerewolfTurnObservation):
            raise TypeError("observation must be WerewolfTurnObservation")

        turn = self.run_room_turn(
            room=observation.public_room,
            additional_rooms=observation.additional_rooms,
            agent_name=agent.name,
            task=task,
            session_id=game.session_id,
            incremental_context=game.contexts[agent.name],
            events=(observation.state_message,),
            available_tool_names=observation.available_tool_names,
        )
        if turn.status == "failed":
            raise RuntimeError(f"Werewolf turn failed for {agent.name}: {turn.error}")

        accepted, rejected = manager.latest_valid_actions(game.public_room.receive(ENGINE_NAME), game.state)
        for rejected_action, reason in rejected:
            if rejected_action.actor == agent.name:
                game.public_room.send(RoomMessage(name=ENGINE_NAME, at=agent.name, txt=f"动作无效：{reason}"))
        return accepted.get(agent.name)

    def step(self, state: State, action: Any) -> State:
        """Execute the phase Actions through Environment rules and return New State."""
        game = self._require_rl_game()
        current = self._require_werewolf_state(state)
        manager = self._require_action_manager()
        if not isinstance(action, dict) or not all(
            isinstance(name, str) and isinstance(value, GameAction)
            for name, value in action.items()
        ):
            raise TypeError("action must be dict[str, GameAction]")
        actions: dict[str, GameAction] = action

        current.consumed_action_ids.update(item.message_id for item in actions.values())
        if current.phase is Phase.PREPARATION:
            current.phase = Phase.NIGHT_WOLF_DISCUSSION
            events: tuple[GameEvent, ...] = ()
        elif current.phase is Phase.REVIEW:
            current.phase = Phase.FINISHED
            events = ()
        else:
            current, events = resolve_phase(current, actions, manager)

        publish_events(game.public_room, events)
        persist(game.state_store, game.session_id, current)
        game.state = current
        self.state = current
        return current

    def _require_rl_game(self) -> WerewolfSession:
        if self._rl_game is None:
            raise RuntimeError("WerewolfEnvironment.run() must initialize the game first")
        return self._rl_game

    def _require_rl_task(self) -> Task:
        if self._rl_task is None:
            raise RuntimeError("WerewolfEnvironment.run() must initialize the task first")
        return self._rl_task

    def _require_action_manager(self) -> WerewolfActionManager:
        if self.action_manager is None:
            raise RuntimeError("WerewolfEnvironment.run() must initialize the ActionManager first")
        return self.action_manager

    @staticmethod
    def _require_werewolf_state(state: State) -> WerewolfGameState:
        if not isinstance(state, WerewolfGameState):
            raise TypeError("state must be WerewolfGameState")
        return state

    def orchestrate_agents(self) -> Any:
        return self.run

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
        try:
            restored = self.trace.messages(session_id, agent_name)
        except KeyError:
            restored = ()
        context, initial = IncrementalContext.restore_or_initialize(
            restored_messages=restored,
            initial_messages=agent.initial_messages(Task(task.description)),
        )
        self.record_initial_trace(session_id, agent_name, initial)
        return context

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
            raise KeyError(f"Agent is not registered: {agent_name}")
        turn_context = RoomTurnContext.receive(session_id=session_id, room=room, additional_rooms=tuple(additional_rooms), agent_name=agent_name)
        room_task = Task(task.description, {**task.inputs, **turn_context.task_inputs(), **(extra_inputs or {})})
        history: list[Message] | None = None
        if incremental_context is not None:
            appended = incremental_context.append((*events, *turn_context.room_message_events()))
            self.record_trace_messages(session_id, agent.name, appended)
            history = list(incremental_context.history())
        self.record_room_inbox(session_id, agent.name, {room_id: tuple(message.message_id for message in inbox) for room_id, inbox in turn_context.inboxes.items()})
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
            self.record_agent_error(session_id, agent.name, stage="run_room_turn", error=str(error))
            return AgentResult("failed", None, str(error), session_id)


def open_or_restore_session(environment: WerewolfEnvironment, *, task: Task, session_id: str | None) -> WerewolfSession:
    store = StateStore(environment.trace.root.parent / "state" / "data")
    if session_id is None:
        session_id = environment.trace.create_session(task.description, "player-1", mode="werewolf")
        state = WerewolfGameState.random_eight_players(task_id=task.description, session_id=session_id)
        public = environment.session.create_room(f"werewolf-public-{session_id}", session_id=session_id)
        wolves = environment.session.create_room(f"werewolf-wolves-{session_id}", session_id=session_id)
        environment.trace.update_session_metadata(session_id, public_room_id=public.room_id, werewolf_rooms={"public_room_id": public.room_id, "wolf_room_id": wolves.room_id})
        register_engine(public, wolves)
        agents: dict[str, WerewolfPlayerAgent] = {}
        for name, player in state.players.items():
            agent = WerewolfPlayerAgent(environment.llm, environment.model, name=name, role=player.role, public_room=public, state=state, wolf_room=wolves)
            environment.register_agent(agent, player_profile(name, player.role))
            agents[name] = agent
        environment.invite_agents(public, tuple(agents), session_id=session_id)
        environment.invite_agents(wolves, tuple(name for name, player in state.players.items() if player.role is Role.WOLF), session_id=session_id)
        persist(store, session_id, state)
        contexts = {name: environment.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
        return WerewolfSession(session_id, public, wolves, agents, contexts, state, store)
    data = environment.trace.session_data(session_id)
    rooms = data.get("werewolf_rooms")
    if data.get("mode") != "werewolf" or not isinstance(rooms, dict):
        raise ValueError(f"Session is not a resumable werewolf session: {session_id}")
    public_id, wolf_id = rooms.get("public_room_id"), rooms.get("wolf_room_id")
    if not isinstance(public_id, str) or not isinstance(wolf_id, str):
        raise ValueError(f"Session has invalid werewolf ROOM metadata: {session_id}")
    environment.trace.resume_session_state(session_id)
    public, wolves = environment.session.resume_room(public_id, session_id=session_id), environment.session.resume_room(wolf_id, session_id=session_id)
    state = store.restore(session_id, "werewolf", WerewolfGameState)
    agents = {}
    for name in state.players:
        player = state.players[name]
        agent = WerewolfPlayerAgent(environment.llm, environment.model, name=name, role=player.role, public_room=public, state=state, wolf_room=wolves)
        environment.register_agent(agent, player_profile(name, player.role))
        agents[name] = agent
    contexts = {name: environment.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
    return WerewolfSession(session_id, public, wolves, agents, contexts, state, store)


def register_engine(*rooms: Room) -> None:
    profile = AgentProfile(name=ENGINE_NAME, introduction="Deterministic werewolf rules engine and public adjudicator.", skill=("werewolf-rules",), role="deterministic-rule-engine")
    for room in rooms:
        room.register(profile)
        room.invite(ENGINE_NAME)


def player_profile(name: str, role: Role) -> AgentProfile:
    return AgentProfile(name=name, introduction="AI participant in a classic eight-player werewolf game.", skill=(f"werewolf-{role.value}",), role="werewolf-player", kwargs={"identity": role.value})


def publish_events(room: Room, events: tuple[GameEvent, ...]) -> None:
    for event in events:
        room.send(RoomMessage(name=ENGINE_NAME, at=event.recipient, txt=event.text))


def available_tool_names(
    state: WerewolfGameState,
    agent: Agent,
    action_manager: WerewolfActionManager,
) -> tuple[str, ...]:
    player_name = agent.name
    names = ["think", "list_experiences", "get_experience"]
    if state.phase is Phase.PREPARATION:
        return tuple(names)
    names.append("save_experience")
    if state.phase is Phase.NIGHT_WOLF_DISCUSSION and state.role_of(player_name) is Role.WOLF:
        names.append("wolf_message")
    if state.phase is Phase.DAY_DISCUSSION:
        names.append("speak")
    names.extend(action.value for action in action_manager.available_actions(state, agent))
    return tuple(names)


def phase_announcement(state: WerewolfGameState) -> str:
    return {
        Phase.PREPARATION: "你已拿到身份。请认真准备并思考策略；如需参考过往复盘，可调用 list_experiences 查看自己的历史经验摘要，再用 get_experience 阅读详情。准备完成后直接结束本回合，等待游戏正式开始。",
        Phase.NIGHT_WOLF_DISCUSSION: f"第 {state.round_no} 夜：狼人请私下协商。",
        Phase.NIGHT_WOLF_KILL: "狼人协商结束，请提交击杀目标。",
        Phase.NIGHT_SEER: "预言家请查验。", Phase.NIGHT_WITCH: "女巫请行动。",
        Phase.HUNTER_SHOT: "猎人进入开枪阶段。", Phase.DAY_DISCUSSION: f"第 {state.round_no} 天：请公开讨论。",
        Phase.DAY_VOTE: "讨论结束，请投票放逐一名玩家。", Phase.REVIEW: "游戏结算已发送，请完成复盘。",
    }.get(state.phase, "请等待游戏继续。");


def actors_for_phase(state: WerewolfGameState) -> tuple[str, ...]:
    if state.phase in {Phase.PREPARATION, Phase.REVIEW}: return tuple(state.players)
    if state.phase in {Phase.NIGHT_WOLF_DISCUSSION, Phase.NIGHT_WOLF_KILL}: return state.alive_wolves()
    if state.phase is Phase.NIGHT_SEER: return tuple(n for n in state.alive_players() if state.role_of(n) is Role.SEER)
    if state.phase is Phase.NIGHT_WITCH: return tuple(n for n in state.alive_players() if state.role_of(n) is Role.WITCH)
    if state.phase in {Phase.DAY_DISCUSSION, Phase.DAY_VOTE}: return state.alive_players()
    if state.phase is Phase.HUNTER_SHOT and state.hunter_name: return (state.hunter_name,)
    return ()


def persist(store: StateStore, session_id: str, state: WerewolfGameState) -> None:
    store.update(session_id, "werewolf", state)


def resolve_phase(
    state: WerewolfGameState,
    actions: dict[str, GameAction],
    action_manager: WerewolfActionManager,
) -> tuple[WerewolfGameState, tuple[GameEvent, ...]]:
    events: list[GameEvent] = []
    if state.phase is Phase.NIGHT_WOLF_DISCUSSION:
        state.phase = Phase.NIGHT_WOLF_KILL; return state, (GameEvent("狼人请提交今晚的击杀目标。"),)
    if state.phase is Phase.NIGHT_WOLF_KILL:
        state.wolf_target = action_manager.majority_target(actions, ActionName.WOLF_KILL); state.phase = Phase.NIGHT_SEER; events.append(GameEvent("狼人行动结束，预言家请查验。"))
    elif state.phase is Phase.NIGHT_SEER:
        inspection = action_manager.first_action(actions, ActionName.INSPECT)
        if inspection and inspection.target: events.append(GameEvent(f"查验结果：{inspection.target} 是{'狼人' if state.role_of(inspection.target) is Role.WOLF else '好人'}。", inspection.actor, True))
        state.phase = Phase.NIGHT_WITCH; events.append(GameEvent("预言家行动结束，女巫请行动。"))
    elif state.phase is Phase.NIGHT_WITCH:
        state, night = resolve_witch_and_night(state, actions); events.extend(night)
    elif state.phase is Phase.DAY_DISCUSSION:
        state.phase = Phase.DAY_VOTE; events.append(GameEvent("讨论结束，请所有存活玩家投票。"))
    elif state.phase is Phase.DAY_VOTE:
        target = action_manager.majority_target(actions, ActionName.VOTE)
        if target is None: events.append(GameEvent("投票平票或无人投票，今日无人出局。")); begin_next_night(state)
        else:
            death = Death(target, "vote"); kill(state, death); events.append(GameEvent(f"投票结果：{target} 出局。")); after_deaths(state, [death], Phase.NIGHT_WOLF_DISCUSSION, events)
    elif state.phase is Phase.HUNTER_SHOT:
        shot = action_manager.first_action(actions, ActionName.SHOOT)
        if shot and shot.target: death = Death(shot.target, "hunter_shot"); kill(state, death); events.append(GameEvent(f"猎人带走了 {shot.target}。"))
        else: events.append(GameEvent("猎人未开枪。"))
        next_phase = state.continue_phase or Phase.NIGHT_WOLF_DISCUSSION; state.hunter_name = None; state.continue_phase = None; after_deaths(state, [], next_phase, events)
    check_winner(state, events)
    return state, tuple(events)


def finish_as_draw(state: WerewolfGameState) -> tuple[WerewolfGameState, tuple[GameEvent, ...]]:
    state.winner = Winner.DRAW; state.phase = Phase.REVIEW
    return state, (GameEvent("游戏因达到最大回合数而平局结束。"), *review_events(state))


def resolve_witch_and_night(state: WerewolfGameState, actions: dict[str, GameAction]) -> tuple[WerewolfGameState, list[GameEvent]]:
    witch = tuple(a for a in actions.values() if a.action in {ActionName.SAVE, ActionName.POISON})
    saved = any(a.action is ActionName.SAVE for a in witch); poison = next((a for a in witch if a.action is ActionName.POISON), None)
    if saved: state.witch_has_antidote = False
    deaths = [] if saved or state.wolf_target is None else [Death(state.wolf_target, "wolf_kill")]
    if poison and poison.target and poison.target not in {d.player for d in deaths}: state.witch_has_poison = False; deaths.append(Death(poison.target, "witch_poison"))
    state.wolf_target = None
    for death in deaths: kill(state, death)
    events = [GameEvent("天亮了，昨夜有人死亡。" if deaths else "天亮了，昨夜平安无事。")]
    after_deaths(state, deaths, Phase.DAY_DISCUSSION, events)
    return state, events


def after_deaths(state: WerewolfGameState, deaths: list[Death], next_phase: Phase, events: list[GameEvent]) -> None:
    hunter = next((d for d in deaths if state.role_of(d.player) is Role.HUNTER and d.cause != "witch_poison"), None)
    if hunter: state.hunter_name = hunter.player; state.continue_phase = next_phase; state.phase = Phase.HUNTER_SHOT; events.append(GameEvent("猎人请决定是否开枪。", hunter.player, True)); return
    state.phase = next_phase
    if next_phase is Phase.NIGHT_WOLF_DISCUSSION: begin_next_night(state)


def begin_next_night(state: WerewolfGameState) -> None:
    state.round_no += 1; state.phase = Phase.NIGHT_WOLF_DISCUSSION


def kill(state: WerewolfGameState, death: Death) -> None:
    if death.player in state.players: state.players[death.player].alive = False


def check_winner(state: WerewolfGameState, events: list[GameEvent]) -> None:
    if not state.alive_wolves(): state.winner = Winner.VILLAGERS
    elif len(state.alive_wolves()) >= len(state.alive_players()) - len(state.alive_wolves()): state.winner = Winner.WOLVES
    if state.winner:
        state.phase = Phase.REVIEW; label = "好人阵营" if state.winner is Winner.VILLAGERS else "狼人阵营"; events.append(GameEvent(f"游戏结束：{label}获胜。")); events.extend(review_events(state))


def review_events(state: WerewolfGameState) -> tuple[GameEvent, ...]:
    identities = "\n".join(f"- {n}：{p.role.value}" for n, p in state.players.items())
    return tuple(GameEvent(f"本局结算：{state.winner.value if state.winner else 'draw'}。\n\n全部玩家身份：\n{identities}\n\n请调用 save_experience 完成本局复盘，然后直接结束本回合。", n, True) for n in state.players)


__all__ = ["GameAction", "GameEvent", "WerewolfActionManager", "WerewolfEnvironment", "WerewolfSession", "WerewolfWorkflowConfig", "finish_as_draw", "open_or_restore_session", "resolve_phase"]
