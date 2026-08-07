"""Pure deterministic resolution for the werewolf game."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .werewolf_actions import ActionName, GameAction
from .werewolf_state import Death, Phase, Role, WerewolfGameState, Winner


@dataclass(frozen=True, slots=True)
class GameEvent:
    text: str
    recipient: str = "all"
    private: bool = False


def resolve_phase(state: WerewolfGameState, actions: dict[str, GameAction]) -> tuple[WerewolfGameState, tuple[GameEvent, ...]]:
    events: list[GameEvent] = []
    if state.phase is Phase.NIGHT_WOLF_DISCUSSION:
        state.phase = Phase.NIGHT_WOLF_KILL
        return state, (GameEvent("狼人请提交今晚的击杀目标。"),)
    if state.phase is Phase.NIGHT_WOLF_KILL:
        state.wolf_target = _majority_target(actions, ActionName.WOLF_KILL)
        state.phase = Phase.NIGHT_SEER
        events.append(GameEvent("狼人行动结束，预言家请查验。"))
    elif state.phase is Phase.NIGHT_SEER:
        inspection = _first_action(actions, ActionName.INSPECT)
        if inspection is not None and inspection.target is not None:
            identity = "狼人" if state.role_of(inspection.target) is Role.WOLF else "好人"
            events.append(GameEvent(f"查验结果：{inspection.target} 是{identity}。", inspection.actor, True))
        state.phase = Phase.NIGHT_WITCH
        events.append(GameEvent("预言家行动结束，女巫请行动。"))
    elif state.phase is Phase.NIGHT_WITCH:
        state, night_events = _resolve_witch_and_night(state, actions)
        events.extend(night_events)
    elif state.phase is Phase.DAY_DISCUSSION:
        state.phase = Phase.DAY_VOTE
        events.append(GameEvent("讨论结束，请所有存活玩家投票。"))
    elif state.phase is Phase.DAY_VOTE:
        target = _majority_target(actions, ActionName.VOTE)
        if target is None:
            events.append(GameEvent("投票平票或无人投票，今日无人出局。"))
            _begin_next_night(state)
        else:
            death = Death(target, "vote")
            _kill(state, death)
            events.append(GameEvent(f"投票结果：{target} 出局。"))
            _after_deaths(state, [death], Phase.NIGHT_WOLF_DISCUSSION, events)
    elif state.phase is Phase.HUNTER_SHOT:
        shot = _first_action(actions, ActionName.SHOOT)
        if shot is not None and shot.target is not None:
            death = Death(shot.target, "hunter_shot")
            _kill(state, death)
            events.append(GameEvent(f"猎人带走了 {shot.target}。"))
        else:
            events.append(GameEvent("猎人未开枪。"))
        next_phase = state.continue_phase or Phase.NIGHT_WOLF_DISCUSSION
        state.hunter_name = None
        state.continue_phase = None
        _after_deaths(state, [], next_phase, events)
    _check_winner(state, events)
    return state, tuple(events)


def finish_as_draw(state: WerewolfGameState) -> tuple[WerewolfGameState, tuple[GameEvent, ...]]:
    state.winner = Winner.DRAW
    state.phase = Phase.REVIEW
    return state, (GameEvent("游戏因达到最大回合数而平局结束。"), *_review_events(state))


def _resolve_witch_and_night(state: WerewolfGameState, actions: dict[str, GameAction]) -> tuple[WerewolfGameState, list[GameEvent]]:
    events: list[GameEvent] = []
    witch_actions = [action for action in actions.values() if action.action in {ActionName.SAVE, ActionName.POISON}]
    used_save = any(action.action is ActionName.SAVE for action in witch_actions)
    poison = next((action for action in witch_actions if action.action is ActionName.POISON), None)
    if used_save:
        state.witch_has_antidote = False
    deaths: list[Death] = []
    if state.wolf_target is not None and not used_save:
        deaths.append(Death(state.wolf_target, "wolf_kill"))
    if poison is not None and poison.target is not None:
        state.witch_has_poison = False
        if poison.target not in {death.player for death in deaths}:
            deaths.append(Death(poison.target, "witch_poison"))
    state.wolf_target = None
    for death in deaths:
        _kill(state, death)
    if deaths:
        events.append(GameEvent("天亮了，昨夜有人死亡。"))
    else:
        events.append(GameEvent("天亮了，昨夜平安无事。"))
    _after_deaths(state, deaths, Phase.DAY_DISCUSSION, events)
    return state, events


def _after_deaths(state: WerewolfGameState, deaths: list[Death], next_phase: Phase, events: list[GameEvent]) -> None:
    hunter_death = next((death for death in deaths if state.role_of(death.player) is Role.HUNTER and death.cause != "witch_poison"), None)
    if hunter_death is not None:
        state.hunter_name = hunter_death.player
        state.continue_phase = next_phase
        state.phase = Phase.HUNTER_SHOT
        events.append(GameEvent("猎人请决定是否开枪。", hunter_death.player, True))
        return
    state.phase = next_phase
    if next_phase is Phase.NIGHT_WOLF_DISCUSSION:
        _begin_next_night(state)


def _begin_next_night(state: WerewolfGameState) -> None:
    state.round_no += 1
    state.phase = Phase.NIGHT_WOLF_DISCUSSION


def _kill(state: WerewolfGameState, death: Death) -> None:
    if death.player in state.players:
        state.players[death.player].alive = False


def _check_winner(state: WerewolfGameState, events: list[GameEvent]) -> None:
    if not state.alive_wolves():
        state.winner = Winner.VILLAGERS
    elif len(state.alive_wolves()) >= len(state.alive_players()) - len(state.alive_wolves()):
        state.winner = Winner.WOLVES
    if state.winner is not None:
        state.phase = Phase.REVIEW
        label = "好人阵营" if state.winner is Winner.VILLAGERS else "狼人阵营"
        events.append(GameEvent(f"游戏结束：{label} 获胜。"))
        events.extend(_review_events(state))


def _review_events(state: WerewolfGameState) -> tuple[GameEvent, ...]:
    identities = "\n".join(f"- {name}：{_role_label(player.role)}" for name, player in state.players.items())
    winner_label = {
        Winner.WOLVES: "狼人阵营获胜",
        Winner.VILLAGERS: "好人阵营获胜",
        Winner.DRAW: "本局平局",
    }[state.winner]
    events: list[GameEvent] = []
    for name, player in state.players.items():
        if state.winner is Winner.DRAW:
            outcome = "平局"
        elif (state.winner is Winner.WOLVES) is (player.role is Role.WOLF):
            outcome = "胜利"
        else:
            outcome = "失败"
        events.append(
            GameEvent(
                f"本局结算：{winner_label}。\n\n全部玩家身份：\n{identities}\n\n你的本局结果：{outcome}。\n请调用 save_experience 完成本局复盘，然后直接结束本回合。",
                name,
                True,
            )
        )
    return tuple(events)


def _role_label(role: Role) -> str:
    return {
        Role.WOLF: "狼人",
        Role.SEER: "预言家",
        Role.WITCH: "女巫",
        Role.HUNTER: "猎人",
        Role.VILLAGER: "村民",
    }[role]


def _majority_target(actions: dict[str, GameAction], expected: ActionName) -> str | None:
    targets = [action.target for action in actions.values() if action.action is expected and action.target is not None]
    if not targets:
        return None
    counts = Counter(targets)
    highest = max(counts.values())
    winners = [target for target, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else None


def _first_action(actions: dict[str, GameAction], expected: ActionName) -> GameAction | None:
    return next((action for action in actions.values() if action.action is expected), None)
