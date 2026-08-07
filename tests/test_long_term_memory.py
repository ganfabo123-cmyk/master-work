from __future__ import annotations

from datetime import datetime
from pathlib import Path

from codeharness.memory import LongTermMemoryEntry, LongTermMemoryManager


def _entry(name: str = "首日发言不足以定罪") -> LongTermMemoryEntry:
    return LongTermMemoryEntry(
        experience_name=name,
        happened_at=datetime(2026, 8, 7, 14, 30),
        thing_done="在首日依据一段公开发言指控玩家",
        outcome="失败",
        feedback_basis="最终结局显示该玩家不是狼人",
        approach="我把单次发言风格当成了决定性证据。",
        reason_and_principle="首日信息稀少，单一行为只能形成低置信假设，应等待交叉验证。",
    )


def test_memory_is_persisted_per_agent_and_keeps_the_experience_template(tmp_path: Path) -> None:
    manager = LongTermMemoryManager(tmp_path / "memory")
    player_one = manager.for_agent("player-1")
    player_two = manager.for_agent("player-2")
    player_one.add(_entry())

    restored = LongTermMemoryManager(tmp_path / "memory").for_agent("player-1")
    entry = restored.get("首日发言不足以定罪")

    assert entry is not None
    assert "经验名称：首日发言不足以定罪" in entry.render()
    assert "在 2026-08-07 14:30，我做了" in entry.render()
    assert "为什么我成功/失败，我认为原因是：" in entry.render()
    assert player_two.list() == ()
    assert player_one.path.exists()
    assert player_two.path.exists()


def test_memory_rejects_duplicate_names_within_one_agent_only(tmp_path: Path) -> None:
    manager = LongTermMemoryManager(tmp_path / "memory")
    player_one = manager.for_agent("player-1")
    player_two = manager.for_agent("player-2")
    player_one.add(_entry())

    try:
        player_one.add(_entry())
    except ValueError as error:
        assert "duplicate experience_name" in str(error)
    else:
        raise AssertionError("same Agent must not accept duplicate experience names")

    player_two.add(_entry())
    assert player_two.get("首日发言不足以定罪") is not None
