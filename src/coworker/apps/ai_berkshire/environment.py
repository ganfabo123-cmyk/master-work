"""Synchronous AI Berkshire multi-Agent investment research Environment."""

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
from ...infra.room import AgentProfile
from ...infra.runtimes import SynchronousAppRuntime
from ...infra.runtimes.room_runtime import RoomRuntime
from ...infra.runtimes.session_runtime import SessionRuntime
from ...infra.session import AppSession, SessionManager
from .action import InvestmentAction
from .agent import InvestmentAgent
from .observation import InvestmentObservation, build_state_message
from .state import InvestmentMemo, InvestmentPhase, InvestmentRole, InvestmentState, ResearchArtifact
from .web_search import BaiduWebSearchClient, BaiduWebSearchTools, canonicalize_source_url

ENGINE_NAME = "investment-engine"
RESEARCHERS = {
    "business-analyst": InvestmentRole.BUSINESS,
    "financial-analyst": InvestmentRole.FINANCIAL,
    "industry-researcher": InvestmentRole.INDUSTRY,
    "risk-assessor": InvestmentRole.RISK,
}
TEAM = {**RESEARCHERS, "team-lead": InvestmentRole.LEAD}


@dataclass(frozen=True, slots=True)
class InvestmentActionPayload:
    title: str = ""
    thesis: str = ""
    content: str = ""
    score: int = 0
    confidence: int = 0
    citations: tuple[str, ...] = ()
    recommendation: str = ""
    source_artifact_ids: tuple[str, ...] = ()


class InvestmentActionValue(ActionEnvelope[InvestmentActionPayload]):
    pass


class InvestmentActionManager(ActionManager):
    def __init__(self, actions: dict[str, InvestmentAction], web_tools: dict[str, BaiduWebSearchTools]) -> None:
        self.actions = actions
        self.web_tools = web_tools

    def resolve_action(self, response: Any) -> InvestmentActionValue | None:
        if not isinstance(response, tuple) or len(response) != 3:
            return None
        actor, message, observation = response
        if not isinstance(actor, str) or not isinstance(message, Message) or not isinstance(observation, InvestmentObservation):
            return None
        try:
            call = next(item for item in message.tool_calls if item.name in {"submit_analysis", "submit_investment_memo"})
            arguments = json.loads(call.arguments) if isinstance(call.arguments, str) else dict(call.arguments)
            mapped = self.actions[actor].get_action(call.name)
            if mapped.name == "submit_analysis":
                payload = InvestmentActionPayload(
                    title=str(arguments["title"]).strip(), thesis=str(arguments["thesis"]).strip(),
                    content=str(arguments["content"]).strip(), score=int(arguments["score"]),
                    confidence=int(arguments["confidence"]),
                    citations=tuple(str(item).strip() for item in arguments.get("citations", []) if str(item).strip()),
                )
            else:
                payload = InvestmentActionPayload(
                    thesis=str(arguments["summary"]).strip(), content=str(arguments["content"]).strip(),
                    score=int(arguments["score"]), confidence=int(arguments["confidence"]),
                    recommendation=str(arguments["recommendation"]).strip(),
                    source_artifact_ids=tuple(str(item) for item in arguments["source_artifact_ids"]),
                )
            return InvestmentActionValue(f"{actor}:{call.id}", actor, mapped.name, payload, call, observation)
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
            return None

    def validate_action(self, action: Any, state: State) -> tuple[bool, str]:
        if not isinstance(action, InvestmentActionValue) or not isinstance(state, InvestmentState):
            return False, "提交参数无法解析；请检查所有必填字段及字段类型。"
        payload = action.payload
        if action.action_id in state.consumed_action_ids or action.actor not in TEAM:
            return False, "该 Action 已消费，或提交者不属于当前投研团队。"
        if not payload.content or not payload.thesis or not 1 <= payload.score <= 5 or not 0 <= payload.confidence <= 100:
            return False, "正文和核心结论不能为空；score 必须为 1 到 5，confidence 必须为 0 到 100。"
        role = TEAM[action.actor]
        if state.phase is InvestmentPhase.PARALLEL_RESEARCH:
            searched_urls = self.web_tools.get(action.actor)
            if role is InvestmentRole.LEAD or action.name != "submit_analysis":
                return False, "当前阶段只有四位分析师可以调用 submit_analysis。"
            if not payload.title:
                return False, "title 不能为空。"
            if not payload.citations:
                return False, "citations 不能为空，且只能填写本回合 search_web 返回的真实 URL。"
            if searched_urls is None or not {canonicalize_source_url(url) for url in payload.citations} <= searched_urls.source_urls:
                return False, "citations 包含本回合 search_web 未返回的 URL。"
            return True, ""
        if state.phase is InvestmentPhase.SYNTHESIS:
            if role is not InvestmentRole.LEAD or action.name != "submit_investment_memo":
                return False, "当前阶段只有 team-lead 可以调用 submit_investment_memo。"
            if payload.recommendation not in {"买入", "观察", "回避"}:
                return False, "recommendation 必须精确填写“买入”“观察”或“回避”，补充说明请写入 summary 或 content。"
            if set(payload.source_artifact_ids) != {item.artifact_id for item in state.artifacts.values()}:
                return False, "source_artifact_ids 必须完整且仅包含 Observation 中的四个 artifact_id。"
            return True, ""
        return False, "当前投研阶段不接受新的 Action。"

    def available_actions(self, state: State, agent: Agent) -> tuple[str, ...]:
        if not isinstance(state, InvestmentState):
            return ()
        role = TEAM.get(agent.name)
        if state.phase is InvestmentPhase.PARALLEL_RESEARCH and role is not None and role is not InvestmentRole.LEAD:
            return ("submit_analysis",)
        if state.phase is InvestmentPhase.SYNTHESIS and role is InvestmentRole.LEAD:
            return ("submit_investment_memo",)
        return ()

    def resolve_actions(self, state: State, actions: object) -> dict[str, InvestmentActionValue]:
        if not isinstance(actions, dict) or not all(isinstance(key, str) and isinstance(value, InvestmentActionValue) for key, value in actions.items()):
            raise TypeError("actions must be dict[str, InvestmentActionValue]")
        return actions


@dataclass(slots=True)
class InvestmentWorkflowConfig:
    company_name: str
    ticker: str = ""
    research_context: str = ""
    information_grade: str = "B"
    data_cutoff: str = ""

    def __post_init__(self) -> None:
        self.company_name = self.company_name.strip()
        self.information_grade = self.information_grade.upper().strip()
        if not self.company_name:
            raise ValueError("company_name is required")
        if self.information_grade not in {"A", "B", "C"}:
            raise ValueError("information_grade must be A, B, or C")


class AIBerkshireEnvironment(Environment):
    session_mode = "ai-berkshire"
    entry_agent = "team-lead"

    def __init__(self, session: SessionManager, *, llm: LLMClient, model: str, max_turns: int = 8, search_client: BaiduWebSearchClient | None = None) -> None:
        self.session, self.llm, self.model, self.max_turns = session, llm, model, max_turns
        self.search_client = search_client or BaiduWebSearchClient.from_environment()
        self.room_runtime = RoomRuntime(trace=session.trace, max_turns=max_turns)
        self.sync_runtime = SynchronousAppRuntime()
        self.event_dispatcher = RoomEventDispatcher()
        self.action_manager: InvestmentActionManager | None = None
        self._active: AppSession[InvestmentState] | None = None
        self._task: Task | None = None
        super().__init__((), InvestmentState.initial("", ""), Observation("investment-placeholder", "", ""), trace=session.trace)

    @classmethod
    def from_environment(cls, *, traces_root: Path = Path("traces"), room_data_root: Path = Path("room/data"), max_turns: int = 8) -> "AIBerkshireEnvironment":
        return cls(SessionManager(traces_root=traces_root, room_data_root=room_data_root), llm=OpenAICompatibleClient.from_environment(), model=os.getenv("COWORKER_MODEL", "deepseek-v4-flash"), max_turns=max_turns)

    def run(self, *, task: Task, config: InvestmentWorkflowConfig | None = None, session_id: str | None = None, on_session_opened: Callable[[str], None] | None = None) -> AgentResult:
        return SessionRuntime(trace=self.session.trace).run(self, task=task, session_id=session_id, on_session_opened=on_session_opened, config=config)

    def run_session(self, *, task: Task, context: SessionContext, config: InvestmentWorkflowConfig | None = None, **_: Any) -> AgentResult:
        self._active = None
        try:
            active = self._open(task, context, config or self._config_from_task(task))
            self._active, self._task = active, task
            self.agents, self.state = tuple(active.agents.values()), active.state
            self.action_manager = InvestmentActionManager(
                {name: agent.action for name, agent in active.agents.items()},
                {
                    name: agent.web_tools
                    for name, agent in active.agents.items()
                    if isinstance(agent, InvestmentAgent) and agent.web_tools is not None
                },
            )
            state = self.sync_runtime.run(self, active)
            memo = state.final_memo
            text = "投资研究完成。" if memo is None else f"{state.company_name}：{memo.recommendation}（{memo.score}/5）\n\n{memo.summary}\n\n{memo.content}"
            return AgentResult("completed", Message("assistant", text), None, active.session_id)
        except Exception:
            if self._active is not None:
                self._active.persist()
            raise

    def select_agents(self, state: State) -> tuple[Agent, ...]:
        current, active = self._state(state), self._require_active()
        names = tuple(RESEARCHERS) if current.phase is InvestmentPhase.PARALLEL_RESEARCH else ("team-lead",) if current.phase is InvestmentPhase.SYNTHESIS else ()
        return tuple(active.agents[name] for name in names)

    def observe(self, state: State, agent: Agent) -> Observation:
        current, active, manager = self._state(state), self._require_active(), self._manager()
        actions = manager.available_actions(current, agent)
        available = ("search_web", *actions) if TEAM[agent.name] is not InvestmentRole.LEAD else actions
        return InvestmentObservation(state_message=build_state_message(current, TEAM[agent.name]), available_tool_names=available, room=active.room("research"), task_id=current.task_id, session_id=current.session_id)

    def act(self, agent: Agent, observation: Observation) -> InvestmentActionValue | None:
        if not isinstance(observation, InvestmentObservation):
            raise TypeError("observation must be InvestmentObservation")
        active = self._require_active()
        events = (observation.state_message,)
        for attempt in range(3):
            turn = self.room_runtime.run_turn(
                room=active.room("research"),
                agent_name=agent.name,
                task=self._require_task(),
                session_id=active.session_id,
                incremental_context=active.contexts[agent.name],
                events=events,
                available_tool_names=observation.available_tool_names,
            )
            if turn.status == "failed":
                raise RuntimeError(f"Investment research turn failed for {agent.name}: {turn.error}")
            action = self._manager().resolve_action((agent.name, turn.content, observation))
            valid, reason = self._manager().validate_action(action, self.state)
            if action is not None and valid:
                return action
            tool_call = next(
                (
                    call
                    for call in (() if turn.content is None else turn.content.tool_calls)
                    if call.name in {"submit_analysis", "submit_investment_memo"}
                ),
                None,
            )
            if tool_call is None:
                raise RuntimeError(f"Investment Agent {agent.name} did not submit an Action")
            self.reject_tool_action(
                agent=agent,
                observation=observation,
                tool_call=tool_call,
                reason=reason,
                message_sink=active.contexts[agent.name].append_turn_messages,
            )
            events = ()
            if attempt == 2:
                break
        raise RuntimeError(f"Investment Agent {agent.name} failed to produce a valid Action after correction")

    def ready_to_step(self, state: State, actions: object) -> bool:
        expected = 4 if self._state(state).phase is InvestmentPhase.PARALLEL_RESEARCH else 1
        return isinstance(actions, dict) and len(actions) == expected

    def step(self, state: State, action: Any) -> State:
        current, active = self._state(state), self._require_active()
        next_state = InvestmentState.from_dict(current.to_dict())
        actions = self._manager().resolve_actions(next_state, action)
        for item in actions.values():
            valid, reason = self._manager().validate_action(item, next_state)
            if not valid:
                self.reject_tool_action(agent=active.agents[item.actor], observation=item.observation, tool_call=item.tool_call, reason=reason, message_sink=active.contexts[item.actor].append_turn_messages)
                raise ValueError(f"Illegal investment action {item.name!r} from {item.actor!r}")
            self.execute_tool_action(agent=active.agents[item.actor], observation=item.observation, tool_call=item.tool_call, message_sink=active.contexts[item.actor].append_turn_messages)
        next_state.consumed_action_ids.update(item.action_id for item in actions.values())
        if next_state.phase is InvestmentPhase.PARALLEL_RESEARCH:
            for item in actions.values():
                next_state.artifacts[item.actor] = ResearchArtifact(item.action_id, item.actor, TEAM[item.actor], item.payload.title, item.payload.thesis, item.payload.content, item.payload.score, item.payload.confidence, item.payload.citations)
            next_state.phase = InvestmentPhase.SYNTHESIS
        else:
            item = next(iter(actions.values()))
            next_state.final_memo = InvestmentMemo(item.action_id, item.payload.recommendation, item.payload.thesis, item.payload.content, item.payload.score, item.payload.confidence, item.payload.source_artifact_ids)
            next_state.phase = InvestmentPhase.FINISHED
        active.state = next_state
        self.state = next_state
        return next_state

    def build_events(self, old_state: State, actions: object, new_state: State) -> tuple[AppEvent, ...]:
        before, after = self._state(old_state), self._state(new_state)
        if before.phase is InvestmentPhase.PARALLEL_RESEARCH and after.phase is InvestmentPhase.SYNTHESIS:
            reports = tuple(
                AppEvent(
                    f"{after.session_id}:investment:report:{artifact.artifact_id}",
                    "research_report_submitted",
                    artifact.author,
                    f"# {artifact.title}\n\n{artifact.thesis}\n\n{artifact.content}",
                    {"artifact_id": artifact.artifact_id, "role": artifact.role.value},
                )
                for artifact in after.artifacts.values()
            )
            return (*reports, AppEvent(f"{after.session_id}:investment:synthesis", "research_completed", ENGINE_NAME, "四位分析师已提交研究产物，team lead 开始综合研判。"))
        if after.phase is InvestmentPhase.FINISHED:
            memo = after.final_memo
            if memo is None:
                return ()
            return (
                AppEvent(
                    f"{after.session_id}:investment:memo:{memo.artifact_id}",
                    "investment_memo_submitted",
                    "team-lead",
                    f"# 最终投资备忘录：{memo.recommendation}\n\n{memo.summary}\n\n{memo.content}",
                    {"artifact_id": memo.artifact_id, "score": memo.score, "confidence": memo.confidence},
                ),
                AppEvent(f"{after.session_id}:investment:finished", "workflow_finished", ENGINE_NAME, "team lead 已提交最终投资备忘录。"),
            )
        return ()

    def dispatch_events(self, events: tuple[AppEvent, ...]) -> None:
        self.event_dispatcher.dispatch(events, tuple(EventDelivery(event.event_id, "research") for event in events), rooms=self._require_active().rooms)

    def orchestrate_agents(self) -> Any:
        return self.run

    def _open(self, task: Task, context: SessionContext, config: InvestmentWorkflowConfig) -> AppSession[InvestmentState]:
        store = StateStore(self.session.trace.root.parent / "state" / "data")
        session_id = context.session_id
        if not context.resumed:
            state = InvestmentState(task_id=task.description, session_id=session_id, company_name=config.company_name, ticker=config.ticker, data_cutoff=config.data_cutoff, information_grade=config.information_grade, research_context=config.research_context)
            room = self.session.create_room(f"ai-berkshire-{session_id}", session_id=session_id)
            self.session.trace.update_session_metadata(session_id, public_room_id=room.room_id, investment_room_id=room.room_id, company_name=config.company_name, ticker=config.ticker)
            room.register(AgentProfile(name=ENGINE_NAME, introduction="Deterministic investment research state-transition engine.", role="investment-engine"))
            room.invite(ENGINE_NAME)
        else:
            metadata = self.session.trace.session_data(session_id)
            if metadata.get("mode") != self.session_mode or not isinstance(metadata.get("investment_room_id"), str):
                raise ValueError(f"Session is not an AI Berkshire session: {session_id}")
            room = self.session.resume_room(metadata["investment_room_id"], session_id=session_id)
            state = store.restore(session_id, "ai_berkshire", InvestmentState)
        agents = {
            name: InvestmentAgent(self.llm, self.model, name=name, role=role, search_client=self.search_client)
            for name, role in TEAM.items()
        }
        for name, agent in agents.items():
            role = TEAM[name]
            self.room_runtime.register_agent(agent, AgentProfile(name=name, introduction=f"AI Berkshire {role.value} research role.", role=role.value))
        if not all(name in room.participants() for name in agents):
            self.room_runtime.invite_agents(room, tuple(agents), session_id=session_id)
        contexts = {name: self.room_runtime.open_incremental_context(agent_name=name, task=task, session_id=session_id) for name in agents}
        active = AppSession(session_id, state, agents, contexts, {"research": room}, store, "ai_berkshire")
        active.persist()
        return active

    def _require_active(self) -> AppSession[InvestmentState]:
        if self._active is None:
            raise RuntimeError("AI Berkshire session has not started")
        return self._active

    def _require_task(self) -> Task:
        if self._task is None:
            raise RuntimeError("AI Berkshire session has no Task")
        return self._task

    def _manager(self) -> InvestmentActionManager:
        if self.action_manager is None:
            raise RuntimeError("AI Berkshire session has no ActionManager")
        return self.action_manager

    @staticmethod
    def _config_from_task(task: Task) -> InvestmentWorkflowConfig:
        inputs = task.inputs
        return InvestmentWorkflowConfig(
            company_name=str(inputs.get("company_name") or task.description),
            ticker=str(inputs.get("ticker") or ""),
            research_context=str(inputs.get("research_context") or ""),
            information_grade=str(inputs.get("information_grade") or "B"),
            data_cutoff=str(inputs.get("data_cutoff") or ""),
        )

    @staticmethod
    def _state(state: State) -> InvestmentState:
        if not isinstance(state, InvestmentState):
            raise TypeError("state must be InvestmentState")
        return state
