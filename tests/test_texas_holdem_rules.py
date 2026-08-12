from __future__ import annotations

from coworker.apps.texas_holdem.environment import PokerActionPayload, PokerActionValue, TexasHoldemEnvironment
from coworker.apps.texas_holdem.observation import PokerObservation
from coworker.apps.texas_holdem.rules import evaluate_seven, settle_pots
from coworker.apps.texas_holdem.state import TexasHoldemState
from coworker.core.models import Message, ToolCall
from coworker.infra import DeterministicRandomSource
from coworker.infra.room import Room


def test_random_source_and_deal_are_replayable() -> None:
    items = tuple(range(20))
    assert DeterministicRandomSource(17).shuffled(items) == DeterministicRandomSource(17).shuffled(items)
    first = TexasHoldemState.create_hand("task", "one", seed=17)
    second = TexasHoldemState.create_hand("task", "two", seed=17)
    assert first.deck == second.deck
    assert first.hole_cards == second.hole_cards


def test_hand_evaluator_orders_straight_flush_above_four_of_a_kind() -> None:
    straight_flush = evaluate_seven(("Ah", "Kh", "Qh", "Jh", "Th", "2c", "3d"))
    four_kind = evaluate_seven(("As", "Ah", "Ad", "Ac", "Kh", "2c", "3d"))
    assert straight_flush > four_kind


def test_side_pots_follow_committed_levels_and_eligibility() -> None:
    state = TexasHoldemState.create_hand("task", "session", seed=1)
    state.community_cards = ["2c", "3d", "4h", "9s", "Kd"]
    state.hole_cards = {
        "player-1": ("5c", "6c"),  # straight, wins main pot
        "player-2": ("Kh", "Kc"),  # trips, wins side pot
        "player-3": ("Qh", "Qc"),
        "player-4": ("Jh", "Jc"),
    }
    state.committed = {"player-1": 20, "player-2": 50, "player-3": 50, "player-4": 50}

    payouts = settle_pots(state)

    assert payouts == {"player-1": 80, "player-2": 90, "player-3": 0, "player-4": 0}


def test_short_all_in_requires_calls_without_reopening_raise(tmp_path) -> None:
    state = TexasHoldemState.create_hand("task", "session", seed=1)
    state.current_actor = "player-2"
    state.current_bet = 50
    state.minimum_raise = 20
    state.street_bets = {"player-1": 50, "player-2": 40, "player-3": 50, "player-4": 50}
    state.stacks["player-2"] = 15
    state.pending_players = {"player-2"}
    observation = PokerObservation(
        state_message=Message("user", "state"), available_tool_names=("all_in",),
        room=Room("public", session_id="session", data_root=tmp_path), task_id="task", session_id="session",
    )
    action = PokerActionValue("a1", "player-2", "all_in", PokerActionPayload(), ToolCall("call", "all_in", {}), observation)

    TexasHoldemEnvironment._apply_action(object.__new__(TexasHoldemEnvironment), state, action)

    assert state.current_bet == 55
    assert state.pending_players == {"player-1", "player-3", "player-4"}
    assert state.raise_locked == {"player-1", "player-3", "player-4"}
