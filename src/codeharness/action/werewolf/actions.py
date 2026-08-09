"""Werewolf action protocol and phase-local validation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
import json

from ...room.models import RoomMessage
from ...state.werewolf import Phase, Role, WerewolfGameState


class ActionName(StrEnum):
    WOLF_KILL = "wolf_kill"
    INSPECT = "inspect"
    SAVE = "save"
    POISON = "poison"
    VOTE = "vote"
    SHOOT = "shoot"
    SKIP_SHOT = "skip_shot"


@dataclass(frozen=True, slots=True)
class GameAction:
    message_id: str
    actor: str
    action: ActionName
    target: str | None
    round_no: int
    phase: Phase


def encode_action(*, action: ActionName, target: str | None, round_no: int, phase: Phase) -> str:
    return json.dumps(
        {"type": "werewolf.action", "action": action, "target": target, "round": round_no, "phase": phase},
        ensure_ascii=False,
    )


def parse_action(message: RoomMessage) -> GameAction | None:
    if not isinstance(message.txt, str):
        return None
    try:
        payload = json.loads(message.txt)
        if not isinstance(payload, dict) or payload.get("type") != "werewolf.action":
            return None
        target = payload.get("target")
        return GameAction(
            message_id=message.message_id,
            actor=message.name,
            action=ActionName(payload["action"]),
            target=target if isinstance(target, str) else None,
            round_no=int(payload["round"]),
            phase=Phase(payload["phase"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def validate_action(action: GameAction, state: WerewolfGameState) -> str | None:
    if action.message_id in state.consumed_action_ids:
        return "该动作已经结算。"
    hunter_final_action = action.action in {ActionName.SHOOT, ActionName.SKIP_SHOT} and state.hunter_name == action.actor
    if not state.is_alive(action.actor) and not hunter_final_action:
        return "死亡玩家不能行动。"
    if action.round_no != state.round_no or action.phase is not state.phase:
        return "动作不属于当前回合或阶段。"
    role = state.role_of(action.actor)
    target_actions = {ActionName.WOLF_KILL, ActionName.INSPECT, ActionName.POISON, ActionName.VOTE, ActionName.SHOOT}
    if action.action in target_actions and (action.target is None or not state.is_alive(action.target)):
        return "目标必须是存活玩家。"
    if action.action is ActionName.WOLF_KILL:
        if state.phase is not Phase.NIGHT_WOLF_KILL or role is not Role.WOLF:
            return "当前无权发动狼人击杀。"
        if action.target is not None and state.role_of(action.target) is Role.WOLF:
            return "狼人不能击杀狼人。"
    elif action.action is ActionName.INSPECT:
        if state.phase is not Phase.NIGHT_SEER or role is not Role.SEER:
            return "当前无权查验。"
        if action.target == action.actor:
            return "不能查验自己。"
    elif action.action is ActionName.SAVE:
        if state.phase is not Phase.NIGHT_WITCH or role is not Role.WITCH or not state.witch_has_antidote:
            return "当前无权使用解药。"
        if state.wolf_target is None:
            return "今晚无人被狼刀，不能使用解药。"
    elif action.action is ActionName.POISON:
        if state.phase is not Phase.NIGHT_WITCH or role is not Role.WITCH or not state.witch_has_poison:
            return "当前无权使用毒药。"
    elif action.action is ActionName.VOTE:
        if state.phase is not Phase.DAY_VOTE:
            return "当前不是投票阶段。"
        if action.target == action.actor:
            return "不能投票给自己。"
    elif action.action in {ActionName.SHOOT, ActionName.SKIP_SHOT}:
        if state.phase is not Phase.HUNTER_SHOT or role is not Role.HUNTER or state.hunter_name != action.actor:
            return "当前无权发动猎人技能。"
    return None


def latest_valid_actions(messages: tuple[RoomMessage, ...], state: WerewolfGameState) -> tuple[dict[str, GameAction], list[tuple[GameAction, str]]]:
    accepted: dict[str, GameAction] = {}
    rejected: list[tuple[GameAction, str]] = []
    for message in messages:
        action = parse_action(message)
        if action is None:
            continue
        reason = validate_action(action, state)
        if reason is not None:
            rejected.append((action, reason))
            continue
        accepted[action.actor] = action
    return accepted, rejected


def majority_target(actions: dict[str, GameAction], expected: ActionName) -> str | None:
    targets = [action.target for action in actions.values() if action.action is expected and action.target is not None]
    if not targets:
        return None
    counts = Counter(targets)
    highest = max(counts.values())
    winners = [target for target, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else None


def first_action(actions: dict[str, GameAction], expected: ActionName) -> GameAction | None:
    return next((action for action in actions.values() if action.action is expected), None)


def available_actions(state: WerewolfGameState, agent_name: str) -> tuple[ActionName, ...]:
    role = state.role_of(agent_name)
    if state.phase is Phase.NIGHT_WOLF_KILL and role is Role.WOLF:
        return (ActionName.WOLF_KILL,)
    if state.phase is Phase.NIGHT_SEER and role is Role.SEER:
        return (ActionName.INSPECT,)
    if state.phase is Phase.NIGHT_WITCH and role is Role.WITCH:
        return tuple(action for action, enabled in ((ActionName.SAVE, state.witch_has_antidote), (ActionName.POISON, state.witch_has_poison)) if enabled)
    if state.phase is Phase.DAY_VOTE:
        return (ActionName.VOTE,)
    if state.phase is Phase.HUNTER_SHOT and agent_name == state.hunter_name:
        return (ActionName.SHOOT, ActionName.SKIP_SHOT)
    return ()
