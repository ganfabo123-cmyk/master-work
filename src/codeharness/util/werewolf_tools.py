"""Context-bound werewolf tools.  They publish intent; rules resolve it later."""

from __future__ import annotations

from typing import Annotated, Callable

from pydantic import Field

from ..room import Room, RoomMessage
from ..tools import ToolRegistry
from .werewolf_actions import ActionName, encode_action
from .werewolf_state import Phase, Role, WerewolfGameState


def tools_for_player(
    *,
    room: Room,
    actor: str,
    state: WerewolfGameState,
    wolf_room: Room | None = None,
) -> tuple[ToolRegistry, tuple[Callable[..., str], ...]]:
    """Build the exact tools one player may call in the current phase."""
    registry = ToolRegistry()
    tools: list[Callable[..., str]] = []
    has_thought = False

    def register(name: str, function: Callable[..., str], description: str) -> None:
        function.__name__ = name
        function.__doc__ = description
        registry.register(function)
        tools.append(function)

    def think(
        strategy: Annotated[str, Field(description="本回合的私密策略推理，包括线索、风险和下一步行动依据；不会发送到 ROOM。")],
    ) -> str:
        """记录本回合的私密思考；必须先调用，之后才能发送 ROOM 消息或提交游戏动作。"""
        nonlocal has_thought
        has_thought = True
        return "思考已记录。现在可以调用公开发言、私聊或游戏动作工具。"

    register("think", think, "记录本回合私密思考；必须先调用，之后才能发送 ROOM 消息或提交游戏动作。")

    def require_thought() -> None:
        if not has_thought:
            raise ValueError("请先调用 think(strategy) 完成私密思考，再发送 ROOM 消息或提交游戏动作。")

    if state.phase is Phase.NIGHT_WOLF_DISCUSSION and state.role_of(actor) is Role.WOLF:
        recipients = state.alive_wolves()

        def wolf_message(
            content: Annotated[str, Field(description="发给全部存活狼队友的私下协商内容。")],
        ) -> str:
            """向全部存活狼人发送私下协商消息。"""
            require_thought()
            (wolf_room or room).send(RoomMessage(name=actor, at=recipients, txt=content))
            return "狼队私聊已发送。"

        register("wolf_message", wolf_message, "向全部存活狼人发送私下协商消息。")

    for action in _phase_actions_for(state, actor):
        if action in {ActionName.SAVE, ActionName.SKIP_SHOT}:
            register(action.value, _no_target_action(room, actor, state, action, require_thought), "提交当前阶段的无目标动作给规则引擎。")
        else:
            register(action.value, _target_action(room, actor, state, action, require_thought), "提交当前阶段的目标动作给规则引擎。")

    if state.phase is Phase.DAY_DISCUSSION:

        def speak(
            content: Annotated[str, Field(description="公开发言内容，应基于当前可见线索进行推理。")],
        ) -> str:
            """向全体玩家公开发言。"""
            require_thought()
            room.send(RoomMessage(name=actor, at="all", txt=content))
            return "公开发言已发送。"

        register("speak", speak, "向全体玩家公开发言。")
    return registry, tuple(tools)


def _phase_actions_for(state: WerewolfGameState, actor: str) -> tuple[ActionName, ...]:
    role = state.role_of(actor)
    if state.phase is Phase.NIGHT_WOLF_KILL and role is Role.WOLF:
        return (ActionName.WOLF_KILL,)
    if state.phase is Phase.NIGHT_SEER and role is Role.SEER:
        return (ActionName.INSPECT,)
    if state.phase is Phase.NIGHT_WITCH and role is Role.WITCH:
        actions: list[ActionName] = []
        if state.witch_has_antidote:
            actions.append(ActionName.SAVE)
        if state.witch_has_poison:
            actions.append(ActionName.POISON)
        return tuple(actions)
    if state.phase is Phase.DAY_VOTE:
        return (ActionName.VOTE,)
    if state.phase is Phase.HUNTER_SHOT and actor == state.hunter_name:
        return (ActionName.SHOOT, ActionName.SKIP_SHOT)
    return ()


def _no_target_action(
    room: Room,
    actor: str,
    state: WerewolfGameState,
    action: ActionName,
    require_thought: Callable[[], None],
) -> Callable[..., str]:
    def submit() -> str:
        """提交无需目标的游戏动作。"""
        require_thought()
        room.send(RoomMessage(name=actor, at="game-engine", txt=encode_action(action=action, target=None, round_no=state.round_no, phase=state.phase)))
        return "动作已提交给规则引擎。"

    return submit


def _target_action(
    room: Room,
    actor: str,
    state: WerewolfGameState,
    action: ActionName,
    require_thought: Callable[[], None],
) -> Callable[..., str]:
    def submit(
        target: Annotated[str, Field(description="目标玩家名称，例如 player-3；必须是存活且合法的玩家。")],
    ) -> str:
        """提交一个有目标的游戏动作。"""
        require_thought()
        room.send(RoomMessage(name=actor, at="game-engine", txt=encode_action(action=action, target=target, round_no=state.round_no, phase=state.phase)))
        return "动作已提交给规则引擎。"

    return submit
