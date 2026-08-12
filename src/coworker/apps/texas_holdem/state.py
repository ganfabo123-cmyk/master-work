"""Serializable state for one deterministic four-player Texas Hold'em hand."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ...core.base_state import State
from ...infra import DeterministicRandomSource


PLAYERS = tuple(f"player-{index}" for index in range(1, 5))
STARTING_STACK = 100
SMALL_BLIND = 5
BIG_BLIND = 10


class PokerPhase(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    FINISHED = "finished"


def standard_deck() -> tuple[str, ...]:
    return tuple(f"{rank}{suit}" for rank in "23456789TJQKA" for suit in "cdhs")


@dataclass
class TexasHoldemState(State):
    seed: int = 0
    phase: PokerPhase = PokerPhase.PREFLOP
    deck: tuple[str, ...] = ()
    deck_index: int = 0
    hole_cards: dict[str, tuple[str, str]] = field(default_factory=dict)
    community_cards: list[str] = field(default_factory=list)
    stacks: dict[str, int] = field(default_factory=dict)
    street_bets: dict[str, int] = field(default_factory=dict)
    committed: dict[str, int] = field(default_factory=dict)
    folded: set[str] = field(default_factory=set)
    all_in: set[str] = field(default_factory=set)
    raise_locked: set[str] = field(default_factory=set)
    pending_players: set[str] = field(default_factory=set)
    current_actor: str | None = None
    current_bet: int = BIG_BLIND
    minimum_raise: int = BIG_BLIND
    consumed_action_ids: set[str] = field(default_factory=set)
    payouts: dict[str, int] = field(default_factory=dict)
    winners: tuple[str, ...] = ()
    ending_report: str = ""

    @classmethod
    def initial(cls, task_id: str, session_id: str) -> "TexasHoldemState":
        return cls.create_hand(task_id, session_id, seed=0)

    @classmethod
    def create_hand(cls, task_id: str, session_id: str, *, seed: int) -> "TexasHoldemState":
        deck = DeterministicRandomSource(seed).shuffled(standard_deck())
        hole_cards = {
            player: (deck[index], deck[index + len(PLAYERS)])
            for index, player in enumerate(PLAYERS)
        }
        stacks = {player: STARTING_STACK for player in PLAYERS}
        street_bets = {player: 0 for player in PLAYERS}
        committed = {player: 0 for player in PLAYERS}
        for player, blind in (("player-2", SMALL_BLIND), ("player-3", BIG_BLIND)):
            stacks[player] -= blind
            street_bets[player] = blind
            committed[player] = blind
        return cls(
            task_id=task_id, session_id=session_id, seed=seed, deck=deck,
            deck_index=len(PLAYERS) * 2, hole_cards=hole_cards,
            stacks=stacks, street_bets=street_bets, committed=committed,
            pending_players=set(PLAYERS), current_actor="player-4",
        )

    @property
    def is_terminal(self) -> bool:
        return self.phase is PokerPhase.FINISHED

    @property
    def pot(self) -> int:
        return sum(self.committed.values())

    def active_players(self) -> tuple[str, ...]:
        return tuple(player for player in PLAYERS if player not in self.folded)

    def actionable_players(self) -> tuple[str, ...]:
        return tuple(player for player in self.active_players() if player not in self.all_in)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id, "session_id": self.session_id, "seed": self.seed,
            "phase": self.phase.value, "deck": list(self.deck), "deck_index": self.deck_index,
            "hole_cards": {key: list(value) for key, value in self.hole_cards.items()},
            "community_cards": list(self.community_cards), "stacks": dict(self.stacks),
            "street_bets": dict(self.street_bets), "committed": dict(self.committed),
            "folded": sorted(self.folded), "all_in": sorted(self.all_in),
            "raise_locked": sorted(self.raise_locked),
            "pending_players": sorted(self.pending_players), "current_actor": self.current_actor,
            "current_bet": self.current_bet, "minimum_raise": self.minimum_raise,
            "consumed_action_ids": sorted(self.consumed_action_ids), "payouts": dict(self.payouts),
            "winners": list(self.winners), "ending_report": self.ending_report,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TexasHoldemState":
        return cls(
            task_id=str(data["task_id"]), session_id=str(data["session_id"]), seed=int(data.get("seed", 0)),
            phase=PokerPhase(str(data.get("phase", PokerPhase.PREFLOP.value))),
            deck=tuple(str(card) for card in data.get("deck", [])), deck_index=int(data.get("deck_index", 0)),
            hole_cards={str(k): tuple(str(card) for card in v) for k, v in dict(data.get("hole_cards") or {}).items()},
            community_cards=[str(card) for card in data.get("community_cards", [])],
            stacks={str(k): int(v) for k, v in dict(data.get("stacks") or {}).items()},
            street_bets={str(k): int(v) for k, v in dict(data.get("street_bets") or {}).items()},
            committed={str(k): int(v) for k, v in dict(data.get("committed") or {}).items()},
            folded={str(item) for item in data.get("folded", [])}, all_in={str(item) for item in data.get("all_in", [])},
            raise_locked={str(item) for item in data.get("raise_locked", [])},
            pending_players={str(item) for item in data.get("pending_players", [])},
            current_actor=None if data.get("current_actor") is None else str(data["current_actor"]),
            current_bet=int(data.get("current_bet", 0)), minimum_raise=int(data.get("minimum_raise", BIG_BLIND)),
            consumed_action_ids={str(item) for item in data.get("consumed_action_ids", [])},
            payouts={str(k): int(v) for k, v in dict(data.get("payouts") or {}).items()},
            winners=tuple(str(item) for item in data.get("winners", [])), ending_report=str(data.get("ending_report", "")),
        )
