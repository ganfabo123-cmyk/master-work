from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from coworker.apps.jubensha_haishanxianguan.action import HaishanActionPayload
from coworker.apps.jubensha_haishanxianguan.agent import build_agents
from coworker.apps.jubensha_haishanxianguan.environment import HaishanXianguanEnvironment
from coworker.apps.jubensha_haishanxianguan.observation import HaishanObservation
from coworker.apps.jubensha_haishanxianguan.state import GamePhase, HaishanXianguanState
from coworker.core.action_envelope import ActionEnvelope
from coworker.core.base_observation import Observation
from coworker.core.models import AgentResult, Message, ModelResult, Task, ToolCall
from coworker.core.session import SessionContext
from coworker.infra.client import LLMClient


def action(state: HaishanXianguanState, actor: str, name: str, **arguments: object) -> ActionEnvelope:
    call = ToolCall(id=f"call-{len(state.consumed_action_ids)}", name=name, arguments=arguments)
    return ActionEnvelope(
        action_id=f"{actor}:{call.id}",
        actor=actor,
        name=name,
        payload=HaishanActionPayload(actor, name, arguments),
        tool_call=call,
        observation=Observation("obs", state.task_id, state.session_id),
    )


def advance_to_vote(env: HaishanXianguanEnvironment) -> HaishanXianguanState:
    state = HaishanXianguanState.initial("task", "session")
    for role in state.role_order:
        state = env.apply_action(state, action(state, role, "introduce_character", content=f"我是{role}"))
    assert state.phase is GamePhase.PERSON_SEARCH
    for role in state.role_order:
        decisions = [
            {"clue_id": clue_id, "reveal": clue_id.endswith("1")}
            for clue_id in state.person_clue_assignments[role]
        ]
        state = env.apply_action(state, action(state, role, "handle_clues", decisions=decisions))
    for role in state.role_order:
        state = env.apply_action(state, action(state, role, "discuss_publicly", content=f"{role} 第一轮发言"))
    for role in state.role_order:
        decisions = [
            {"clue_id": clue_id, "reveal": False}
            for clue_id in state.scene_clue_assignments[role]
        ]
        state = env.apply_action(state, action(state, role, "handle_clues", decisions=decisions))
    for role in state.role_order:
        state = env.apply_action(state, action(state, role, "discuss_publicly", content=f"{role} 第二轮发言"))
    assert state.phase is GamePhase.VOTE
    return state


def vote(state: HaishanXianguanState, role: str, suspect: str = "maid") -> ActionEnvelope:
    return action(
        state,
        role,
        "submit_vote",
        suspect_id=suspect,
        image_location="water_boat_beside_zhuyun_tower",
        motive="family_medical_cost_and_freedom",
        self_is_culprit=role == "maid",
        task_claims={"review": "已提交复盘陈述"},
    )


def test_ac_normal_01_and_terminal_01_domain_flow() -> None:
    env = HaishanXianguanEnvironment.from_environment()
    state = advance_to_vote(env)
    for role in state.role_order:
        state = env.apply_action(state, vote(state, role))
    assert state.phase is GamePhase.REVEAL
    assert state.collective_result == {"success": True, "leaders": ["maid"], "reason": "unique_correct"}
    state = env.apply_action(state, None)
    assert state.phase is GamePhase.SCORE and state.truth_revealed
    state = env.apply_action(state, None)
    assert state.is_terminal
    assert state.winner_ids == state.role_order
    assert all(score["rate"] == 1.0 for score in state.scores.values())
    events = env.build_events(HaishanXianguanState.from_dict({**state.to_dict(), "phase": "score", "terminal_result": None}), None, state)
    assert any(event.event_type == "terminal_result" for event in events)


def test_ac_pairing_01_appends_matching_tool_result_to_same_context() -> None:
    env = HaishanXianguanEnvironment.from_environment()
    env.agents = build_agents(llm=object(), model="mock")
    state = HaishanXianguanState.initial("task", "session")
    current = action(state, "pan", "introduce_character", content="我是潘仕成")
    context = SimpleNamespace(
        messages=[Message("assistant", "", tool_calls=(current.tool_call,))]
    )
    context.append_turn_messages = lambda messages: context.messages.extend(messages)
    env.active_session = SimpleNamespace(contexts={"pan": context})
    new_state = env.step(state, current)
    assert new_state.introductions["pan"] == "我是潘仕成"
    assert context.messages[-2].role == "assistant"
    assert context.messages[-2].tool_calls[0].id == current.tool_call.id
    assert context.messages[-1].role == "tool"
    assert context.messages[-1].tool_call_id == current.tool_call.id


def test_ac_vote_privacy_01_and_tie_01() -> None:
    env = HaishanXianguanEnvironment.from_environment()
    state = advance_to_vote(env)
    suspects = {"pan": "maid", "ivan": "maid", "li": "pan", "maid": "pan", "butler": "li", "he": "li"}
    for role in state.role_order:
        old = state
        current = vote(state, role, suspects[role])
        state = env.apply_action(state, current)
        events = env.build_events(old, current, state)
        if state.phase is GamePhase.VOTE:
            assert all(event.event_type != "votes_revealed" for event in events)
    assert state.collective_result["reason"] == "tie"
    assert not state.collective_result["success"]


def test_ac_recovery_01_resumes_at_next_actor_without_replay() -> None:
    env = HaishanXianguanEnvironment.from_environment()
    state = HaishanXianguanState.initial("task", "session")
    for role in state.role_order[:3]:
        state = env.apply_action(state, action(state, role, "introduce_character", content=role))
    restored = HaishanXianguanState.from_dict(state.to_dict())
    assert env.action_manager.current_actor(restored) == "maid"
    assert list(restored.introductions) == ["pan", "ivan", "li"]
    duplicate = action(restored, "pan", "introduce_character", content="duplicate")
    duplicate = ActionEnvelope(
        action_id=next(iter(restored.consumed_action_ids)),
        actor=duplicate.actor,
        name=duplicate.name,
        payload=duplicate.payload,
        tool_call=duplicate.tool_call,
        observation=duplicate.observation,
    )
    valid, reason = env.action_manager.validate_action(duplicate, restored)
    assert not valid and "已消费" in reason


class ScriptedLLMClient(LLMClient):
    """Return protocol-real ToolCalls derived only from the current Observation message."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        *,
        model: str,
        messages,
        tools: list[dict],
        **kwargs,
    ) -> ModelResult:
        observation = next(
            (
                json.loads(message.content)
                for message in reversed(messages)
                if message.role == "user"
                and isinstance(message.content, str)
                and message.content.startswith("{")
                and '"actor_id"' in message.content
            ),
            None,
        )
        if observation is None:
            raise AssertionError("ScriptedLLMClient did not receive an Observation payload")
        actor = str(observation["actor_id"])
        phase = str(observation["phase"])
        available = str(observation["available_action"])
        advertised_tools = {
            str(schema.get("name") or schema.get("function", {}).get("name"))
            for schema in tools
            if isinstance(schema, dict)
        }
        if available not in advertised_tools:
            raise AssertionError(
                f"Observation advertises {available}, but runtime tools are {sorted(advertised_tools)}"
            )
        if phase == GamePhase.INTRO.value:
            arguments = {"content": f"我是{actor}，这是固定测试介绍。"}
        elif phase in (GamePhase.PERSON_SEARCH.value, GamePhase.SCENE_SEARCH.value):
            clue_ids = tuple(observation["private_clue_ids"])
            if not clue_ids:
                raise AssertionError(f"{phase}/{actor} has no phase-authorized private clues")
            arguments = {
                "decisions": [
                    {"clue_id": clue_id, "reveal": True} for clue_id in clue_ids
                ]
            }
        elif phase in (
            GamePhase.PERSON_DISCUSS.value,
            GamePhase.SCENE_DISCUSS.value,
        ):
            arguments = {"content": f"{actor} 在 {phase} 的固定测试发言。"}
        elif phase == GamePhase.VOTE.value:
            arguments = {
                "suspect_id": "maid",
                "image_location": "water_boat_beside_zhuyun_tower",
                "motive": "family_medical_cost_and_freedom",
                "self_is_culprit": actor == "maid",
                "task_claims": {"review": "固定测试复盘"},
            }
        else:
            raise AssertionError(f"unexpected scripted phase: {phase}")
        call_id = f"scripted-{len(self.calls) + 1:03d}"
        tool_call = ToolCall(call_id, available, arguments)
        self.calls.append(
            {
                "actor": actor,
                "phase": phase,
                "tool": available,
                "arguments": arguments,
            }
        )
        return ModelResult(
            raw_content="",
            tool_calls=(tool_call,),
            model=model,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            finish_reason="tool_calls",
        )


def test_scripted_llm_runs_full_official_action_pipeline_to_terminal() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        scripted_llm = ScriptedLLMClient()
        env = HaishanXianguanEnvironment(
            traces_root=root / "traces",
            room_data_root=root / "rooms",
        )
        result = env.run(
            task=Task("完成《海山仙馆之寻》"),
            llm=scripted_llm,
            model="scripted",
        )
        assert result.status == "completed"
        assert env.active_session.state.is_terminal
        assert len(scripted_llm.calls) == 36
        assert {
            str(call["phase"]) for call in scripted_llm.calls
        } == {
            GamePhase.INTRO.value,
            GamePhase.PERSON_SEARCH.value,
            GamePhase.PERSON_DISCUSS.value,
            GamePhase.SCENE_SEARCH.value,
            GamePhase.SCENE_DISCUSS.value,
            GamePhase.VOTE.value,
        }
        trace_data = env.session.trace.session_data(result.session_id)
        assert trace_data["status"] == "completed"
        assert trace_data["app_id"] == env.session_mode
        assert env.session.trace.messages(result.session_id, "pan")
        public_messages = env.active_session.rooms["public"].history()
        assert any("侍" in message.txt and "小舟" in message.txt for message in public_messages)
        assert any("winner_ids" in message.txt and "NOT_SCORED" in message.txt for message in public_messages)
        private_history = env.active_session.rooms["private:maid"].history()
        assert any("04_侍女剧本.md" in message.txt for message in private_history)
        assert all("04_侍女剧本.md" not in message.txt for message in public_messages)


def test_ac_recovery_02_restores_boundary_and_deduplicates_stable_events() -> None:
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        options = {"llm": object(), "model": "mock"}
        task = Task("恢复《海山仙馆之寻》")
        first = HaishanXianguanEnvironment(
            traces_root=root / "traces",
            room_data_root=root / "rooms",
        )
        session_id = first.session.trace.create_session(task.description, "pan", mode=first.session_mode)
        first._open_or_restore_session(
            task=task,
            context=SessionContext(session_id, False),
            options=options,
        )
        initial_events = first.before_cycle(first.state)
        first.dispatch_events(initial_events)
        first.dispatch_events(initial_events)
        assert len(first.active_session.rooms["public"].history()) == 1
        first.state.introductions["pan"] = "已完成介绍"
        first.active_session.state = first.state
        first.active_session.persist()

        restored = HaishanXianguanEnvironment(
            traces_root=root / "traces",
            room_data_root=root / "rooms",
        )
        restored.session.trace.resume_session_state(session_id)
        restored._open_or_restore_session(
            task=task,
            context=SessionContext(session_id, True),
            options=options,
        )
        assert restored.state.introductions == {"pan": "已完成介绍"}
        assert restored.action_manager.current_actor(restored.state) == "ivan"
        assert len(restored.active_session.rooms["public"].history()) == 1


def test_model_configuration_prefers_deepseek_names() -> None:
    environment = HaishanXianguanEnvironment.from_environment()
    values = {
        "DEEPSEEK_API_KEY": "deepseek-key",
        "DEEPSEEK_MODEL": "deepseek-model",
        "DEEPSEEK_BASE_URL": "https://deepseek.example",
        "PRO_API": "alias-key",
        "PRO_MODEL": "alias-model",
    }
    with patch.dict(os.environ, values, clear=True), patch(
        "coworker.apps.jubensha_haishanxianguan.environment.OpenAICompatibleClient"
    ) as client_type:
        client, model = environment._resolve_model_configuration({})
    client_type.assert_called_once_with(
        api_key="deepseek-key",
        base_url="https://deepseek.example",
    )
    assert client is client_type.return_value
    assert model == "deepseek-model"


def test_model_configuration_supports_declared_pro_aliases() -> None:
    environment = HaishanXianguanEnvironment.from_environment()
    with patch.dict(
        os.environ,
        {"PRO_API": "alias-key", "PRO_MODEL": "alias-model"},
        clear=True,
    ), patch(
        "coworker.apps.jubensha_haishanxianguan.environment.OpenAICompatibleClient"
    ) as client_type:
        _, model = environment._resolve_model_configuration({})
    client_type.assert_called_once_with(
        api_key="alias-key",
        base_url="https://api.deepseek.com",
    )
    assert model == "alias-model"


def test_model_configuration_keeps_explicit_injection() -> None:
    environment = HaishanXianguanEnvironment.from_environment()
    injected = object()
    with patch.dict(os.environ, {}, clear=True):
        client, model = environment._resolve_model_configuration(
            {"llm": injected, "model": "mock"}
        )
    assert client is injected
    assert model == "mock"


def test_model_configuration_reports_safe_missing_names() -> None:
    environment = HaishanXianguanEnvironment.from_environment()
    with patch.dict(os.environ, {}, clear=True):
        try:
            environment._resolve_model_configuration({})
        except RuntimeError as error:
            message = str(error)
        else:
            raise AssertionError("missing model configuration must fail")
    assert "DEEPSEEK_MODEL" in message and "PRO_MODEL" in message
    assert "OPENAI_" not in message


def test_act_uses_public_room_runtime_contract_and_unwraps_result() -> None:
    environment = HaishanXianguanEnvironment.from_environment()
    environment.current_task = Task("测试 RoomRuntime 调用")
    context = object()
    environment.active_session = SimpleNamespace(contexts={"pan": context})
    tool_call = ToolCall(
        id="call-runtime",
        name="introduce_character",
        arguments={"content": "我是潘仕成"},
    )
    assistant = Message("assistant", "", tool_calls=(tool_call,))

    class FakeRoomRuntime:
        def __init__(self) -> None:
            self.kwargs = None

        def run_turn(self, **kwargs):
            self.kwargs = kwargs
            return AgentResult("completed", assistant, None, "session")

    runtime = FakeRoomRuntime()
    environment.room_runtime = runtime
    public_room = object()
    private_room = object()
    observation = HaishanObservation(
        observation_id="obs",
        task_id="task",
        session_id="session",
        actor_id="pan",
        state_message=Message("user", "{}"),
        available_tool_names=("introduce_character",),
        rooms=(public_room, private_room),
    )
    resolved = environment.act(SimpleNamespace(name="pan"), observation)
    assert resolved is not None
    assert resolved.tool_call.id == "call-runtime"
    assert runtime.kwargs["room"] is public_room
    assert runtime.kwargs["additional_rooms"] == (private_room,)
    assert runtime.kwargs["incremental_context"] is context
    assert "context" not in runtime.kwargs
