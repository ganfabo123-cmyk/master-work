"""Pure card evaluation and pot settlement rules."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

from .state import PLAYERS, TexasHoldemState


RANK_VALUE = {rank: index for index, rank in enumerate("23456789TJQKA", start=2)}


def evaluate_five(cards: tuple[str, ...]) -> tuple[int, ...]:
    ranks = sorted((RANK_VALUE[card[0]] for card in cards), reverse=True)
    counts = Counter(ranks)
    groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    flush = len({card[1] for card in cards}) == 1
    unique = sorted(set(ranks), reverse=True)
    if 14 in unique:
        unique.append(1)
    straight_high = next((unique[index] for index in range(len(unique) - 4) if unique[index] - unique[index + 4] == 4), 0)
    if flush and straight_high:
        return (8, straight_high)
    if groups[0][0] == 4:
        return (7, groups[0][1], max(rank for rank in ranks if rank != groups[0][1]))
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (6, groups[0][1], groups[1][1])
    if flush:
        return (5, *ranks)
    if straight_high:
        return (4, straight_high)
    if groups[0][0] == 3:
        return (3, groups[0][1], *(rank for rank in ranks if rank != groups[0][1]))
    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if len(pairs) >= 2:
        kicker = max(rank for rank in ranks if rank not in pairs[:2])
        return (2, pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        return (1, pairs[0], *(rank for rank in ranks if rank != pairs[0]))
    return (0, *ranks)


def evaluate_seven(cards: tuple[str, ...]) -> tuple[int, ...]:
    if len(cards) != 7:
        raise ValueError("Texas Hold'em showdown requires seven cards")
    return max(evaluate_five(tuple(choice)) for choice in combinations(cards, 5))


def settle_pots(state: TexasHoldemState) -> dict[str, int]:
    payouts = {player: 0 for player in PLAYERS}
    levels = sorted({amount for amount in state.committed.values() if amount > 0})
    previous = 0
    for level in levels:
        contributors = [player for player in PLAYERS if state.committed[player] >= level]
        amount = (level - previous) * len(contributors)
        eligible = [player for player in contributors if player not in state.folded]
        if eligible:
            scores = {
                player: evaluate_seven((*state.hole_cards[player], *state.community_cards))
                for player in eligible
            }
            best = max(scores.values())
            winners = [player for player in PLAYERS if player in eligible and scores[player] == best]
            share, remainder = divmod(amount, len(winners))
            for index, player in enumerate(winners):
                payouts[player] += share + (1 if index < remainder else 0)
        previous = level
    return payouts
