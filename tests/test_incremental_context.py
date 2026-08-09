from __future__ import annotations

import json
from pathlib import Path

from codeharness.infra.runtimes import IncrementalContext
from codeharness.core.models import Message
from codeharness.infra.room import AgentProfile, Room, RoomMessage, RoomTurnContext
from codeharness.infra.trace import TraceRecorder


def test_incremental_context_records_initial_prefix_once_and_restores_in_order(tmp_path: Path) -> None:
    trace = TraceRecorder(tmp_path)
    session_id = trace.create_session("task", "agent")
    context, initial = IncrementalContext.restore_or_initialize(
        restored_messages=(),
        initial_messages=(Message("developer", "stable instructions"), Message("user", "initial request")),
    )
    trace.record_messages(session_id, "agent", initial)
    event = Message("user", '{"type":"state","step":1}')
    trace.record_messages(session_id, "agent", context.append((event,)))

    restored, repeated_initial = IncrementalContext.restore_or_initialize(
        restored_messages=trace.messages(session_id, "agent"),
        initial_messages=(Message("developer", "stable instructions"), Message("user", "initial request")),
    )

    assert repeated_initial == ()
    assert restored.history() == context.history()


def test_room_turn_context_groups_inboxes_and_emits_standard_events(tmp_path: Path) -> None:
    profile = AgentProfile(name="agent", introduction="agent", skill=(), role="worker")
    sender = AgentProfile(name="sender", introduction="sender", skill=(), role="worker")
    public = Room("public", session_id="session", data_root=tmp_path)
    private = Room("private", session_id="session", data_root=tmp_path)
    for room in (public, private):
        room.register(profile)
        room.register(sender)
        room.invite("agent")
        room.invite("sender")
    public.send(RoomMessage(name="sender", at="agent", txt="public update"))
    private.send(RoomMessage(name="sender", at="agent", txt="private update"))

    turn = RoomTurnContext.receive(session_id="session", room=public, additional_rooms=(private,), agent_name="agent")
    events = [json.loads(message.content) for message in turn.room_message_events()]

    assert set(turn.inboxes) == {"public", "private"}
    assert [event["room_id"] for event in events] == ["public", "private"]
    assert turn.task_inputs()["rooms"]["private"]["inbox"][0]["txt"] == "private update"
