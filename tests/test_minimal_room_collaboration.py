from __future__ import annotations

from pathlib import Path
from typing import Any

from codeharness.agents import Agent
from codeharness.llm import LLMClient, ModelResult
from codeharness.models import Message, Prompt, Task
from codeharness.orchestrator import Orchestrator
from codeharness.room import AgentProfile, RoomMessage


class ScenarioLLM(LLMClient):
    """Deterministic model double that makes the collaboration contract observable."""

    def generate(self, *, model: str, messages: tuple[Message, ...], tools: list[dict[str, Any]], **_: Any) -> ModelResult:
        user_message = next(message for message in reversed(messages) if message.role == "user")
        if "Prepare a rollback plan" in user_message.content:
            content = "PLAN: pause rollout; verify error rate; roll back if errors remain elevated."
        else:
            assert "Planner proposal:" in user_message.content
            assert "verify error rate" in user_message.content
            content = "REVIEW: approved after confirming the rollback owner and error-rate threshold."
        return ModelResult(raw_content=content, parsed_content=content, model=model, finish_reason="stop")


def _profile(name: str, role: str) -> AgentProfile:
    return AgentProfile(
        name=name,
        introduction=f"{role} for release incidents",
        skill=("release-incident",),
        role=role,
    )


def _planner_prompt(task: Task) -> Prompt:
    return Prompt((Message("developer", "You are the release planner."), Message("user", task.description)))


def _reviewer_prompt(task: Task) -> Prompt:
    inbox = task.inputs["room"]["inbox"]
    proposal = next(message["txt"] for message in inbox if message["name"] == "planner")
    return Prompt(
        (
            Message("developer", "You are the release reviewer."),
            Message("user", f"Review the release plan. Planner proposal: {proposal}"),
        )
    )


def test_planner_reviewer_room_collaboration_is_traceable(tmp_path: Path) -> None:
    """The application workflow owns publication; ROOM only transports the proposal."""
    orchestrator = Orchestrator(traces_root=tmp_path / "traces", room_data_root=tmp_path / "room")
    llm = ScenarioLLM()
    planner = Agent("planner", "scenario-model", llm, _planner_prompt)
    reviewer = Agent("reviewer", "scenario-model", llm, _reviewer_prompt)
    orchestrator.register_agent(planner, _profile("planner", "planner"))
    orchestrator.register_agent(reviewer, _profile("reviewer", "reviewer"))
    room = orchestrator.create_room("release-review", session_id="minimal-collaboration")
    orchestrator.invite_agents(room, ("planner", "reviewer"))
    session_id = orchestrator.trace.create_session("release review", "planner", mode="room")

    planner_result = orchestrator.run_room_turn(
        room=room,
        agent_name="planner",
        task=Task("Prepare a rollback plan for elevated post-release errors."),
        session_id=session_id,
    )
    assert planner_result.status == "completed"
    room.send(RoomMessage(name="planner", at="reviewer", txt=str(planner_result.content.content)))

    reviewer_result = orchestrator.run_room_turn(
        room=room,
        agent_name="reviewer",
        task=Task("Review the release plan."),
        session_id=session_id,
    )

    assert reviewer_result.status == "completed"
    assert reviewer_result.content.content == "REVIEW: approved after confirming the rollback owner and error-rate threshold."
    assert room.receive("reviewer") == ()
    assert room.history()[0].txt == planner_result.content.content
    assert (tmp_path / "traces" / planner_result.session_id / "agents" / "planner.jsonl").exists()
    assert (tmp_path / "traces" / reviewer_result.session_id / "agents" / "reviewer.jsonl").exists()
