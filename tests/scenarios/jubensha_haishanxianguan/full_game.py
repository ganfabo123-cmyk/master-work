from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from coworker import Task
from coworker.apps.jubensha_haishanxianguan.environment import HaishanXianguanEnvironment
from coworker.apps.jubensha_haishanxianguan.state import GamePhase, ROLE_ORDER
from coworker.core.models import AgentResult
from coworker.testing import ScenarioRunner, ScriptedLLMClient, ScriptedTurn

from .helpers import expect_tool_call


PERSON_CLUES = {
    "pan": ("person-01", "person-02"),
    "ivan": ("person-03", "person-04"),
    "li": ("person-05", "person-06"),
    "maid": ("person-07", "person-08"),
    "butler": ("person-09", "person-10"),
    "he": ("person-11", "person-12"),
}

SCENE_CLUES = {
    "pan": ("scene-01", "scene-02", "scene-03"),
    "ivan": ("scene-04", "scene-05", "scene-06"),
    "li": ("scene-07", "scene-08"),
    "maid": ("scene-09", "scene-10"),
    "butler": ("scene-11", "scene-12"),
    "he": ("scene-13", "scene-14"),
}


@dataclass(frozen=True, slots=True)
class FullGameExecution:
    result: AgentResult
    environment: HaishanXianguanEnvironment


def _clue_arguments(clue_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "decisions": [
            {"clue_id": clue_id, "reveal": True}
            for clue_id in clue_ids
        ]
    }


def _build_turns() -> tuple[ScriptedTurn, ...]:
    turns: list[ScriptedTurn] = []
    for actor in ROLE_ORDER:
        turns.append(expect_tool_call(
            step=f"intro-{actor}",
            actor=actor,
            phase=GamePhase.INTRO.value,
            available_action="introduce_character",
            tool="introduce_character",
            arguments={"content": f"我是{actor}，这是正常流程固定介绍。"},
            expected_clue_ids=(),
        ))
    for actor in ROLE_ORDER:
        turns.append(expect_tool_call(
            step=f"person-search-{actor}",
            actor=actor,
            phase=GamePhase.PERSON_SEARCH.value,
            available_action="handle_clues",
            tool="handle_clues",
            arguments=_clue_arguments(PERSON_CLUES[actor]),
            expected_clue_ids=PERSON_CLUES[actor],
        ))
    for actor in ROLE_ORDER:
        turns.append(expect_tool_call(
            step=f"person-discuss-{actor}",
            actor=actor,
            phase=GamePhase.PERSON_DISCUSS.value,
            available_action="discuss_publicly",
            tool="discuss_publicly",
            arguments={"content": f"{actor} 的第一轮固定公开讨论。"},
        ))
    for actor in ROLE_ORDER:
        turns.append(expect_tool_call(
            step=f"scene-search-{actor}",
            actor=actor,
            phase=GamePhase.SCENE_SEARCH.value,
            available_action="handle_clues",
            tool="handle_clues",
            arguments=_clue_arguments(SCENE_CLUES[actor]),
            expected_clue_ids=SCENE_CLUES[actor],
        ))
    for actor in ROLE_ORDER:
        turns.append(expect_tool_call(
            step=f"scene-discuss-{actor}",
            actor=actor,
            phase=GamePhase.SCENE_DISCUSS.value,
            available_action="discuss_publicly",
            tool="discuss_publicly",
            arguments={"content": f"{actor} 的第二轮固定公开讨论。"},
        ))
    for actor in ROLE_ORDER:
        turns.append(expect_tool_call(
            step=f"vote-{actor}",
            actor=actor,
            phase=GamePhase.VOTE.value,
            available_action="submit_vote",
            tool="submit_vote",
            arguments={
                "suspect_id": "maid",
                "image_location": "water_boat_beside_zhuyun_tower",
                "motive": "family_medical_cost_and_freedom",
                "self_is_culprit": actor == "maid",
                "task_claims": {"review": f"{actor} 的固定任务复盘。"},
            },
        ))
    return tuple(turns)


TURNS = _build_turns()


def execute(client: ScriptedLLMClient, workspace: Path) -> FullGameExecution:
    environment = HaishanXianguanEnvironment(
        traces_root=workspace / "traces",
        room_data_root=workspace / "rooms",
    )
    result = environment.run(
        task=Task("完成《海山仙馆之寻》正常流程固定推演"),
        llm=client,
        model="scripted",
    )
    return FullGameExecution(result=result, environment=environment)


def verify(
    execution: FullGameExecution,
    client: ScriptedLLMClient,
    _workspace: Path,
) -> None:
    result = execution.result
    environment = execution.environment
    assert result.status == "completed", result.error
    assert result.error is None
    assert environment.active_session is not None
    state = environment.active_session.state
    assert state.phase is GamePhase.FINISHED
    assert state.is_terminal
    assert len(state.introductions) == len(ROLE_ORDER)
    assert len(state.votes) == len(ROLE_ORDER)
    assert len(state.consumed_action_ids) == len(TURNS)
    assert state.collective_result == {
        "success": True,
        "leaders": ["maid"],
        "reason": "unique_correct",
    }
    assert client.consumed == len(TURNS)

    trace_data = environment.session.trace.session_data(result.session_id)
    assert trace_data["status"] == "completed"
    public_messages = environment.active_session.rooms["public"].history()
    private_messages = environment.active_session.rooms["private:maid"].history()
    assert any("winner_ids" in message.txt for message in public_messages)
    assert any("04_侍女剧本.md" in message.txt for message in private_messages)
    assert all("04_侍女剧本.md" not in message.txt for message in public_messages)


def main() -> int:
    result = ScenarioRunner.run(
        name="jubensha_haishanxianguan/full_game",
        turns=TURNS,
        execute=execute,
        verify=verify,
    )
    print(f"PASS {result.name}: {result.turn_count}/{len(TURNS)} scripted turns consumed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
