"""狼人杀环境：会话编排、动作结算和状态推进。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from .agent import WerewolfPlayerAgent
from .action import ActionName, WerewolfAction
from ...infra.runtimes import IncrementalContext
from ...infra.runtimes.room_runtime import RoomRuntime
from ...infra.runtimes.session_runtime import SessionRuntime
from ...core.base_agent import Agent
from ...core.base_environment import ActionManager, Environment
from ...core.base_observation import Observation
from ...core.base_state import State
from ...infra import StateStore
from ...core.models import AgentResult, Message, Task, ToolCall
from ...core.session import SessionContext
from ...infra.client import LLMClient, OpenAICompatibleClient
from .observation import WerewolfObservation, WerewolfTurnObservation
from ...infra.room import AgentProfile, Room, RoomMessage
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
    tool_call: ToolCall
    observation: WerewolfTurnObservation
    content: str = ""


class WerewolfActionManager(ActionManager):
    def __init__(self, action: WerewolfAction) -> None:
        self.action = action

    def resolve_action(self, response: Any) -> GameAction | None:
        if not isinstance(response, tuple) or len(response) != 4:
            return None
        actor, message, observation, state = response
        if not isinstance(actor, str) or not isinstance(message, Message) or not isinstance(observation, WerewolfTurnObservation) or not isinstance(state, WerewolfGameState):
            return None
        try:
            call = next(item for item in message.tool_calls if item.name in {action.value for action in ActionName})
            payload = json.loads(call.arguments) if isinstance(call.arguments, str) else dict(call.arguments)
            if not isinstance(payload, dict):
                return None
            mapped_action = self.action.get_action(call.name)
            target = payload.get("target")
            return GameAction(
                message_id=f"{actor}:{call.id}",
                actor=actor,
                action=ActionName(mapped_action.name),
                target=target if isinstance(target, str) else None,
                round_no=state.round_no,
                phase=state.phase,
                tool_call=call,
                observation=observation,
                content=str(payload.get("content", "")).strip(),
            )
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
            return None

    def validate_action(self, action: GameAction, state: WerewolfGameState) -> bool:
        return self._validation_error(action, state) is None

    def available_actions(self, state: WerewolfGameState, agent: Agent) -> tuple[ActionName, ...]:
        agent_name = agent.name
        role = state.role_of(agent_name)
        if state.phase is Phase.NIGHT_WOLF_DISCUSSION and role is Role.WOLF:
            return (ActionName.WOLF_MESSAGE,)
        if state.phase is Phase.DAY_DISCUSSION and state.is_alive(agent_name):
            return (ActionName.SPEAK,)
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

    def resolve_actions(self, state: State, actions: object) -> dict[str, GameAction]:
        if not isinstance(state, WerewolfGameState):
            raise TypeError("state must be WerewolfGameState")
        if not isinstance(actions, dict) or not all(
            isinstance(name, str) and isinstance(action, GameAction)
            for name, action in actions.items()
        ):
            raise TypeError("actions must be dict[str, GameAction]")
        return actions

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
        if action.action in {ActionName.WOLF_MESSAGE, ActionName.SPEAK} and not action.content:
            return "发言内容不能为空。"
        target_actions = {ActionName.WOLF_KILL, ActionName.INSPECT, ActionName.POISON, ActionName.VOTE, ActionName.SHOOT}
        if action.action in target_actions and (action.target is None or not state.is_alive(action.target)):
            return "目标必须是存活玩家。"
        if action.action is ActionName.WOLF_MESSAGE:
            if state.phase is not Phase.NIGHT_WOLF_DISCUSSION or role is not Role.WOLF:
                return "当前无权进行狼队协商。"
        elif action.action is ActionName.SPEAK:
            if state.phase is not Phase.DAY_DISCUSSION:
                return "当前不是公开讨论阶段。"
        elif action.action is ActionName.WOLF_KILL:
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

    session_mode = "werewolf"
    entry_agent = "player-1"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 8) -> None:
        self.session = session
        self.trace = session.trace
        self.llm = llm
        self.model = model
        self.max_turns = max_turns
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.action_manager: WerewolfActionManager | None = None
        self._step_events: tuple[GameEvent, ...] = ()
        self._rl_game: WerewolfSession | None = None
        self._rl_task: Task | None = None
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
            model=os.getenv("COWORKER_MODEL", "deepseek-v4-flash"),
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
        """Compatibility entrypoint delegating session lifecycle to SessionRuntime."""
        return SessionRuntime(trace=self.trace).run(
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
        config: WerewolfWorkflowConfig | None = None,
        **_: Any,
    ) -> AgentResult:
        """Run Werewolf domain logic inside a Runtime-managed session."""
        game = open_or_restore_session(self, task=task, context=context)
        self._rl_game = game
        self._rl_task = task
        self.agents = tuple(game.agents.values())
        self.state = game.state
        self.observation = WerewolfObservation()
        self.action_manager = WerewolfActionManager(next(iter(game.agents.values())).action)
        config = config or WerewolfWorkflowConfig()
        try:
            state = game.state
            while state.phase is not Phase.FINISHED:
                publish_events(game.public_room, (GameEvent(phase_announcement(state)),))

                actions: dict[str, GameAction] = {}
                for agent in self.select_agents(state):

                    # State → Observation
                    observation = self.observe(state, agent)

                    # Observation → Policy → Action
                    action = self.act(agent, observation)
                    if action is not None:
                        actions[action.actor] = action

                if self.ready_to_step(state, actions):
                    resolved_actions = self._require_action_manager().resolve_actions(state, actions)
                    old_state = state

                    # Action → Environment → New State
                    state = self.step(state, resolved_actions)
                    events = self.build_events(old_state, resolved_actions, state)
                    publish_events(game.public_room, tuple(events))

                if state.round_no > config.max_game_rounds and state.phase not in {Phase.REVIEW, Phase.FINISHED}:
                    state, events = finish_as_draw(state)
                    publish_events(game.public_room, events)
                    persist(game.state_store, game.session_id, state)
                    game.state = state
                    self.state = state
            winner = state.winner.value if state.winner else "unknown"
            return AgentResult("completed", Message("assistant", f"狼人杀游戏结束，结果：{winner}。"), None, game.session_id)
        except Exception:
            persist(game.state_store, game.session_id, game.state)
            raise

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

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        """Select all Agents scheduled to act for the current Werewolf phase."""
        game = self._require_rl_game()
        current = self._require_werewolf_state(state)
        return tuple(game.agents[name] for name in actors_for_phase(current))

    def act(self, agent: Agent, observation: Observation) -> GameAction | None:
        """Run the Agent Policy on an Observation and resolve its structured Action."""
        game = self._require_rl_game()
        task = self._require_rl_task()
        manager = self._require_action_manager()
        if not isinstance(observation, WerewolfTurnObservation):
            raise TypeError("observation must be WerewolfTurnObservation")

        turn = self.room_runtime.run_turn(
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

        action = manager.resolve_action((agent.name, turn.content, observation, game.state))
        if action is None:
            return None
        reason = manager._validation_error(action, game.state)
        if reason is not None:
            self.reject_tool_action(
                agent=agent, observation=observation, tool_call=action.tool_call, reason=reason,
                message_sink=game.contexts[agent.name].append_turn_messages,
            )
            game.public_room.send(RoomMessage(name=ENGINE_NAME, at=agent.name, txt=f"动作无效：{reason}"))
            return None
        return action

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

        for item in actions.values():
            reason = manager._validation_error(item, current)
            if reason is not None:
                self.reject_tool_action(
                    agent=game.agents[item.actor], observation=item.observation, tool_call=item.tool_call, reason=reason,
                    message_sink=game.contexts[item.actor].append_turn_messages,
                )
                raise ValueError(f"Illegal werewolf action {item.action.value!r} from {item.actor!r}: {reason}")
            self.execute_tool_action(
                agent=game.agents[item.actor],
                observation=item.observation,
                tool_call=item.tool_call,
                message_sink=game.contexts[item.actor].append_turn_messages,
            )
            if item.action is ActionName.WOLF_MESSAGE:
                game.wolf_room.send(RoomMessage(name=item.actor, at=current.alive_wolves(), txt=item.content))
            elif item.action is ActionName.SPEAK:
                game.public_room.send(RoomMessage(name=item.actor, at="all", txt=item.content))

        current.consumed_action_ids.update(item.message_id for item in actions.values())
        if current.phase is Phase.PREPARATION:
            current.phase = Phase.NIGHT_WOLF_DISCUSSION
            events: tuple[GameEvent, ...] = ()
        elif current.phase is Phase.REVIEW:
            current.phase = Phase.FINISHED
            events = ()
        else:
            current, events = resolve_phase(current, actions, manager)

        self._step_events = events
        persist(game.state_store, game.session_id, current)
        game.state = current
        self.state = current
        return current

    def ready_to_step(self, state: State, actions: object) -> bool:
        """The synchronous Werewolf loop advances after all selected Agents ran."""
        self._require_werewolf_state(state)
        return isinstance(actions, dict)

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[GameEvent, ...]:
        """Return the feedback events produced by the latest Werewolf transition."""
        self._require_werewolf_state(old_state)
        self._require_werewolf_state(new_state)
        return self._step_events

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


def open_or_restore_session(environment: WerewolfEnvironment, *, task: Task, context: SessionContext) -> WerewolfSession:
    store = StateStore(environment.trace.root.parent / "state" / "data")
    session_id = context.session_id
    if not context.resumed:
        state = WerewolfGameState.random_eight_players(task_id=task.description, session_id=session_id)
        public = environment.session.create_room(f"werewolf-public-{session_id}", session_id=session_id)
        wolves = environment.session.create_room(f"werewolf-wolves-{session_id}", session_id=session_id)
        environment.trace.update_session_metadata(session_id, public_room_id=public.room_id, werewolf_rooms={"public_room_id": public.room_id, "wolf_room_id": wolves.room_id})
        register_engine(public, wolves)
        agents: dict[str, WerewolfPlayerAgent] = {}
        for name, player in state.players.items():
            agent = WerewolfPlayerAgent(environment.llm, environment.model, name=name, role=player.role, public_room=public, state=state, wolf_room=wolves)
            environment.room_runtime.register_agent(agent, player_profile(name, player.role))
            agents[name] = agent
        environment.room_runtime.invite_agents(public, tuple(agents), session_id=session_id)
        environment.room_runtime.invite_agents(wolves, tuple(name for name, player in state.players.items() if player.role is Role.WOLF), session_id=session_id)
        persist(store, session_id, state)
        contexts = {name: environment.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
        return WerewolfSession(session_id, public, wolves, agents, contexts, state, store)
    data = environment.trace.session_data(session_id)
    rooms = data.get("werewolf_rooms")
    if data.get("mode") != "werewolf" or not isinstance(rooms, dict):
        raise ValueError(f"Session is not a resumable werewolf session: {session_id}")
    public_id, wolf_id = rooms.get("public_room_id"), rooms.get("wolf_room_id")
    if not isinstance(public_id, str) or not isinstance(wolf_id, str):
        raise ValueError(f"Session has invalid werewolf ROOM metadata: {session_id}")
    public, wolves = environment.session.resume_room(public_id, session_id=session_id), environment.session.resume_room(wolf_id, session_id=session_id)
    state = store.restore(session_id, "werewolf", WerewolfGameState)
    agents = {}
    for name in state.players:
        player = state.players[name]
        agent = WerewolfPlayerAgent(environment.llm, environment.model, name=name, role=player.role, public_room=public, state=state, wolf_room=wolves)
        environment.room_runtime.register_agent(agent, player_profile(name, player.role))
        agents[name] = agent
    contexts = {name: environment.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
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
