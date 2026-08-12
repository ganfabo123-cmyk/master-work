"""Synchronous eight-participant werewolf instruction discussion."""

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
from .action import ENGINE_NAME, WerewolfInstructionAction
from .agent import WerewolfInstructionAgent
from .observation import WerewolfInstructionObservation, build_state_message
from .state import InstructionPhase, PARTICIPANTS, WerewolfInstructionState


@dataclass(frozen=True, slots=True)
class InstructionActionPayload:
    content: str


class InstructionActionValue(ActionEnvelope[InstructionActionPayload]):
    @property
    def content(self) -> str:
        return self.payload.content


class WerewolfInstructionActionManager(ActionManager):
    def resolve_action(self, response: Any) -> InstructionActionValue | None:
        if not isinstance(response, tuple) or len(response) != 4:
            return None
        actor, message, observation, state = response
        if not isinstance(actor, str) or not isinstance(message, Message) or not isinstance(observation, WerewolfInstructionObservation) or not isinstance(state, WerewolfInstructionState):
            return None
        try:
            allowed = {"speak"} if actor not in state.spoken else {"submit_my_instruction"} if actor not in state.instructions else set()
            call = next(item for item in message.tool_calls if item.name in allowed)
            payload = json.loads(call.arguments) if isinstance(call.arguments, str) else dict(call.arguments)
        except (StopIteration, TypeError, ValueError, json.JSONDecodeError):
            return None
        key = "content" if call.name == "speak" else "instruction"
        return InstructionActionValue(f"{actor}:{call.id}", actor, call.name, InstructionActionPayload(str(payload.get(key, "")).strip()), call, observation)

    def validate_action(self, action: Any, state: State) -> tuple[bool, str]:
        if not isinstance(action, InstructionActionValue) or not isinstance(state, WerewolfInstructionState):
            return False, "提交参数无法解析，或当前 State 类型不正确。"
        if action.actor not in PARTICIPANTS or action.message_id in state.consumed_action_ids:
            return False, "提交者不是参与者，或该 Action 已消费。"
        if not action.content:
            return False, "提交内容不能为空。"
        if action.name == "speak":
            return (False, "该参与者已经完成公开发言。") if action.actor in state.spoken else (True, "")
        if action.name == "submit_my_instruction":
            if action.actor not in state.spoken:
                return False, "必须先完成公开发言，再提交教程正文。"
            return (False, "该参与者已经提交教程正文。") if action.actor in state.instructions else (True, "")
        return False, "当前只接受 speak 或 submit_my_instruction。"

    def available_actions(self, state: State, agent: Agent) -> tuple[str, ...]:
        if isinstance(state, WerewolfInstructionState) and agent.name not in state.spoken:
            return ("speak",)
        if isinstance(state, WerewolfInstructionState) and agent.name not in state.instructions:
            return ("submit_my_instruction",)
        return ()

    def resolve_actions(self, state: State, actions: object) -> dict[str, InstructionActionValue]:
        if not isinstance(actions, dict) or not all(isinstance(name, str) and isinstance(action, InstructionActionValue) for name, action in actions.items()):
            raise TypeError("actions must be dict[str, InstructionActionValue]")
        return actions


@dataclass(slots=True)
class WerewolfInstructionWorkflowConfig:
    max_discussion_rounds: int = 8


class WerewolfInstructionEnvironment(Environment):
    session_mode = "werewolf-instruction"
    entry_agent = "player-1"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 6) -> None:
        self.session = session
        self.llm = llm
        self.model = model
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.sync_runtime = SynchronousAppRuntime()
        self.event_dispatcher = RoomEventDispatcher()
        self.action_manager = WerewolfInstructionActionManager()
        self._active: AppSession[WerewolfInstructionState] | None = None
        self._task: Task | None = None
        self._max_discussion_rounds = WerewolfInstructionWorkflowConfig().max_discussion_rounds
        placeholder = WerewolfInstructionState.initial("", "")
        super().__init__((), placeholder, Observation("werewolf-instruction-placeholder", "", ""), trace=session.trace)

    @classmethod
    def from_environment(cls, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data"), max_turns: int = 6) -> "WerewolfInstructionEnvironment":
        return cls(SessionManager(traces_root=traces_root, room_data_root=room_data_root), llm=OpenAICompatibleClient.from_environment(), model=os.getenv("COWORKER_MODEL", "deepseek-v4-flash"), max_turns=max_turns)

    def run(self, *, task: Task, session_id: str | None = None, on_session_opened: Callable[[str], None] | None = None, config: WerewolfInstructionWorkflowConfig | None = None) -> AgentResult:
        return SessionRuntime(trace=self.session.trace).run(self, task=task, session_id=session_id, on_session_opened=on_session_opened, config=config)

    def run_session(self, *, task: Task, context: SessionContext, config: WerewolfInstructionWorkflowConfig | None = None, **_: Any) -> AgentResult:
        self._active = self._open(task, context)
        self._task = task
        self.agents = tuple(self._active.agents.values())
        self.state = self._active.state
        active = self._active
        self._max_discussion_rounds = (config or WerewolfInstructionWorkflowConfig()).max_discussion_rounds
        state = self.sync_runtime.run(self, active)
        return AgentResult("completed", Message("assistant", state.tutorial), None, active.session_id)

    def before_cycle(self, state: State) -> tuple[AppEvent, ...]:
        current = self._state(state)
        if current.discussion_round > self._max_discussion_rounds:
            raise RuntimeError(f"Not all participants submitted instructions within {self._max_discussion_rounds} discussion rounds")
        return ()

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        current, active = self._state(state), self._require_active()
        return tuple(active.agents[name] for name in PARTICIPANTS if name not in current.instructions)

    def observe(self, state: State, agent: Agent) -> Observation:
        current, active = self._state(state), self._require_active()
        return WerewolfInstructionObservation(state_message=build_state_message(current, agent.name), available_tool_names=self.action_manager.available_actions(current, agent), room=active.room("public"), task_id=current.task_id, session_id=current.session_id)

    def act(self, agent: Agent, observation: Observation) -> InstructionActionValue | None:
        if not isinstance(observation, WerewolfInstructionObservation):
            raise TypeError("observation must be WerewolfInstructionObservation")
        active = self._require_active()
        turn = self.room_runtime.run_turn(room=active.room("public"), agent_name=agent.name, task=self._require_task(), session_id=active.session_id, incremental_context=active.contexts[agent.name], events=(observation.state_message,), available_tool_names=observation.available_tool_names)
        if turn.status == "failed":
            raise RuntimeError(f"Instruction discussion turn failed for {agent.name}: {turn.error}")
        return self.action_manager.resolve_action((agent.name, turn.content, observation, active.state))

    def ready_to_step(self, state: State, actions: object) -> bool:
        self._state(state)
        return isinstance(actions, dict)

    def step(self, state: State, action: Any) -> State:
        current, active = self._state(state), self._require_active()
        next_state = WerewolfInstructionState.from_dict(current.to_dict())
        actions = self.action_manager.resolve_actions(next_state, action)
        for item in actions.values():
            valid, reason = self.action_manager.validate_action(item, next_state)
            if valid:
                self.execute_tool_action(
                    agent=active.agents[item.actor],
                    observation=item.observation,
                    tool_call=item.tool_call,
                    message_sink=active.contexts[item.actor].append_turn_messages,
                )
                if item.name == "speak":
                    active.room("public").send(RoomMessage(name=item.actor, at="all", txt=item.content))
                    next_state.spoken.add(item.actor)
                else:
                    next_state.instructions[item.actor] = item.content
                    active.room("public").send(RoomMessage(name=item.actor, at="all", txt=f"# 教程提交\n\n{item.content}"))
                next_state.consumed_action_ids.add(item.message_id)
            else:
                self.reject_tool_action(
                    agent=active.agents[item.actor], observation=item.observation, tool_call=item.tool_call,
                    reason=reason,
                    message_sink=active.contexts[item.actor].append_turn_messages,
                )
        if all(name in next_state.instructions for name in PARTICIPANTS):
            next_state.tutorial = "\n\n".join(next_state.instructions[name].strip() for name in PARTICIPANTS)
            next_state.phase = InstructionPhase.FINISHED
        else:
            next_state.discussion_round += 1
        active.state = next_state
        self.state = next_state
        return next_state

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[AppEvent, ...]:
        before, after = self._state(old_state), self._state(new_state)
        if not before.is_terminal and after.is_terminal:
            return (
                AppEvent(f"{after.session_id}:instruction:tutorial", "tutorial_completed", ENGINE_NAME, f"# 完整狼人杀教程\n\n{after.tutorial}"),
                AppEvent(f"{after.session_id}:instruction:finished", "workflow_finished", ENGINE_NAME, "八名参与者均已提交教程内容，讨论结束。"),
            )
        return ()

    def dispatch_events(self, events: tuple[AppEvent, ...]) -> None:
        deliveries = tuple(EventDelivery(event.event_id, "public") for event in events)
        self.event_dispatcher.dispatch(events, deliveries, rooms=self._require_active().rooms)

    def orchestrate_agents(self) -> Any:
        return self.run

    def _open(self, task: Task, context: SessionContext) -> AppSession[WerewolfInstructionState]:
        session_id = context.session_id
        store = StateStore(self.session.trace.root.parent / "state" / "data")
        if context.resumed:
            metadata = self.session.trace.session_data(session_id)
            room_id = metadata.get("werewolf_instruction_room_id")
            if not isinstance(room_id, str):
                raise ValueError(f"Session has no instruction discussion ROOM: {session_id}")
            room = self.session.resume_room(room_id, session_id=session_id)
            state = store.restore(session_id, "werewolf_instruction", WerewolfInstructionState)
        else:
            state = WerewolfInstructionState.initial(task.description, session_id)
            room = self.session.create_room(f"werewolf-instruction-{session_id}", session_id=session_id)
            self.session.trace.update_session_metadata(session_id, public_room_id=room.room_id, werewolf_instruction_room_id=room.room_id)
            room.register(AgentProfile(name=ENGINE_NAME, introduction="Deterministic instruction collection engine.", role="instruction-engine"))
            room.invite(ENGINE_NAME)
        agents = {name: WerewolfInstructionAgent(self.llm, self.model, name=name, room=room) for name in PARTICIPANTS}
        for name, agent in agents.items():
            self.room_runtime.register_agent(agent, AgentProfile(name=name, introduction="Werewolf strategy discussion participant.", role="werewolf-instruction-author"))
        missing = tuple(name for name in PARTICIPANTS if name not in room.participants())
        if missing:
            self.room_runtime.invite_agents(room, missing, session_id=session_id)
        contexts = {name: self.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
        active = AppSession(session_id, state, agents, contexts, {"public": room}, store, "werewolf_instruction")
        active.persist()
        return active

    def _require_active(self) -> AppSession[WerewolfInstructionState]:
        if self._active is None:
            raise RuntimeError("Werewolf instruction discussion has not started")
        return self._active

    def _require_task(self) -> Task:
        if self._task is None:
            raise RuntimeError("Werewolf instruction discussion has no Task")
        return self._task

    @staticmethod
    def _state(state: State) -> WerewolfInstructionState:
        if not isinstance(state, WerewolfInstructionState):
            raise TypeError("state must be WerewolfInstructionState")
        return state
