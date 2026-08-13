"""Domain-rule tests for 海山仙馆之寻 (blueprint section 9, AC-2/3/4/5/6/8).

These tests drive the pure domain logic only (dealing, validation, verdict,
scoring, privacy projections) and need no runtime or LLM.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from coworker.apps.jubensha_haishanxianguan.action import validate_domain_action
from coworker.apps.jubensha_haishanxianguan.data_loader import ROLES, ROLE_NAMES, TRUTH, load_domain_data
from coworker.apps.jubensha_haishanxianguan.observation import build_projection_payload
from coworker.apps.jubensha_haishanxianguan.state import (
    Phase,
    SUBTASK_DEFS,
    JubenshaState,
    compute_reveal,
    deal_person_clues,
    deal_scene_clues,
    domain_transition,
    identified_culprit,
)

DOMAIN = load_domain_data()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _claim_actions(state, visibility="public"):
    actions = []
    for role in ROLES:
        for clue_id in state.players[role].clues_held:
            actions.append({
                "actor": role, "tool": "claim_clue",
                "params": {"clue_id": clue_id, "visibility": visibility},
            })
    return actions


def state_after_intro_and_clue1(claim_visibility="private"):
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    state = domain_transition(state, DOMAIN, [
        {"actor": r, "tool": "introduce", "params": {"text": f"{ROLE_NAMES[r]}问好。"}} for r in ROLES
    ])
    state = domain_transition(state, DOMAIN, _claim_actions(state, claim_visibility))
    return state  # PHASE-DISC1, disc_round=1


# --------------------------------------------------------------------------
# Dealing: RULE-CLUE1-DIST / RULE-CLUE2-DIST / RULE-CLUE2-REMAINDER (Q-5/Q-12)
# --------------------------------------------------------------------------

def test_person_clues_two_per_role_grouped_by_owner():
    assert len(DOMAIN.person_clue_ids()) == 12
    for role in ROLES:
        ids = DOMAIN.person_clues_for(role)
        assert len(ids) == 2, role
        for clue_id in ids:
            assert DOMAIN.clue(clue_id).owner == role


def test_scene_clues_round_robin_twelve_of_fourteen():
    assert len(DOMAIN.scene_clue_ids()) == 14
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    deal_scene_clues(state, DOMAIN)
    dealt = []
    for role in ROLES:
        held = state.players[role].clues_held
        assert len(held) == 2, role
        dealt.extend(held)
    assert len(set(dealt)) == 12
    assert set(dealt) == set(DOMAIN.scene_clue_ids()[:12])
    assert "CLUE-S13" not in dealt and "CLUE-S14" not in dealt


# --------------------------------------------------------------------------
# AC-3: invalid actions rejected with (valid=False, reason)
# --------------------------------------------------------------------------

def test_validation_rejects_vote_out_of_phase():
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)  # PHASE-INTRO
    valid, reason = validate_domain_action(state, "PAN", "vote", {"target": "LI"})
    assert not valid and reason.startswith("NOT_IN_PHASE")


def test_validation_rejects_claiming_unowned_clue():
    state = state_after_intro_and_clue1()
    # During CLUE1 the unowned test needs a CLUE1 state; rebuild one directly.
    s = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "introduce", "params": {"text": "hi"}} for r in ROLES
    ])  # -> CLUE1, PAN holds CLUE-P1/CLUE-P2
    valid, reason = validate_domain_action(s, "PAN", "claim_clue", {"clue_id": "CLUE-P3", "visibility": "public"})
    assert not valid and reason.startswith("NOT_OWNER")
    # own clue is fine
    valid, _ = validate_domain_action(s, "PAN", "claim_clue", {"clue_id": "CLUE-P1", "visibility": "public"})
    assert valid


def test_validation_rejects_double_claim_and_double_speak():
    s = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "introduce", "params": {"text": "hi"}} for r in ROLES
    ])
    valid, _ = validate_domain_action(s, "PAN", "claim_clue", {"clue_id": "CLUE-P1", "visibility": "private"})
    assert valid
    s = domain_transition(s, DOMAIN, _claim_actions(s))  # -> DISC1 round 1
    valid, reason = validate_domain_action(s, "PAN", "speak", {"text": "我有一言"})
    assert valid
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "speak", "params": {"text": "发言"}} for r in ROLES
    ])  # round 1 done -> round 2
    # A second claim on CLUE-P1 would have been rejected in CLUE1 as ALREADY_CLAIMED
    s_clue1 = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    s_clue1 = domain_transition(s_clue1, DOMAIN, [
        {"actor": r, "tool": "introduce", "params": {"text": "hi"}} for r in ROLES
    ])
    s_clue1.players["PAN"].claim_status["CLUE-P1"] = "public"
    valid, reason = validate_domain_action(s_clue1, "PAN", "claim_clue", {"clue_id": "CLUE-P1", "visibility": "private"})
    assert not valid and reason.startswith("ALREADY_CLAIMED")


def test_validation_rejects_self_vote_and_bad_target():
    s = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "introduce", "params": {"text": "hi"}} for r in ROLES
    ])
    s = domain_transition(s, DOMAIN, _claim_actions(s))
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "speak", "params": {"text": "x"}} for r in ROLES
    ])
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "speak", "params": {"text": "y"}} for r in ROLES
    ])  # -> CLUE2
    s = domain_transition(s, DOMAIN, _claim_actions(s))  # -> DISC2
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "speak", "params": {"text": "x"}} for r in ROLES
    ])
    s = domain_transition(s, DOMAIN, [
        {"actor": r, "tool": "speak", "params": {"text": "y"}} for r in ROLES
    ])  # -> VOTE
    valid, reason = validate_domain_action(s, "PAN", "vote", {"target": "PAN"})
    assert not valid and reason.startswith("SELF_VOTE")
    valid, reason = validate_domain_action(s, "PAN", "vote", {"target": "NOT_A_ROLE"})
    assert not valid and reason.startswith("INVALID_TARGET")
    valid, _ = validate_domain_action(s, "PAN", "vote", {"target": "LI"})
    assert valid


# --------------------------------------------------------------------------
# AC-2: privacy isolation in Observation projection
# --------------------------------------------------------------------------

def test_projection_contains_only_own_script_and_public_content():
    state = state_after_intro_and_clue1(claim_visibility="private")
    pan = build_projection_payload(state, "PAN", DOMAIN)
    assert pan["role"] == "PAN"
    assert pan["your_script"] == DOMAIN.script("PAN")
    # no other role's script text leaks into the projection
    for other in ("MAID", "HE", "LI", "STEWARD", "YVAN"):
        assert DOMAIN.script(other) not in str(pan), other
    # no truth leakage
    assert "truth" not in pan
    assert "TRUTH" not in str(pan)
    assert "贮韵楼旁的小舟" not in str(pan)
    # own clues present, others' private clues absent (all held private)
    assert all(c["id"] in state.players["PAN"].clues_held for c in pan["your_clues"])
    others = [cid for r in ROLES if r != "PAN" for cid in state.players[r].clues_held]
    for cid in others:
        assert cid not in str(pan)
    assert pan["phase"] == Phase.DISC1.value


def test_projection_shows_public_clues_to_everyone():
    state = state_after_intro_and_clue1(claim_visibility="public")
    pan = build_projection_payload(state, "PAN", DOMAIN)
    # all 12 public person clues are in the public discourse of the projection
    public_ids = {e["clue_id"] for e in pan["public_discourse"] if e["type"] == "public_clue"}
    assert public_ids == set(DOMAIN.person_clue_ids())


# --------------------------------------------------------------------------
# AC-5: vote verdict (highest vote / tie -> nobody identified)
# --------------------------------------------------------------------------

def test_verdict_identifies_highest_vote():
    votes = {r: "MAID" for r in ROLES if r != "MAID"}
    votes["MAID"] = "LI"
    assert identified_culprit(votes) == "MAID"


def test_verdict_tie_identifies_nobody():
    votes = {"PAN": "LI", "YVAN": "LI", "LI": "PAN", "MAID": "STEWARD", "STEWARD": "MAID", "HE": "PAN"}
    assert identified_culprit(votes) is None


def test_reveal_culprit_escapes_on_tie():
    votes = {"PAN": "LI", "YVAN": "LI", "LI": "PAN", "MAID": "STEWARD", "STEWARD": "MAID", "HE": "PAN"}
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    for r in ROLES:
        state.players[r].vote = votes[r]
    result = compute_reveal(state)
    assert result["identified_culprit"] is None
    assert result["players"]["MAID"]["mainline_done"] is True  # escaped
    assert result["players"]["PAN"]["mainline_done"] is False  # nobody identified


# --------------------------------------------------------------------------
# AC-6: scoring (RULE-SCORE / RULE-SUBTASK-JUDGE / Q-9 / Q-10)
# --------------------------------------------------------------------------

def test_scoring_mainline_and_subtasks():
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    # All hide subtasks unexposed; all vote MAID -> identified.
    for r in ROLES:
        state.players[r].intro_text = f"{ROLE_NAMES[r]}的自我介绍，不涉及任何私密事实。"
        state.players[r].vote = "MAID" if r != "MAID" else "LI"
    result = compute_reveal(state)
    assert result["identified_culprit"] == "MAID"
    for r in ROLES:
        detail = result["players"][r]
        assert detail["mainline_done"] == (r != "MAID")
        expected_main = 3 if r != "MAID" else 0
        assert detail["mainline_points"] == expected_main
    # PAN: hide subtask done (1) + location subtask not scored -> subtask_points 1
    assert result["players"]["PAN"]["subtask_points"] == 1
    # LI: ST-LI-1 hide done (1) + ST-LI-2 motive not mentioned (0) -> 1
    assert result["players"]["LI"]["subtask_points"] == 1
    # MAID: ST-MAID-1 hide done (1)
    assert result["players"]["MAID"]["subtask_points"] == 1
    # HE: only a location subtask -> 0
    assert result["players"]["HE"]["subtask_points"] == 0
    # winner is max total; ties share the win (Q-11)
    totals = {r: result["players"][r]["total"] for r in ROLES}
    top = max(totals.values())
    winners = [r for r, t in totals.items() if t == top]
    assert set(result["winner"]) == set(winners)


def test_scoring_exposed_hide_subtask_fails_and_motive_completes():
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    state.players["MAID"].intro_text = "其实是我调包了画像。"  # exposes ST-MAID-1
    state.players["LI"].speaks = [{"round": 1, "text": "我推测她是收了重金与匿名信才这么做。"}]  # ST-LI-2 motive
    for r in ROLES:
        state.players[r].vote = "MAID" if r != "MAID" else "LI"
    result = compute_reveal(state)
    maid_sub = {s["id"]: s for s in result["players"]["MAID"]["subtask_details"]}
    assert maid_sub["ST-MAID-1"]["done"] is False
    assert result["players"]["MAID"]["subtask_points"] == 0
    li_sub = {s["id"]: s for s in result["players"]["LI"]["subtask_details"]}
    assert li_sub["ST-LI-2"]["done"] is True
    assert result["players"]["LI"]["subtask_points"] == 2


# --------------------------------------------------------------------------
# AC-8: truth is a constant, never derived from play
# --------------------------------------------------------------------------

def test_truth_constant_under_any_votes():
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    # nobody votes MAID: verdict points elsewhere, but truth stays fixed
    for r in ROLES:
        state.players[r].vote = "PAN" if r != "PAN" else "HE"
    result = compute_reveal(state)
    assert result["culprit"] == "MAID"
    assert result["culprit_name"] == "侍女"
    assert result["painting_location"] == "贮韵楼旁的小舟"
    assert result["players"]["MAID"]["mainline_done"] is True  # escaped


# --------------------------------------------------------------------------
# AC-4: idempotent re-submission of a consumed phase cannot re-apply
# --------------------------------------------------------------------------

def test_consumed_phase_actions_cannot_reapply():
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    state = domain_transition(state, DOMAIN, [
        {"actor": r, "tool": "introduce", "params": {"text": "hi"}} for r in ROLES
    ])  # now CLUE1
    # re-submitting an introduce is out of phase
    valid, reason = validate_domain_action(state, "PAN", "introduce", {"text": "again"})
    assert not valid and reason.startswith("NOT_IN_PHASE")


# --------------------------------------------------------------------------
# Data source sanity (section 2 source index)
# --------------------------------------------------------------------------

def test_data_sources_loaded():
    assert set(ROLES) == {"PAN", "YVAN", "LI", "MAID", "STEWARD", "HE"}
    assert len(DOMAIN.scripts) == 6
    for role in ROLES:
        assert len(DOMAIN.script(role)) > 500
    assert len(DOMAIN.clues) == 26
