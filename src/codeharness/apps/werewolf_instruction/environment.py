"""Synchronous eight-participant werewolf instruction discussion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from ...core.base_agent import Agent
from ...core.base_environment import ActionManager, Environment
from ...core.base_observation import Observation
from ...core.base_state import State
from ...core.models import AgentResult, Message, Task, ToolCall
from ...core.session import SessionContext
from ...infra import StateStore
from ...infra.client import LLMClient, OpenAICompatibleClient
from ...infra.room import AgentProfile, Room, RoomMessage
from ...infra.runtimes import IncrementalContext, RoomRuntime, SessionRuntime
from ...infra.session import SessionManager
from .action import ENGINE_NAME, WerewolfInstructionAction
from .agent import WerewolfInstructionAgent
from .observation import WerewolfInstructionObservation, build_state_message
from .state import InstructionPhase, PARTICIPANTS, WerewolfInstructionState


@dataclass(frozen=True, slots=True)
class InstructionActionValue:
    message_id: str
    actor: str
    name: str
    content: str
    tool_call: ToolCall
    observation: WerewolfInstructionObservation


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
        return InstructionActionValue(f"{actor}:{call.id}", actor, call.name, str(payload.get(key, "")).strip(), call, observation)

    def validate_action(self, action: Any, state: State) -> bool:
        return (
            isinstance(action, InstructionActionValue)
            and isinstance(state, WerewolfInstructionState)
            and action.actor in PARTICIPANTS
            and action.message_id not in state.consumed_action_ids
            and bool(action.content)
            and (
                (action.name == "speak" and action.actor not in state.spoken)
                or (action.name == "submit_my_instruction" and action.actor in state.spoken and action.actor not in state.instructions)
            )
        )

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


@dataclass(slots=True)
class WerewolfInstructionSession:
    session_id: str
    room: Room
    agents: dict[str, WerewolfInstructionAgent]
    contexts: dict[str, IncrementalContext]
    state: WerewolfInstructionState
    state_store: StateStore


class WerewolfInstructionEnvironment(Environment):
    session_mode = "werewolf-instruction"
    entry_agent = "player-1"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 6) -> None:
        self.session = session
        self.llm = llm
        self.model = model
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.action_manager = WerewolfInstructionActionManager()
        self._active: WerewolfInstructionSession | None = None
        self._task: Task | None = None
        placeholder = WerewolfInstructionState.initial("", "")
        super().__init__((), placeholder, Observation("werewolf-instruction-placeholder", "", ""), trace=session.trace)

    @classmethod
    def from_environment(cls, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data"), max_turns: int = 6) -> "WerewolfInstructionEnvironment":
        return cls(SessionManager(traces_root=traces_root, room_data_root=room_data_root), llm=OpenAICompatibleClient.from_environment(), model=os.getenv("CODEHARNESS_MODEL", "deepseek-v4-flash"), max_turns=max_turns)

    def run(self, *, task: Task, session_id: str | None = None, on_session_opened: Callable[[str], None] | None = None, config: WerewolfInstructionWorkflowConfig | None = None) -> AgentResult:
        return SessionRuntime(trace=self.session.trace).run(self, task=task, session_id=session_id, on_session_opened=on_session_opened, config=config)

    def run_session(self, *, task: Task, context: SessionContext, config: WerewolfInstructionWorkflowConfig | None = None, **_: Any) -> AgentResult:
        self._active = self._open(task, context)
        self._task = task
        self.agents = tuple(self._active.agents.values())
        self.state = self._active.state
        active = self._active
        limit = (config or WerewolfInstructionWorkflowConfig()).max_discussion_rounds
        while not active.state.is_terminal:
            if active.state.discussion_round > limit:
                raise RuntimeError(f"Not all participants submitted instructions within {limit} discussion rounds")
            actions: dict[str, InstructionActionValue] = {}
            for agent in self.select_agents(active.state):
                action = self.act(agent, self.observe(active.state, agent))
                if action is not None:
                    actions[action.actor] = action
            old_state = WerewolfInstructionState.from_dict(active.state.to_dict())
            active.state = self.step(active.state, self.action_manager.resolve_actions(active.state, actions))
            for event in self.build_events(old_state, actions, active.state):
                active.room.send(RoomMessage(name=ENGINE_NAME, at="all", txt=event.content))
        return AgentResult("completed", Message("assistant", active.state.tutorial), None, active.session_id)

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        current, active = self._state(state), self._require_active()
        return tuple(active.agents[name] for name in PARTICIPANTS if name not in current.instructions)

    def observe(self, state: State, agent: Agent) -> Observation:
        current, active = self._state(state), self._require_active()
        return WerewolfInstructionObservation(state_message=build_state_message(current, agent.name), available_tool_names=self.action_manager.available_actions(current, agent), room=active.room, task_id=current.task_id, session_id=current.session_id)

    def act(self, agent: Agent, observation: Observation) -> InstructionActionValue | None:
        if not isinstance(observation, WerewolfInstructionObservation):
            raise TypeError("observation must be WerewolfInstructionObservation")
        active = self._require_active()
        turn = self.room_runtime.run_turn(room=active.room, agent_name=agent.name, task=self._require_task(), session_id=active.session_id, incremental_context=active.contexts[agent.name], events=(observation.state_message,), available_tool_names=observation.available_tool_names)
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
            if self.action_manager.validate_action(item, next_state):
                self.execute_tool_action(
                    agent=active.agents[item.actor],
                    observation=item.observation,
                    tool_call=item.tool_call,
                    message_sink=active.contexts[item.actor].append_turn_messages,
                )
                if item.name == "speak":
                    active.room.send(RoomMessage(name=item.actor, at="all", txt=item.content))
                    next_state.spoken.add(item.actor)
                else:
                    next_state.instructions[item.actor] = item.content
                next_state.consumed_action_ids.add(item.message_id)
            else:
                self.reject_tool_action(
                    agent=active.agents[item.actor], observation=item.observation, tool_call=item.tool_call,
                    reason="Action 未通过当前教程讨论状态验证。",
                    message_sink=active.contexts[item.actor].append_turn_messages,
                )
        if all(name in next_state.instructions for name in PARTICIPANTS):
            next_state.tutorial = "\n\n".join(next_state.instructions[name].strip() for name in PARTICIPANTS)
            next_state.phase = InstructionPhase.FINISHED
        else:
            next_state.discussion_round += 1
        active.state = next_state
        self.state = next_state
        active.state_store.update(active.session_id, "werewolf_instruction", next_state)
        return next_state

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[Message, ...]:
        before, after = self._state(old_state), self._state(new_state)
        if not before.is_terminal and after.is_terminal:
            return (Message("user", "八名参与者均已提交教程内容，讨论结束。"),)
        return ()

    def orchestrate_agents(self) -> Any:
        return self.run

    def _open(self, task: Task, context: SessionContext) -> WerewolfInstructionSession:
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
        store.update(session_id, "werewolf_instruction", state)
        contexts = {name: self.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
        return WerewolfInstructionSession(session_id, room, agents, contexts, state, store)

    def _require_active(self) -> WerewolfInstructionSession:
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
