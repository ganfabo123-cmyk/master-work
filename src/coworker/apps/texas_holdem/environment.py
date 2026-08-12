"""Deterministic four-player Texas Hold'em Environment."""

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
from ...infra.room import AgentProfile, RoomMessage
from ...infra.runtimes import RoomRuntime, SessionRuntime, SynchronousAppRuntime
from ...infra.session import AppSession, SessionManager
from .action import ACTION_NAMES, ENGINE_NAME
from .agent import PokerAgent
from .observation import PokerObservation, build_state_message
from .rules import evaluate_seven, settle_pots
from .state import BIG_BLIND, PLAYERS, PokerPhase, TexasHoldemState


@dataclass(frozen=True, slots=True)
class PokerActionPayload:
    amount: int | None = None


class PokerActionValue(ActionEnvelope[PokerActionPayload]):
    @property
    def amount(self) -> int | None:
        return self.payload.amount


class PokerActionManager(ActionManager):
    def resolve_action(self, response: Any) -> PokerActionValue | None:
        if not isinstance(response, tuple) or len(response) != 3:
            return None
        actor, message, observation = response
        if not isinstance(actor, str) or not isinstance(message, Message) or not isinstance(observation, PokerObservation):
            return None
        call = next((item for item in message.tool_calls if item.name in ACTION_NAMES), None)
        if call is None:
            return None
        try:
            arguments = json.loads(call.arguments) if isinstance(call.arguments, str) else dict(call.arguments)
            amount = int(arguments["amount"]) if call.name == "raise_bet" else None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return PokerActionValue(f"{actor}:{call.id}", actor, call.name, PokerActionPayload(amount), call, observation)

    def validate_action(self, action: Any, state: State) -> tuple[bool, str]:
        if not isinstance(action, PokerActionValue) or not isinstance(state, TexasHoldemState):
            return False, "提交参数无法解析，或当前 State 类型不正确。"
        if action.action_id in state.consumed_action_ids or action.actor != state.current_actor:
            return False, f"Action 已消费，或当前应由 {state.current_actor or '无人'} 行动。"
        if action.actor in state.folded or action.actor in state.all_in or state.stacks[action.actor] <= 0:
            return False, "已弃牌、已全押或没有剩余筹码的玩家不能行动。"
        to_call = max(0, state.current_bet - state.street_bets[action.actor])
        if action.name == "fold":
            return True, ""
        if action.name == "check":
            return (True, "") if to_call == 0 else (False, f"当前需跟注 {to_call}，不能 check。")
        if action.name == "call":
            return (True, "") if to_call > 0 else (False, "当前无需跟注，应选择 check 或其他合法动作。")
        if action.name == "all_in":
            return (True, "") if state.stacks[action.actor] > 0 else (False, "没有剩余筹码，不能 all_in。")
        if action.name != "raise_bet" or action.amount is None or action.actor in state.raise_locked:
            return False, "raise_bet 缺少 amount，动作类型错误，或当前禁止再次加注。"
        maximum = state.street_bets[action.actor] + state.stacks[action.actor]
        minimum = state.current_bet + state.minimum_raise
        if action.amount > maximum:
            return False, f"raise_bet 金额超过最大可下注额 {maximum}。"
        if action.amount < minimum:
            return False, f"raise_bet 金额不得低于最小加注总额 {minimum}。"
        return True, ""

    def available_actions(self, state: State, agent: Agent) -> tuple[str, ...]:
        if not isinstance(state, TexasHoldemState) or agent.name != state.current_actor:
            return ()
        to_call = max(0, state.current_bet - state.street_bets[agent.name])
        names = ["fold", "check" if to_call == 0 else "call", "all_in"]
        if agent.name not in state.raise_locked and state.street_bets[agent.name] + state.stacks[agent.name] >= state.current_bet + state.minimum_raise:
            names.append("raise_bet")
        return tuple(names)

    def resolve_actions(self, state: State, actions: object) -> PokerActionValue:
        if not isinstance(actions, PokerActionValue):
            raise TypeError("poker step requires exactly one Action")
        return actions


@dataclass(slots=True)
class TexasHoldemWorkflowConfig:
    seed: int = 20260811


class TexasHoldemEnvironment(Environment):
    """Play one deterministic four-player no-limit Texas Hold'em hand."""

    session_mode = "texas-holdem"
    entry_agent = "player-1"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 5) -> None:
        self.session = session
        self.llm = llm
        self.model = model
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.sync_runtime = SynchronousAppRuntime()
        self.event_dispatcher = RoomEventDispatcher()
        self.action_manager = PokerActionManager()
        self._active: AppSession[TexasHoldemState] | None = None
        self._task: Task | None = None
        placeholder = TexasHoldemState.initial("", "")
        super().__init__((), placeholder, Observation("poker-placeholder", "", ""), trace=session.trace)

    @classmethod
    def from_environment(cls, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data"), max_turns: int = 5) -> "TexasHoldemEnvironment":
        return cls(SessionManager(traces_root=traces_root, room_data_root=room_data_root), llm=OpenAICompatibleClient.from_environment(), model=os.getenv("COWORKER_MODEL", "deepseek-v4-flash"), max_turns=max_turns)

    def run(self, *, task: Task, session_id: str | None = None, on_session_opened: Callable[[str], None] | None = None, config: TexasHoldemWorkflowConfig | None = None) -> AgentResult:
        return SessionRuntime(trace=self.session.trace).run(self, task=task, session_id=session_id, on_session_opened=on_session_opened, config=config)

    def run_session(self, *, task: Task, context: SessionContext, config: TexasHoldemWorkflowConfig | None = None, **_: Any) -> AgentResult:
        active = self._open(task, context, config or TexasHoldemWorkflowConfig())
        self._active, self._task = active, task
        self.agents, self.state = tuple(active.agents.values()), active.state
        try:
            state = self.sync_runtime.run(self, active)
            return AgentResult("completed", Message("assistant", state.ending_report), None, active.session_id)
        except Exception:
            active.persist()
            raise

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        current, active = self._state(state), self._require_active()
        return () if current.current_actor is None else (active.agents[current.current_actor],)

    def observe(self, state: State, agent: Agent) -> Observation:
        current, active = self._state(state), self._require_active()
        available = self.action_manager.available_actions(current, agent)
        return PokerObservation(
            state_message=build_state_message(current, agent.name, available), available_tool_names=("think", *available),
            room=active.room("public"), task_id=current.task_id, session_id=current.session_id,
        )

    def act(self, agent: Agent, observation: Observation) -> PokerActionValue | None:
        if not isinstance(observation, PokerObservation):
            raise TypeError("observation must be PokerObservation")
        active = self._require_active()
        turn = self.room_runtime.run_turn(
            room=active.room("public"), additional_rooms=(active.room(f"private:{agent.name}"),),
            agent_name=agent.name, task=self._require_task(), session_id=active.session_id,
            incremental_context=active.contexts[agent.name], events=(observation.state_message,),
            available_tool_names=observation.available_tool_names,
        )
        if turn.status == "failed":
            raise RuntimeError(f"Poker turn failed for {agent.name}: {turn.error}")
        return self.action_manager.resolve_action((agent.name, turn.content, observation))

    def ready_to_step(self, state: State, actions: object) -> bool:
        current = self._state(state)
        return isinstance(actions, dict) and len(actions) == 1 and current.current_actor in actions and self.action_manager.validate_action(actions[current.current_actor], current)[0]

    def resolve_collected_actions(self, state: State, actions: dict[str, ActionEnvelope[Any]]) -> PokerActionValue:
        if len(actions) != 1:
            raise RuntimeError("Poker requires exactly one current actor")
        return self.action_manager.resolve_actions(state, next(iter(actions.values())))

    def step(self, state: State, action: Any) -> State:
        current, active = self._state(state), self._require_active()
        resolved = self.action_manager.resolve_actions(current, action)
        valid, reason = self.action_manager.validate_action(resolved, current)
        if not valid:
            self.reject_tool_action(agent=active.agents[resolved.actor], observation=resolved.observation, tool_call=resolved.tool_call, reason=reason, message_sink=active.contexts[resolved.actor].append_turn_messages)
            raise ValueError(f"Illegal poker action {resolved.name!r} from {resolved.actor!r}")
        self.execute_tool_action(agent=active.agents[resolved.actor], observation=resolved.observation, tool_call=resolved.tool_call, message_sink=active.contexts[resolved.actor].append_turn_messages)
        next_state = TexasHoldemState.from_dict(current.to_dict())
        self._apply_action(next_state, resolved)
        next_state.consumed_action_ids.add(resolved.action_id)
        active.state, self.state = next_state, next_state
        return next_state

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[AppEvent, ...]:
        before, after = self._state(old_state), self._state(new_state)
        action = self.action_manager.resolve_actions(before, actions)
        content = f"{action.actor} 执行 {action.name}"
        if action.amount is not None:
            content += f" 到 {action.amount}"
        content += (
            f"。本街投入：{after.street_bets[action.actor]}；累计投入：{after.committed[action.actor]}；"
            f"剩余筹码：{after.stacks[action.actor]}；当前底池：{after.pot}。"
        )
        events = [AppEvent(f"{action.action_id}:settled", "betting_action", action.actor, content)]
        if before.phase is not after.phase:
            reveal = " ".join(after.community_cards)
            active = "、".join(after.active_players())
            events.append(AppEvent(f"{after.session_id}:poker:{after.phase.value}", "phase_changed", ENGINE_NAME, f"进入 {after.phase.value}，公共牌：{reveal or '无'}；当前底池：{after.pot}；仍在局：{active}。"))
        if after.is_terminal:
            showdown = "\n".join(
                f"- {player}：{' '.join(after.hole_cards[player])}"
                for player in after.active_players()
            ) if len(after.active_players()) > 1 else ""
            payouts = "、".join(f"{player}={amount}" for player, amount in after.payouts.items())
            events.append(AppEvent(
                f"{after.session_id}:poker:settlement", "hand_settled", ENGINE_NAME,
                f"# 完整结算\n\n{after.ending_report}\n\n摊牌手牌：\n{showdown or '无摊牌'}\n\n派奖：{payouts}",
            ))
        return tuple(events)

    def dispatch_events(self, events: tuple[AppEvent, ...]) -> None:
        deliveries = tuple(EventDelivery(event.event_id, "public") for event in events)
        self.event_dispatcher.dispatch(events, deliveries, rooms=self._require_active().rooms)

    def orchestrate_agents(self) -> Any:
        return self.run

    def _apply_action(self, state: TexasHoldemState, action: PokerActionValue) -> None:
        actor = action.actor
        old_bet = state.current_bet
        pending_before = set(state.pending_players)
        if action.name == "fold":
            state.folded.add(actor)
        else:
            target = state.street_bets[actor]
            if action.name == "call":
                target = min(state.current_bet, target + state.stacks[actor])
            elif action.name == "raise_bet":
                target = int(action.amount or 0)
            elif action.name == "all_in":
                target += state.stacks[actor]
            contribution = target - state.street_bets[actor]
            state.stacks[actor] -= contribution
            state.street_bets[actor] = target
            state.committed[actor] += contribution
            if state.stacks[actor] == 0:
                state.all_in.add(actor)
            if target > old_bet:
                raise_size = target - old_bet
                state.current_bet = target
                if raise_size >= state.minimum_raise:
                    state.minimum_raise = raise_size
                    state.raise_locked.clear()
                    state.pending_players = {player for player in state.actionable_players() if player != actor}
                else:
                    actionable = set(state.actionable_players()) - {actor}
                    state.pending_players |= {player for player in actionable if state.street_bets[player] < target}
                    state.raise_locked |= actionable - pending_before
        state.pending_players.discard(actor)
        if len(state.active_players()) == 1:
            self._finish_without_showdown(state)
            return
        state.pending_players &= set(state.actionable_players())
        while not state.pending_players and not state.is_terminal:
            self._advance_street(state)
        if not state.is_terminal:
            state.current_actor = self._next_pending(state, actor if state.phase is PokerPhase.PREFLOP else "player-1")

    def _advance_street(self, state: TexasHoldemState) -> None:
        if state.phase is PokerPhase.RIVER:
            self._finish_showdown(state)
            return
        reveal_count = 3 if state.phase is PokerPhase.PREFLOP else 1
        state.deck_index += 1  # burn card
        state.community_cards.extend(state.deck[state.deck_index:state.deck_index + reveal_count])
        state.deck_index += reveal_count
        state.phase = {PokerPhase.PREFLOP: PokerPhase.FLOP, PokerPhase.FLOP: PokerPhase.TURN, PokerPhase.TURN: PokerPhase.RIVER}[state.phase]
        state.street_bets = {player: 0 for player in PLAYERS}
        state.current_bet = 0
        state.minimum_raise = BIG_BLIND
        state.raise_locked.clear()
        actionable = state.actionable_players()
        state.pending_players = set(actionable) if len(actionable) > 1 else set()
        if state.pending_players:
            state.current_actor = self._next_pending(state, "player-1")

    def _finish_without_showdown(self, state: TexasHoldemState) -> None:
        winner = state.active_players()[0]
        state.payouts = {player: state.pot if player == winner else 0 for player in PLAYERS}
        self._finish(state, (winner,))

    def _finish_showdown(self, state: TexasHoldemState) -> None:
        state.payouts = settle_pots(state)
        scores = {
            player: evaluate_seven((*state.hole_cards[player], *state.community_cards))
            for player in state.active_players()
        }
        best = max(scores.values())
        self._finish(state, tuple(player for player in PLAYERS if scores.get(player) == best))

    @staticmethod
    def _finish(state: TexasHoldemState, winners: tuple[str, ...]) -> None:
        for player, amount in state.payouts.items():
            state.stacks[player] += amount
        state.winners = winners
        state.phase = PokerPhase.FINISHED
        state.current_actor = None
        state.pending_players.clear()
        state.ending_report = f"德州扑克单局结束。获胜者：{', '.join(winners)}；公共牌：{' '.join(state.community_cards)}；底池：{state.pot}。"

    @staticmethod
    def _next_pending(state: TexasHoldemState, after: str) -> str:
        start = PLAYERS.index(after)
        for offset in range(1, len(PLAYERS) + 1):
            player = PLAYERS[(start + offset) % len(PLAYERS)]
            if player in state.pending_players:
                return player
        raise RuntimeError("No pending poker player")

    def _open(self, task: Task, context: SessionContext, config: TexasHoldemWorkflowConfig) -> AppSession[TexasHoldemState]:
        session_id = context.session_id
        store = StateStore(self.session.trace.root.parent / "state" / "data")
        if context.resumed:
            metadata = self.session.trace.session_data(session_id)
            public_id, private_ids = metadata.get("poker_public_room_id"), metadata.get("poker_private_room_ids")
            if not isinstance(public_id, str) or not isinstance(private_ids, dict):
                raise ValueError(f"Session has no poker ROOM metadata: {session_id}")
            public = self.session.resume_room(public_id, session_id=session_id)
            private_rooms = {player: self.session.resume_room(str(private_ids[player]), session_id=session_id) for player in PLAYERS}
            state = store.restore(session_id, "texas_holdem", TexasHoldemState)
        else:
            state = TexasHoldemState.create_hand(task.description, session_id, seed=config.seed)
            public = self.session.create_room(f"poker-public-{session_id}", session_id=session_id)
            private_rooms = {player: self.session.create_room(f"poker-{player}-{session_id}", session_id=session_id) for player in PLAYERS}
            self.session.trace.update_session_metadata(session_id, public_room_id=public.room_id, poker_public_room_id=public.room_id, poker_private_room_ids={player: room.room_id for player, room in private_rooms.items()}, poker_seed=config.seed)
        engine = AgentProfile(name=ENGINE_NAME, introduction="Deterministic Texas Hold'em dealer and rules engine.", role="poker-engine")
        for room in (public, *private_rooms.values()):
            if ENGINE_NAME not in room.participants():
                room.register(engine)
                room.invite(ENGINE_NAME)
        agents = {player: PokerAgent(self.llm, self.model, name=player) for player in PLAYERS}
        for player, agent in agents.items():
            self.room_runtime.register_agent(agent, AgentProfile(name=player, introduction="Texas Hold'em player.", role="poker-player"))
        missing = tuple(player for player in PLAYERS if player not in public.participants())
        if missing:
            self.room_runtime.invite_agents(public, missing, session_id=session_id)
        for player, room in private_rooms.items():
            if player not in room.participants():
                self.room_runtime.invite_agents(room, (player,), session_id=session_id)
        active = AppSession(
            session_id, state, agents,
            {player: self.room_runtime.open_incremental_context(agent_name=player, task=task, session_id=session_id) for player in PLAYERS},
            {"public": public, **{f"private:{player}": room for player, room in private_rooms.items()}},
            store, "texas_holdem",
        )
        self._active = active
        if not context.resumed:
            public.send(RoomMessage(name=ENGINE_NAME, at="all", txt="四人德州扑克单局开始：player-2 小盲 5，player-3 大盲 10。"))
            for player in PLAYERS:
                active.room(f"private:{player}").send(RoomMessage(name=ENGINE_NAME, at=player, txt=f"你的手牌：{' '.join(state.hole_cards[player])}"))
        active.persist()
        return active

    def _require_active(self) -> AppSession[TexasHoldemState]:
        if self._active is None:
            raise RuntimeError("Poker session has not started")
        return self._active

    def _require_task(self) -> Task:
        if self._task is None:
            raise RuntimeError("Poker session has no Task")
        return self._task

    @staticmethod
    def _state(state: State) -> TexasHoldemState:
        if not isinstance(state, TexasHoldemState):
            raise TypeError("state must be TexasHoldemState")
        return state


__all__ = ["PokerActionManager", "PokerActionPayload", "PokerActionValue", "TexasHoldemEnvironment", "TexasHoldemWorkflowConfig"]
