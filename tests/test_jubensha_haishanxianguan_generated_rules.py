from __future__ import annotations

from coworker.apps.jubensha_haishanxianguan.action import (
    HaishanActionManager,
    HaishanActionPayload,
)
from coworker.apps.jubensha_haishanxianguan.data_loader import HaishanMaterialLoader
from coworker.apps.jubensha_haishanxianguan.observation import build_visible_payload
from coworker.apps.jubensha_haishanxianguan.state import (
    GamePhase,
    HaishanXianguanState,
)
from coworker.core.action_envelope import ActionEnvelope
from coworker.core.base_observation import Observation
from coworker.core.models import ToolCall


def make_action(state: HaishanXianguanState, actor: str, name: str, **arguments: object) -> ActionEnvelope:
    call = ToolCall(id=f"call-{len(state.consumed_action_ids)}", name=name, arguments=arguments)
    return ActionEnvelope(
        action_id=f"{actor}:{call.id}",
        actor=actor,
        name=name,
        payload=HaishanActionPayload(actor, name, arguments),
        tool_call=call,
        observation=Observation("obs", state.task_id, state.session_id),
    )


def test_ac_normal_01_initial_state_round_trip_and_assignments() -> None:
    state = HaishanXianguanState.initial("task", "session")
    restored = HaishanXianguanState.from_dict(state.to_dict())
    assert restored == state
    assert [len(state.person_clue_assignments[role]) for role in state.role_order] == [2] * 6
    assert [len(state.scene_clue_assignments[role]) for role in state.role_order] == [3, 3, 2, 2, 2, 2]
    assert not state.is_terminal


def test_ac_invalid_01_rejects_foreign_clue_with_specific_reason() -> None:
    state = HaishanXianguanState.initial("task", "session")
    state.phase = GamePhase.PERSON_SEARCH
    action = make_action(
        state,
        "pan",
        "handle_clues",
        decisions=[
            {"clue_id": "person-03", "reveal": True},
            {"clue_id": "person-02", "reveal": False},
        ],
    )
    valid, reason = HaishanActionManager().validate_action(action, state)
    assert not valid
    assert "person-03" in reason
    assert "不属于" in reason


def test_ac_invalid_02_and_duplicate_01_have_actionable_reasons() -> None:
    state = HaishanXianguanState.initial("task", "session")
    state.phase = GamePhase.VOTE
    invalid = make_action(
        state,
        "pan",
        "submit_vote",
        suspect_id="outsider",
        image_location="unknown",
        motive="unknown",
        self_is_culprit=False,
        task_claims={},
    )
    valid, reason = HaishanActionManager().validate_action(invalid, state)
    assert not valid and "outsider" in reason
    state.consumed_action_ids.add(invalid.action_id)
    valid, reason = HaishanActionManager().validate_action(invalid, state)
    assert not valid and "已消费" in reason


def test_ac_privacy_01_observation_excludes_other_private_clues() -> None:
    state = HaishanXianguanState.initial("task", "session")
    state.phase = GamePhase.PERSON_SEARCH
    state.revealed_clues.add("person-03")
    payload = build_visible_payload(state, "pan", HaishanMaterialLoader())
    visible = payload["visible_clues"]
    assert "person-01" in visible and "person-02" in visible
    assert "person-03" in visible
    assert "person-04" not in visible
    assert "truth" not in payload


def test_observation_releases_ivan_scene_04_only_in_scene_phase() -> None:
    state = HaishanXianguanState.initial("task", "session")
    loader = HaishanMaterialLoader()

    intro = build_visible_payload(state, "ivan", loader)
    assert intro["visible_clues"] == {}
    assert intro["private_clue_ids"] == []

    state.phase = GamePhase.PERSON_SEARCH
    person_search = build_visible_payload(state, "ivan", loader)
    assert set(person_search["visible_clues"]) == {"person-03", "person-04"}
    assert "scene-04" not in person_search["visible_clues"]
    assert "scene-04" not in person_search["private_clue_ids"]

    state.phase = GamePhase.SCENE_SEARCH
    scene_search = build_visible_payload(state, "ivan", loader)
    assert {"scene-04", "scene-05", "scene-06"}.issubset(
        scene_search["visible_clues"]
    )
    assert {"scene-04", "scene-05", "scene-06"}.issubset(
        scene_search["private_clue_ids"]
    )
    state.handled_clues["pan"].update(state.scene_clue_assignments["pan"])
    scene_action = make_action(
        state,
        "ivan",
        "handle_clues",
        decisions=[
            {"clue_id": clue_id, "reveal": False}
            for clue_id in ("scene-04", "scene-05", "scene-06")
        ],
    )
    valid, reason = HaishanActionManager().validate_action(scene_action, state)
    assert valid, reason


def test_material_loader_preserves_expected_source_cardinality() -> None:
    loader = HaishanMaterialLoader()
    assert len(loader.clues("person")) == 12
    assert len(loader.clues("scene")) == 14
    assert "侍" in loader.truth().content
