"""Shared implementations used by Agent-callable tool methods.

Nothing in this module is registered as a model tool.  Agent tool classes call
these functions after their own ``self.agent_name`` and input validation have
already established the caller and public tool contract.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Callable

from pydantic import Field

from ..room import Room, RoomMessage
from ..util.werewolf_actions import ActionName, encode_action
from ..util.werewolf_state import Phase, Role, WerewolfGameState


# Markdown knowledge retrieval -------------------------------------------------

def knowledge_terms(text: str) -> set[str]:
    """Extract lightweight English and Chinese lookup terms from one query."""
    words = {word.lower() for word in re.findall(r"[A-Za-z0-9_]{2,}", text)}
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        words.add(phrase)
        words.update(phrase[index:index + 2] for index in range(len(phrase) - 1))
    return words


def search_markdown(query: str, root: Path, *, no_match: str) -> str:
    """Search Markdown files below one supplied knowledge root."""
    query_terms = knowledge_terms(query)
    scored: list[tuple[int, Path, str]] = []
    for path in root.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        score = len(query_terms & knowledge_terms(text))
        if score:
            scored.append((score, path, text))
    if not scored:
        return no_match
    return "\n\n".join(f"# Source: {path.name}\n\n{text}" for _, path, text in sorted(scored, reverse=True)[:3])


# Werewolf action construction --------------------------------------------------

def available_werewolf_actions(state: WerewolfGameState, agent_name: str) -> tuple[ActionName, ...]:
    """Return phase-legal actions for one player without exposing game helpers."""
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


def require_werewolf_thought(has_thought: bool) -> None:
    """Reject game communication and action before the private-thought gate."""
    if not has_thought:
        raise ValueError("请先调用 think(strategy) 完成私密思考，再发送 ROOM 消息或提交游戏动作。")


def send_wolf_message(room: Room, wolf_room: Room | None, state: WerewolfGameState, agent_name: str, content: str, has_thought: bool) -> str:
    """Publish one private wolf discussion message after the thought gate."""
    require_werewolf_thought(has_thought)
    (wolf_room or room).send(RoomMessage(name=agent_name, at=state.alive_wolves(), txt=content))
    return "狼队私聊已发送。"


def send_public_werewolf_message(room: Room, agent_name: str, content: str, has_thought: bool) -> str:
    """Publish one public werewolf discussion message after the thought gate."""
    require_werewolf_thought(has_thought)
    room.send(RoomMessage(name=agent_name, at="all", txt=content))
    return "公开发言已发送。"


def build_werewolf_action_tool(
    room: Room,
    agent_name: str,
    state: WerewolfGameState,
    action: ActionName,
    has_thought: Callable[[], bool],
) -> Callable[..., str]:
    """Build one phase-specific, model-callable action function for a player."""
    if action in {ActionName.SAVE, ActionName.SKIP_SHOT}:
        def submit() -> str:
            """提交无需目标的游戏动作。"""
            require_werewolf_thought(has_thought())
            room.send(RoomMessage(name=agent_name, at="game-engine", txt=encode_action(action=action, target=None, round_no=state.round_no, phase=state.phase)))
            return "动作已提交给规则引擎。"
    else:
        def submit(
            target: Annotated[str, Field(description="目标玩家名称，例如 player-3；必须是存活且合法的玩家。")],
        ) -> str:
            """提交一个有目标的游戏动作。"""
            require_werewolf_thought(has_thought())
            room.send(RoomMessage(name=agent_name, at="game-engine", txt=encode_action(action=action, target=target, round_no=state.round_no, phase=state.phase)))
            return "动作已提交给规则引擎。"
    submit.__name__ = action.value
    return submit
