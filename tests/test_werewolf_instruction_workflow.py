from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codeharness.apps.werewolf_instruction.environment import WerewolfInstructionEnvironment
from codeharness.apps.werewolf_instruction.state import PARTICIPANTS
from codeharness.core.models import Message, ModelResult, Task, ToolCall
from codeharness.infra.client import LLMClient
from codeharness.infra.runtimes import SessionRuntime
from codeharness.infra.session import SessionManager
from tool_message_assertions import assert_tool_calls_are_paired


class DiscussionLLM(LLMClient):
    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        assert_tool_calls_are_paired(messages)
        if messages[-1].role == "tool":
            return ModelResult(raw_content="done", parsed_content="done", model=model)
        state_message = next(message for message in reversed(messages) if message.role == "user" and '"type": "werewolf_instruction_state"' in str(message.content))
        participant = json.loads(state_message.content)["participant"]
        return ModelResult(
            raw_content="",
            tool_calls=(
                ToolCall(f"{participant}-speak", "speak", {"content": f"{participant} 分享一条可供大家吸收的策略。"}),
                ToolCall(f"{participant}-submit", "submit_my_instruction", {"instruction": f"面对信息不足的局面时，{participant} 建议结合发言变化和投票关系持续修正判断。"}),
            ),
            model=model,
        )


def test_discussion_builds_plain_tutorial_and_resumes(tmp_path: Path) -> None:
    environment = WerewolfInstructionEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=DiscussionLLM(),
        model="test",
    )
    result = SessionRuntime(trace=environment.session.trace).run(environment, task=Task("交流狼人杀心得并编写教程"))

    assert result.status == "completed", result.error
    expected = "\n\n".join(f"面对信息不足的局面时，{name} 建议结合发言变化和投票关系持续修正判断。" for name in PARTICIPANTS)
    assert result.content.content == expected
    assert "##" not in expected
    assert "的心得" not in expected
    assert environment.state.tutorial == expected
    room_id = environment.trace.session_data(result.session_id)["werewolf_instruction_room_id"]
    discussion = environment.trace.room_messages(result.session_id, room_id)
    assert all(any(message.name == name and "分享一条" in str(message.txt) for message in discussion) for name in PARTICIPANTS)
    assert environment._active is not None
    for context in environment._active.contexts.values():
        assert_tool_calls_are_paired(context.history())

    resumed = WerewolfInstructionEnvironment(
        SessionManager(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room"),
        llm=DiscussionLLM(),
        model="test",
    )
    resumed_result = SessionRuntime(trace=resumed.session.trace).run(resumed, task=Task("继续"), session_id=result.session_id)
    assert resumed_result.status == "completed"
    assert resumed_result.content.content == expected
    assert resumed.trace.session_data(result.session_id)["resume_count"] == 1
    assert resumed._active is not None
    for context in resumed._active.contexts.values():
        assert_tool_calls_are_paired(context.history())
