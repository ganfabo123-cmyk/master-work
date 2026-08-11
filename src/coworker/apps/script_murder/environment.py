"""爱丽舍宫阴影：五人同步、封闭动作空间的政治悬疑工作流。"""

from __future__ import annotations

from collections import Counter
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
from .action import ENGINE_NAME
from .agent import ScriptMurderAgent
from .case_loader import ScriptMurderCase, load_case
from .observation import ScriptMurderObservation, build_state_message
from .state import FinalSubmission, PLAYERS, ScriptMurderPhase, ScriptMurderState


DISCUSSION_PHASES = {ScriptMurderPhase.ROUND_1_DISCUSSION, ScriptMurderPhase.ROUND_2_DISCUSSION}


@dataclass(frozen=True, slots=True)
class ScriptMurderActionPayload:
    content: str = ""
    submission: FinalSubmission | None = None


class ScriptMurderActionValue(ActionEnvelope[ScriptMurderActionPayload]):
    @property
    def content(self) -> str:
        return self.payload.content

    @property
    def submission(self) -> FinalSubmission | None:
        return self.payload.submission


class ScriptMurderActionManager(ActionManager):
    def resolve_action(self, response: Any) -> ScriptMurderActionValue | None:
        if not isinstance(response, tuple) or len(response) != 3:
            return None
        actor, message, observation = response
        if not isinstance(actor, str) or not isinstance(message, Message) or not isinstance(observation, ScriptMurderObservation):
            return None
        call = next((item for item in message.tool_calls if item.name in {"speak", "pass_turn", "submit_resolution"}), None)
        if call is None:
            return None
        try:
            payload = json.loads(call.arguments) if isinstance(call.arguments, str) else dict(call.arguments)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        name = call.name
        if name == "speak":
            return ScriptMurderActionValue(f"{actor}:{call.id}", actor, name, ScriptMurderActionPayload(content=str(payload.get("message", "")).strip()), call, observation)
        if name == "pass_turn":
            return ScriptMurderActionValue(f"{actor}:{call.id}", actor, name, ScriptMurderActionPayload(), call, observation)
        if name != "submit_resolution":
            return None
        submission = FinalSubmission(
            declarations=tuple(str(item).strip() for item in payload.get("declarations", []) if str(item).strip()),
            decisive_action=str(payload.get("decisive_action", "")),
            target=None if payload.get("target") is None else str(payload["target"]),
            leader_vote=str(payload.get("leader_vote", "")),
        )
        return ScriptMurderActionValue(f"{actor}:{call.id}", actor, name, ScriptMurderActionPayload(submission=submission), call, observation)

    def validate_action(self, action: Any, state: State) -> bool:
        if not isinstance(action, ScriptMurderActionValue) or not isinstance(state, ScriptMurderState):
            return False
        if action.message_id in state.consumed_action_ids or action.actor not in state.character_assignments:
            return False
        expected = self.expected_player(state)
        if action.actor != expected:
            return False
        if state.phase in DISCUSSION_PHASES:
            return action.name in {"speak", "pass_turn"} and (action.name != "speak" or bool(action.content))
        if state.phase is not ScriptMurderPhase.FINAL_SUBMISSION or action.name != "submit_resolution" or action.submission is None:
            return False
        submission = action.submission
        character_ids = set(state.character_assignments.values())
        if submission.decisive_action not in {"murder", "guard", "investigate", "pass"}:
            return False
        if submission.decisive_action == "pass" and submission.target is not None:
            return False
        if submission.decisive_action != "pass" and submission.target not in character_ids:
            return False
        return submission.leader_vote in character_ids and action.actor not in state.final_submissions

    def available_actions(self, state: State, agent: Agent) -> tuple[str, ...]:
        if not isinstance(state, ScriptMurderState) or agent.name != self.expected_player(state):
            return ()
        if state.phase in DISCUSSION_PHASES:
            return ("think", "speak", "pass_turn")
        if state.phase is ScriptMurderPhase.FINAL_SUBMISSION:
            return ("think", "submit_resolution")
        return ()

    def resolve_actions(self, state: State, actions: object) -> ScriptMurderActionValue:
        if not isinstance(actions, ScriptMurderActionValue):
            raise TypeError("script murder step requires one action")
        return actions

    @staticmethod
    def expected_player(state: ScriptMurderState) -> str | None:
        if state.phase in DISCUSSION_PHASES:
            return PLAYERS[state.speaker_index] if state.speaker_index < len(PLAYERS) else None
        if state.phase is ScriptMurderPhase.FINAL_SUBMISSION:
            return next((name for name in PLAYERS if name not in state.final_submissions), None)
        return None


@dataclass(slots=True)
class ScriptMurderWorkflowConfig:
    case_root: Path | None = None


class ScriptMurderEnvironment(Environment):
    """Run one deterministic two-round murder-mystery session."""

    session_mode = "script-murder"
    entry_agent = "player-1"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 6) -> None:
        self.session = session
        self.llm = llm
        self.model = model
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.sync_runtime = SynchronousAppRuntime()
        self.event_dispatcher = RoomEventDispatcher()
        self.action_manager = ScriptMurderActionManager()
        self.case = load_case()
        self._active: AppSession[ScriptMurderState] | None = None
        self._task: Task | None = None
        placeholder = ScriptMurderState.initial("", "")
        super().__init__((), placeholder, Observation("script-murder-placeholder", "", ""), trace=session.trace)

    @classmethod
    def from_environment(cls, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data"), max_turns: int = 6) -> "ScriptMurderEnvironment":
        return cls(SessionManager(traces_root=traces_root, room_data_root=room_data_root), llm=OpenAICompatibleClient.from_environment(), model=os.getenv("COWORKER_MODEL", "deepseek-v4-flash"), max_turns=max_turns)

    def run(self, *, task: Task, session_id: str | None = None, on_session_opened: Callable[[str], None] | None = None, config: ScriptMurderWorkflowConfig | None = None) -> AgentResult:
        return SessionRuntime(trace=self.session.trace).run(self, task=task, session_id=session_id, on_session_opened=on_session_opened, config=config)

    def run_session(self, *, task: Task, context: SessionContext, config: ScriptMurderWorkflowConfig | None = None, **_: Any) -> AgentResult:
        self.case = load_case((config or ScriptMurderWorkflowConfig()).case_root) if config and config.case_root else load_case()
        self._active = self._open(task, context)
        self._task = task
        self.agents = tuple(self._active.agents.values())
        self.state = self._active.state
        state = self.sync_runtime.run(self, self._active)
        return AgentResult("completed", Message("assistant", state.ending_report), None, self._active.session_id)

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        current, active = self._state(state), self._require_active()
        player = self.action_manager.expected_player(current)
        return () if player is None else (active.agents[player],)

    def observe(self, state: State, agent: Agent) -> Observation:
        current, active = self._state(state), self._require_active()
        available = self.action_manager.available_actions(current, agent)
        return ScriptMurderObservation(
            state_message=build_state_message(current, agent.name, available), available_tool_names=available,
            public_room=active.room("public"), private_room=active.room(f"private:{agent.name}"),
            task_id=current.task_id, session_id=current.session_id,
        )

    def act(self, agent: Agent, observation: Observation) -> ScriptMurderActionValue | None:
        if not isinstance(observation, ScriptMurderObservation):
            raise TypeError("observation must be ScriptMurderObservation")
        active = self._require_active()
        turn = self.room_runtime.run_turn(
            room=active.room("public"), additional_rooms=(observation.private_room,), agent_name=agent.name,
            task=self._require_task(), session_id=active.session_id, incremental_context=active.contexts[agent.name],
            events=(observation.state_message,), available_tool_names=observation.available_tool_names,
        )
        if turn.status == "failed":
            raise RuntimeError(f"Script murder turn failed for {agent.name}: {turn.error}")
        return self.action_manager.resolve_action((agent.name, turn.content, observation))

    def ready_to_step(self, state: State, actions: object) -> bool:
        current = self._state(state)
        if current.phase is ScriptMurderPhase.RESOLUTION:
            return isinstance(actions, dict) and not actions
        return isinstance(actions, dict) and len(actions) == 1 and self.action_manager.validate_action(next(iter(actions.values())), current)

    def resolve_collected_actions(self, state: State, actions: dict[str, ActionEnvelope[Any]]) -> ScriptMurderActionValue | None:
        current = self._state(state)
        if current.phase is ScriptMurderPhase.RESOLUTION:
            return None
        if len(actions) != 1:
            raise RuntimeError(f"Expected one script murder actor in phase {current.phase.value}")
        return self.action_manager.resolve_actions(current, next(iter(actions.values())))

    def after_transition(self, old_state: State, actions: object, new_state: State) -> State:
        before, after = self._state(old_state), self._state(new_state)
        if before.phase is ScriptMurderPhase.ROUND_1_DISCUSSION and after.phase is ScriptMurderPhase.ROUND_2_DISCUSSION:
            self._deliver_round(2)
        return after

    def step(self, state: State, action: Any) -> State:
        current, active = self._state(state), self._require_active()
        next_state = ScriptMurderState.from_dict(current.to_dict())
        if next_state.phase is ScriptMurderPhase.RESOLUTION:
            self._resolve_case(next_state)
        else:
            resolved = self.action_manager.resolve_actions(next_state, action)
            if not self.action_manager.validate_action(resolved, next_state):
                self.reject_tool_action(
                    agent=active.agents[resolved.actor], observation=resolved.observation, tool_call=resolved.tool_call,
                    reason="Action 未通过当前剧本杀状态验证。",
                    message_sink=active.contexts[resolved.actor].append_turn_messages,
                )
                raise ValueError(f"Illegal action {resolved.name!r} from {resolved.actor!r}")
            actor = active.agents[resolved.actor]
            self.execute_tool_action(
                agent=actor,
                observation=resolved.observation,
                tool_call=resolved.tool_call,
                message_sink=active.contexts[resolved.actor].append_turn_messages,
            )
            next_state.consumed_action_ids.add(resolved.message_id)
            if next_state.phase in DISCUSSION_PHASES:
                if resolved.name == "speak":
                    active.room("public").send(RoomMessage(name=resolved.actor, at="all", txt=resolved.content))
                next_state.speaker_index += 1
                if next_state.speaker_index == len(PLAYERS):
                    next_state.speaker_index = 0
                    next_state.phase = ScriptMurderPhase.ROUND_2_DISCUSSION if next_state.phase is ScriptMurderPhase.ROUND_1_DISCUSSION else ScriptMurderPhase.FINAL_SUBMISSION
            else:
                if resolved.submission is None:
                    raise ValueError("Final submission payload is missing")
                next_state.final_submissions[resolved.actor] = resolved.submission
                if len(next_state.final_submissions) == len(PLAYERS):
                    next_state.phase = ScriptMurderPhase.RESOLUTION
        active.state = next_state
        self.state = next_state
        return next_state

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[AppEvent, ...]:
        before, after = self._state(old_state), self._state(new_state)
        if before.phase is not after.phase:
            labels = {
                ScriptMurderPhase.ROUND_2_DISCUSSION: "第一轮结束。第二轮私密材料已投递，开始第二轮讨论。",
                ScriptMurderPhase.FINAL_SUBMISSION: "讨论结束。请依次私下提交最终声明、决定性行动和党魁选票。",
                ScriptMurderPhase.RESOLUTION: "所有角色均已提交最终决定，开始统一结算。",
                ScriptMurderPhase.FINISHED: after.ending_report,
            }
            content = labels.get(after.phase)
            return () if content is None else (AppEvent(f"{after.session_id}:script-murder:{after.phase.value}", "phase_changed", ENGINE_NAME, content),)
        return ()

    def dispatch_events(self, events: tuple[AppEvent, ...]) -> None:
        deliveries = tuple(EventDelivery(event.event_id, "public") for event in events)
        self.event_dispatcher.dispatch(events, deliveries, rooms=self._require_active().rooms)

    def orchestrate_agents(self) -> Any:
        return self.run

    def _open(self, task: Task, context: SessionContext) -> AppSession[ScriptMurderState]:
        session_id = context.session_id
        store = StateStore(self.session.trace.root.parent / "state" / "data")
        if context.resumed:
            metadata = self.session.trace.session_data(session_id)
            public_room_id = metadata.get("script_murder_public_room_id")
            private_room_ids = metadata.get("script_murder_private_room_ids")
            if not isinstance(public_room_id, str) or not isinstance(private_room_ids, dict):
                raise ValueError(f"Session has no script murder ROOM metadata: {session_id}")
            public_room = self.session.resume_room(public_room_id, session_id=session_id)
            private_rooms = {str(player): self.session.resume_room(str(room_id), session_id=session_id) for player, room_id in private_room_ids.items()}
            state = store.restore(session_id, "script_murder", ScriptMurderState)
        else:
            assignments = dict(zip(PLAYERS, self.case.character_order, strict=True))
            state = ScriptMurderState.initial(task.description, session_id, case_id=self.case.case_id, assignments=assignments)
            public_room = self.session.create_room(f"script-murder-public-{session_id}", session_id=session_id)
            private_rooms = {player: self.session.create_room(f"script-murder-{player}-{session_id}", session_id=session_id) for player in PLAYERS}
            self.session.trace.update_session_metadata(session_id, public_room_id=public_room.room_id, script_murder_public_room_id=public_room.room_id, script_murder_private_room_ids={player: room.room_id for player, room in private_rooms.items()})
        engine_profile = AgentProfile(name=ENGINE_NAME, introduction="Deterministic murder-mystery engine.", role="game-engine")
        for room in (public_room, *private_rooms.values()):
            if ENGINE_NAME not in room.participants():
                room.register(engine_profile)
                room.invite(ENGINE_NAME)
        agents = {
            player: ScriptMurderAgent(
                self.llm, self.model, name=player, character=self.case.characters[state.character_for(player)],
                public_room=public_room, private_room=private_rooms[player],
            )
            for player in PLAYERS
        }
        for player, agent in agents.items():
            character = self.case.characters[state.character_for(player)]
            self.room_runtime.register_agent(agent, AgentProfile(name=player, introduction=character.name, role=character.character_id))
        missing_public = tuple(player for player in PLAYERS if player not in public_room.participants())
        if missing_public:
            self.room_runtime.invite_agents(public_room, missing_public, session_id=session_id)
        for player, room in private_rooms.items():
            if player not in room.participants():
                self.room_runtime.invite_agents(room, (player,), session_id=session_id)
        active = AppSession(
            session_id, state, agents,
            {player: self.room_runtime.open_incremental_context(agent_name=player, task=task, session_id=session_id) for player in PLAYERS},
            {"public": public_room, **{f"private:{player}": room for player, room in private_rooms.items()}},
            store, "script_murder",
        )
        self._active = active
        if not context.resumed:
            self._publish_opening()
            self._deliver_round(1)
        active.persist()
        return active

    def _publish_opening(self) -> None:
        active = self._require_active()
        cast = "\n".join(f"- {self.case.characters[key].name}：{value}" for key, value in self.case.public_cast.items())
        situation = "\n".join(f"- {item}" for item in self.case.public_situation)
        active.room("public").send(RoomMessage(name=ENGINE_NAME, at="all", txt=f"# {self.case.title}\n\n{self.case.public_briefing}\n\n{situation}\n\n公开角色：\n{cast}"))
        for player in PLAYERS:
            room = active.room(f"private:{player}")
            character = self.case.characters[active.state.character_for(player)]
            goals = "\n".join(f"- {item}" for item in character.goals)
            room.send(RoomMessage(name=ENGINE_NAME, at=player, txt=f"你的角色是 {character.name}。\n\n{character.private_briefing}\n\n你的目标：\n{goals}"))

    def _deliver_round(self, round_no: int) -> None:
        active = self._require_active()
        for document_id in self.case.deliveries.get(round_no, ()):
            if document_id in active.state.delivered_document_ids:
                continue
            document = self.case.documents[document_id]
            if document.recipients == "all":
                active.room("public").send(RoomMessage(name=ENGINE_NAME, at="all", txt=f"【第 {round_no} 轮材料】{document.title}\n{document.content}"))
            else:
                for character_id in document.recipients:
                    player = active.state.player_for(character_id)
                    active.room(f"private:{player}").send(RoomMessage(name=ENGINE_NAME, at=player, txt=f"【第 {round_no} 轮私密材料】{document.title}\n{document.content}"))
            active.state.delivered_document_ids.add(document_id)
        active.persist()

    def _resolve_case(self, state: ScriptMurderState) -> None:
        by_character = {state.character_for(player): submission for player, submission in state.final_submissions.items()}
        guards = Counter(item.target for item in by_character.values() if item.decisive_action == "guard")
        investigations = Counter(item.target for item in by_character.values() if item.decisive_action == "investigate")
        murders: list[dict[str, object]] = []
        killed: set[str] = set()
        for actor, submission in by_character.items():
            if submission.decisive_action != "murder" or submission.target is None:
                continue
            blocked = guards[submission.target] >= 2 or investigations[actor] >= 2
            murders.append({"actor": actor, "target": submission.target, "blocked": blocked})
            if not blocked:
                killed.add(submission.target)
        state.alive_character_ids -= killed
        votes = Counter(
            submission.leader_vote
            for actor, submission in by_character.items()
            if actor in state.alive_character_ids and submission.leader_vote in state.alive_character_ids
        )
        leader = None
        if votes:
            top = max(votes.values())
            leader = next(character_id for character_id in self.case.character_order if votes[character_id] == top)
        declarations = [
            {"character_id": actor, "declarations": list(submission.declarations)}
            for actor, submission in by_character.items() if actor in state.alive_character_ids and submission.declarations
        ]
        state.resolution = {
            "guards": dict(guards), "investigations": dict(investigations), "murders": murders,
            "killed": sorted(killed), "leader_votes": dict(votes), "elected_leader": leader,
            "tie_break_rule": "case_character_order", "declarations": declarations,
        }
        state.ending_report = self._ending_report(state)
        state.phase = ScriptMurderPhase.FINISHED

    def _ending_report(self, state: ScriptMurderState) -> str:
        names = {key: value.name for key, value in self.case.characters.items()}
        leader = state.resolution.get("elected_leader")
        killed = state.resolution.get("killed", [])
        lines = [
            f"《{self.case.title}》结算完成。",
            f"当选党魁：{names.get(str(leader), '无人')}。",
            "死亡角色：" + ("、".join(names[item] for item in killed) if killed else "无"),
            "",
            "案件真相：",
            "- 安德烈·罗伯斯庇尔是潜伏自由党的极端民族主义卧底。",
            "- 卡米耶·波拿巴在争执中将莫里斯推下阳台。",
            "- 安德烈与玛丽秘密交往已有六个月。",
            "",
            "角色目标复盘：",
        ]
        for character_id in self.case.character_order:
            character = self.case.characters[character_id]
            lines.append(f"- {character.name}：" + "；".join(character.goals))
        lines.append("\n最终声明、行动及投票的完整结构化结果已保存在 Session State 和 Trace 中。")
        return "\n".join(lines)

    def _require_active(self) -> AppSession[ScriptMurderState]:
        if self._active is None:
            raise RuntimeError("Script murder session has not started")
        return self._active

    def _require_task(self) -> Task:
        if self._task is None:
            raise RuntimeError("Script murder session has no task")
        return self._task

    @staticmethod
    def _state(state: State) -> ScriptMurderState:
        if not isinstance(state, ScriptMurderState):
            raise TypeError("state must be ScriptMurderState")
        return state
