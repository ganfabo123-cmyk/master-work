"""Workflow tests for 海山仙馆之寻 (blueprint section 9, AC-1 and AC-7).

AC-1 drives the deterministic transition chain end-to-end; AC-7 checks that a
persisted State round-trips and resumes at the same phase boundary.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from coworker.apps.jubensha_haishanxianguan.data_loader import ROLES, ROLE_NAMES, load_domain_data
from coworker.apps.jubensha_haishanxianguan.state import Phase, JubenshaState, domain_transition

DOMAIN = load_domain_data()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _advance_intro(state, intros=None):
    return domain_transition(state, DOMAIN, [
        {"actor": r, "tool": "introduce",
         "params": {"text": (intros or {}).get(r, f"{ROLE_NAMES[r]}向大家问好。")}}
        for r in ROLES
    ])


def _advance_claims(state, visibility="public"):
    actions = []
    for role in ROLES:
        for clue_id in state.players[role].clues_held:
            actions.append({
                "actor": role, "tool": "claim_clue",
                "params": {"clue_id": clue_id, "visibility": visibility},
            })
    return domain_transition(state, DOMAIN, actions)


def _advance_disc(state, phase, texts=None):
    for _ in range(2):  # two fixed rounds (RULE-DISC-TURNS)
        actions = [
            {"actor": r, "tool": "speak",
             "params": {"text": (texts or {}).get(r, f"{ROLE_NAMES[r]}正在发言。")}}
            for r in ROLES
        ]
        state = domain_transition(state, DOMAIN, actions)
        assert state.current_phase == phase or (phase == Phase.DISC1 and state.current_phase == Phase.CLUE2) \
            or (phase == Phase.DISC2 and state.current_phase == Phase.VOTE)
    return state


def play_full_game(*, votes=None, claim_visibility="public", intros=None, speaks=None):
    """Deterministic full playthrough driving domain_transition directly."""
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    assert state.current_phase == Phase.INTRO

    state = _advance_intro(state, intros)
    assert state.current_phase == Phase.CLUE1
    assert all(len(state.players[r].clues_held) == 2 for r in ROLES)

    state = _advance_claims(state, claim_visibility)
    assert state.current_phase == Phase.DISC1 and state.disc_round == 1

    state = _advance_disc(state, Phase.DISC1, speaks)
    assert state.current_phase == Phase.CLUE2
    assert all(len(state.players[r].clues_held) == 2 for r in ROLES)

    state = _advance_claims(state, claim_visibility)
    assert state.current_phase == Phase.DISC2 and state.disc_round == 1

    state = _advance_disc(state, Phase.DISC2, speaks)
    assert state.current_phase == Phase.VOTE

    resolved_votes = votes or {r: ("MAID" if r != "MAID" else "LI") for r in ROLES}
    state = domain_transition(state, DOMAIN, [
        {"actor": r, "tool": "vote", "params": {"target": resolved_votes[r]}} for r in ROLES
    ])
    assert state.current_phase == Phase.REVEAL

    state = domain_transition(state, DOMAIN, [])
    assert state.current_phase == Phase.TERMINAL
    return state


# --------------------------------------------------------------------------
# AC-1: complete normal flow to TERMINAL with a full result
# --------------------------------------------------------------------------

def test_ac1_full_flow_reaches_terminal_with_complete_result():
    state = play_full_game()

    assert state.is_terminal
    assert state.terminal_result is not None
    result = state.terminal_result

    # truth constants (AC-8)
    assert result["culprit"] == "MAID"
    assert result["painting_location"] == "贮韵楼旁的小舟"
    # identified by the scripted votes
    assert result["identified_culprit"] == "MAID"
    # every role scored with breakdown
    assert set(result["players"].keys()) == set(ROLES)
    for r in ROLES:
        detail = result["players"][r]
        assert detail["mainline_points"] in (0, 3)
        assert detail["subtask_points"] >= 0
        assert detail["total"] == detail["mainline_points"] + detail["subtask_points"]
    # votes recorded
    assert set(result["votes"].keys()) == set(ROLES)
    # winners non-empty, each marked is_winner
    assert result["winner"], "at least one winner"
    for r in ROLES:
        assert result["players"][r]["is_winner"] == (r in result["winner"])


def test_ac1_public_discourse_accumulates_all_phases():
    state = play_full_game()
    types = {entry["type"] for entry in state.public_discourse}
    assert {"intro", "speak"} <= types
    # 6 intros + 6*4 speaks (2 rounds x 2 discussion phases) = 30 non-clue entries
    intros = [e for e in state.public_discourse if e["type"] == "intro"]
    speaks = [e for e in state.public_discourse if e["type"] == "speak"]
    assert len(intros) == 6
    assert len(speaks) == 6 * 4


def test_ac1_private_claims_stay_out_of_public_discourse():
    state = play_full_game(claim_visibility="private")
    # every held clue was claimed private -> nothing public
    public_clues = [e for e in state.public_discourse if e["type"] == "public_clue"]
    assert public_clues == []
    # each player recorded claim decisions for both clue rounds (2 person + 2 scene)
    for r in ROLES:
        assert len(state.players[r].claim_status) == 4
        assert all(v == "private" for v in state.players[r].claim_status.values())


def test_ac1_phase_sequence_is_exactly_ordered():
    state = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    order = []
    # walk phase by phase, recording current_phase after each collected batch
    state = _advance_intro(state)
    order.append(state.current_phase)
    state = _advance_claims(state)
    order.append(state.current_phase)
    state = _advance_disc(state, Phase.DISC1)
    order.append(state.current_phase)
    state = _advance_claims(state)
    order.append(state.current_phase)
    state = _advance_disc(state, Phase.DISC2)
    order.append(state.current_phase)
    votes = {r: ("MAID" if r != "MAID" else "LI") for r in ROLES}
    state = domain_transition(state, DOMAIN, [
        {"actor": r, "tool": "vote", "params": {"target": votes[r]}} for r in ROLES
    ])
    order.append(state.current_phase)
    state = domain_transition(state, DOMAIN, [])
    order.append(state.current_phase)
    assert [p.value for p in order] == [
        "PHASE-CLUE1", "PHASE-DISC1", "PHASE-CLUE2", "PHASE-DISC2",
        "PHASE-VOTE", "PHASE-REVEAL", "PHASE-TERMINAL",
    ]


# --------------------------------------------------------------------------
# AC-7: phase-boundary recovery via State round-trip
# --------------------------------------------------------------------------

def test_ac7_state_round_trip_preserves_phase_boundary():
    state = play_full_game()

    # restart a fresh play and stop mid-way at the CLUE1 boundary
    mid = JubenshaState.initial("task-1", "sess-1", DOMAIN)
    mid = _advance_intro(mid)
    assert mid.current_phase == Phase.CLUE1

    restored = JubenshaState.from_dict(mid.to_dict())
    assert restored.task_id == mid.task_id
    assert restored.session_id == mid.session_id
    assert restored.current_phase == mid.current_phase
    assert restored.disc_round == mid.disc_round
    assert [restored.players[r].intro_text for r in ROLES] == [mid.players[r].intro_text for r in ROLES]
    assert [restored.players[r].clues_held for r in ROLES] == [mid.players[r].clues_held for r in ROLES]

    # continue from the restored state without loss
    continued = _advance_claims(restored)
    assert continued.current_phase == Phase.DISC1
    assert continued.public_discourse == _advance_claims(mid).public_discourse


def test_ac7_terminal_result_survives_round_trip():
    state = play_full_game()
    restored = JubenshaState.from_dict(state.to_dict())
    assert restored.is_terminal
    assert restored.terminal_result == state.terminal_result
    assert restored.consumed_action_ids == state.consumed_action_ids
