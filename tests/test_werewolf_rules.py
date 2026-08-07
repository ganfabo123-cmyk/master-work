from __future__ import annotations

from collections import Counter
from random import Random

from codeharness.room import RoomMessage
from codeharness.util.werewolf_actions import ActionName, encode_action, latest_valid_actions
from codeharness.util.werewolf_rules import resolve_phase
from codeharness.util.werewolf_state import Phase, WerewolfGameState, Winner


def test_random_game_preserves_classic_role_composition() -> None:
    state = WerewolfGameState.random_eight_players(randomizer=Random(20260806))

    assert tuple(state.players) == tuple(f"player-{number}" for number in range(1, 9))
    assert Counter(player.role.value for player in state.players.values()) == {
        "wolf": 2,
        "seer": 1,
        "witch": 1,
        "hunter": 1,
        "villager": 3,
    }


def _action(actor: str, action: ActionName, target: str | None, state: WerewolfGameState) -> RoomMessage:
    return RoomMessage(
        name=actor,
        at="game-engine",
        txt=encode_action(action=action, target=target, round_no=state.round_no, phase=state.phase),
    )


def test_wolf_vote_is_resolved_deterministically() -> None:
    state = WerewolfGameState.classic_eight_players()
    state.phase = Phase.NIGHT_WOLF_KILL
    messages = (
        _action("player-1", ActionName.WOLF_KILL, "player-3", state),
        _action("player-2", ActionName.WOLF_KILL, "player-3", state),
    )
    actions, rejected = latest_valid_actions(messages, state)

    assert rejected == []
    state, _ = resolve_phase(state, actions)
    assert state.wolf_target == "player-3"
    assert state.phase is Phase.NIGHT_SEER


def test_witch_poisoned_hunter_cannot_open_fire() -> None:
    state = WerewolfGameState.classic_eight_players()
    state.phase = Phase.NIGHT_WITCH
    message = _action("player-4", ActionName.POISON, "player-5", state)
    actions, rejected = latest_valid_actions((message,), state)

    assert rejected == []
    state, _ = resolve_phase(state, actions)
    assert not state.is_alive("player-5")
    assert state.phase is Phase.DAY_DISCUSSION


def test_all_wolves_dead_means_villager_win() -> None:
    state = WerewolfGameState.classic_eight_players()
    state.phase = Phase.DAY_VOTE
    for wolf in ("player-1", "player-2"):
        state.players[wolf].alive = False
    messages = tuple(_action(name, ActionName.VOTE, "player-6", state) for name in state.alive_players())
    actions, _ = latest_valid_actions(messages, state)

    state, _ = resolve_phase(state, actions)
    assert state.winner is Winner.VILLAGERS
    assert state.phase is Phase.FINISHED
