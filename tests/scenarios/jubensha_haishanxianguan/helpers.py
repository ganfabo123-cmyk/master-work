from __future__ import annotations

import json
from typing import Any

from coworker.core.models import ModelResult, ToolCall
from coworker.testing import ScriptedLLMError, ScriptedRequest, ScriptedTurn


def expect_tool_call(
    *,
    step: str,
    actor: str,
    phase: str,
    available_action: str,
    tool: str,
    arguments: dict[str, object],
    expected_clue_ids: tuple[str, ...] | None = None,
) -> ScriptedTurn:
    """Build one fixed reply plus assertions about the real Observation request."""

    def assert_request(request: ScriptedRequest) -> None:
        observation = _latest_observation(request)
        actual = {
            "actor": observation.get("actor_id"),
            "phase": observation.get("phase"),
            "action": observation.get("available_action"),
        }
        expected = {
            "actor": actor,
            "phase": phase,
            "action": available_action,
        }
        assert actual == expected, f"expected {expected}, got {actual}"
        if expected_clue_ids is not None:
            actual_clues = tuple(str(item) for item in observation.get("private_clue_ids", ()))
            assert actual_clues == expected_clue_ids, (
                f"expected clues {expected_clue_ids}, got {actual_clues}"
            )

    return ScriptedTurn(
        name=step,
        expected_model="scripted",
        required_tools=(tool,),
        assert_request=assert_request,
        response=ModelResult(
            raw_content="",
            tool_calls=(ToolCall(step, tool, arguments),),
            model="scripted",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            finish_reason="tool_calls",
        ),
    )


def _latest_observation(request: ScriptedRequest) -> dict[str, Any]:
    for message in reversed(request.messages):
        if message.role != "user" or not isinstance(message.content, str):
            continue
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "actor_id" in payload and "phase" in payload:
            return payload
    raise ScriptedLLMError("model request contains no serialized Observation")

