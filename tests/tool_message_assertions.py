from __future__ import annotations

from collections.abc import Iterable

from coworker.core.models import Message


def assert_tool_calls_are_paired(messages: Iterable[Message]) -> None:
    pending: set[str] = set()
    for message in messages:
        if message.role == "assistant":
            pending.update(call.id for call in message.tool_calls)
        elif message.role == "tool":
            assert message.tool_call_id in pending, f"tool result has no preceding call: {message.tool_call_id}"
            pending.remove(message.tool_call_id)
    assert not pending, f"tool calls have no results: {sorted(pending)}"
