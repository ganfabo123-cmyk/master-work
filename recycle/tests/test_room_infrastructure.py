from __future__ import annotations

import json
from pathlib import Path

from codeharness.models import Message, Task
from codeharness.orchestrator import Orchestrator
from codeharness.room import AgentProfile, Room, RoomMessage


class RecordingAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.received_task: Task | None = None

    def run(self, task: Task, **_: object) -> Message:
        self.received_task = task
        return Message("assistant", f"{self.name} completed")


def _profile(name: str) -> AgentProfile:
    return AgentProfile(
        name=name,
        introduction=f"{name} agent",
        skill=("review",),
        role="reviewer",
        kwargs={"factory": "recording"},
    )


def test_room_persists_and_restores_unread_inbox(tmp_path: Path) -> None:
    room = Room("release", session_id="session-1", data_root=tmp_path)
    room.register(_profile("planner"))
    room.register(_profile("reviewer"))
    room.invite("planner")
    room.invite("reviewer")
    room.send(RoomMessage(name="planner", at="reviewer", txt="please inspect the rollback gate"))

    restored = Room.resume("release", session_id="session-1", data_root=tmp_path)

    assert restored.participants() == ("planner", "reviewer")
    assert restored.history()[0].txt == "please inspect the rollback gate"
    assert restored.receive("reviewer")[0].name == "planner"
    assert (tmp_path / "session-1" / "rooms" / "release.events.jsonl").exists()


def test_room_routes_private_group_message_only_to_named_participants(tmp_path: Path) -> None:
    room = Room("werewolf", session_id="session-wolves", data_root=tmp_path)
    for name in ("player-1", "player-2", "player-3", "player-6"):
        room.register(_profile(name))
        room.invite(name)

    room.send(RoomMessage(name="player-1", at=("player-1", "player-2", "player-6"), txt="今晚刀 player-3"))

    assert [message.txt for message in room.receive("player-1")] == ["今晚刀 player-3"]
    assert [message.txt for message in room.receive("player-2")] == ["今晚刀 player-3"]
    assert room.receive("player-3") == ()
    assert [message.txt for message in room.receive("player-6")] == ["今晚刀 player-3"]
    restored = Room.resume("werewolf", session_id="session-wolves", data_root=tmp_path)
    assert restored.history()[0].at == ("player-1", "player-2", "player-6")


def test_orchestrator_recovers_agent_and_passes_room_inbox(tmp_path: Path) -> None:
    orchestrator = Orchestrator(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room")
    planner = RecordingAgent("planner")
    reviewer = RecordingAgent("reviewer")
    orchestrator.register_agent(planner, _profile("planner"))  # type: ignore[arg-type]
    orchestrator.register_agent(reviewer, _profile("reviewer"))  # type: ignore[arg-type]
    room = orchestrator.create_room("release", session_id="session-2")
    orchestrator.invite_agents(room, ("planner", "reviewer"))
    room.send(RoomMessage(name="planner", at="reviewer", txt="inspect service signals"))
    session_id = orchestrator.trace.create_session("review release", reviewer.name, mode="room")

    result = orchestrator.run_room_turn(
        room=room,
        agent_name="reviewer",
        task=Task("review release"),
        session_id=session_id,
    )

    assert result.status == "completed"
    assert reviewer.received_task is not None
    assert reviewer.received_task.inputs["room"]["inbox"][0]["txt"] == "inspect service signals"
    assert room.receive("reviewer") == ()

    restored_orchestrator = Orchestrator(room_data_root=tmp_path / "room")
    restored_orchestrator.register_agent_factory("recording", lambda profile: RecordingAgent(profile.name))  # type: ignore[arg-type]
    restored_room = restored_orchestrator.resume_room("release", session_id="session-2")
    recovered = restored_orchestrator.restore_room_agents(restored_room)
    assert tuple(agent.name for agent in recovered) == ("planner", "reviewer")


def test_one_session_can_restore_multiple_rooms_without_agent_or_message_collisions(tmp_path: Path) -> None:
    traces = tmp_path / "traces"
    room_root = tmp_path / "room"
    orchestrator = Orchestrator(traces_root=traces, room_data_root=room_root)
    session_id = orchestrator.trace.create_session("two rooms", "planner-a", mode="multi-room")
    planner_a = RecordingAgent("planner-a")
    planner_b = RecordingAgent("planner-b")
    reviewer = RecordingAgent("reviewer")
    planner_a_profile = _profile("planner-a").model_copy(update={"display_name": "Planner"})
    planner_b_profile = _profile("planner-b").model_copy(update={"display_name": "Planner"})
    orchestrator.register_agent(planner_a, planner_a_profile)  # type: ignore[arg-type]
    orchestrator.register_agent(planner_b, planner_b_profile)  # type: ignore[arg-type]
    orchestrator.register_agent(reviewer, _profile("reviewer"))  # type: ignore[arg-type]
    planning = orchestrator.create_room("planning", session_id=session_id)
    review = orchestrator.create_room("review", session_id=session_id)
    orchestrator.invite_agents(planning, ("planner-a", "planner-b"), session_id=session_id)
    orchestrator.invite_agents(review, ("planner-a", "reviewer"), session_id=session_id)

    planning.send(RoomMessage(name="planner-a", at="planner-b", txt="draft the plan"))
    review.send(RoomMessage(name="planner-a", at="reviewer", txt="review the plan"))

    assert [message.txt for message in planning.history()] == ["draft the plan"]
    assert [message.txt for message in review.history()] == ["review the plan"]
    assert (traces / session_id / "agents" / "planner-a.jsonl").exists()
    assert "room_message_sent" in (traces / session_id / "agents" / "planner-a.md").read_text(encoding="utf-8")
    assert orchestrator.trace.messages(session_id, "planner-a") == ()
    assert not (room_root / session_id / "rooms" / "planning.json").read_text(encoding="utf-8").__contains__("draft the plan")

    restored = Orchestrator(traces_root=traces, room_data_root=room_root)
    restored_planning = restored.resume_room("planning", session_id=session_id)
    restored_review = restored.resume_room("review", session_id=session_id)
    assert [message.txt for message in restored_planning.receive("planner-b")] == ["draft the plan"]
    assert [message.txt for message in restored_review.receive("reviewer")] == ["review the plan"]


def test_resume_replays_agent_trace_when_room_snapshot_missed_a_delivery(tmp_path: Path) -> None:
    traces = tmp_path / "traces"
    room_root = tmp_path / "room"
    orchestrator = Orchestrator(traces_root=traces, room_data_root=room_root)
    session_id = orchestrator.trace.create_session("recover delivery", "sender", mode="multi-room")
    sender = RecordingAgent("sender")
    receiver = RecordingAgent("receiver")
    orchestrator.register_agent(sender, _profile("sender"))  # type: ignore[arg-type]
    orchestrator.register_agent(receiver, _profile("receiver"))  # type: ignore[arg-type]
    room = orchestrator.create_room("handoff", session_id=session_id)
    orchestrator.invite_agents(room, ("sender", "receiver"), session_id=session_id)
    room.send(RoomMessage(name="sender", at="receiver", txt="durable message"))

    state_path = room_root / session_id / "rooms" / "handoff.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["message_ids"] = []
    state["inboxes"]["receiver"] = []
    state_path.write_text(json.dumps(state), encoding="utf-8")

    resumed = Orchestrator(traces_root=traces, room_data_root=room_root).resume_room("handoff", session_id=session_id)
    assert [message.txt for message in resumed.receive("receiver")] == ["durable message"]
