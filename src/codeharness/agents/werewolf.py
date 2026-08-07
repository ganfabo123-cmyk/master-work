"""One configurable Agent class for all werewolf players."""

from __future__ import annotations

from pathlib import Path

from .base import Agent, SkillSpec
from ..llm import LLMClient
from ..prompts.werewolf import WerewolfPromptBuilder
from ..room import Room
from ..tools.werewolf_player import WerewolfPlayerTools
from ..util.werewolf_state import Role, WerewolfGameState


_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills" / "werewolf"


class WerewolfPlayerAgent(Agent):
    def __init__(
        self,
        llm: LLMClient,
        model: str,
        *,
        name: str,
        role: Role,
        public_room: Room,
        state: WerewolfGameState,
        wolf_room: Room | None = None,
    ) -> None:
        super().__init__(
            name=name,
            model=model,
            llm=llm,
            prompt_builder=WerewolfPromptBuilder(player_name=name, role=role).build,
            temperature=0.9,
            tools=(WerewolfPlayerTools(name, public_room, state, wolf_room),),
            skills=(
                SkillSpec(
                    name=f"werewolf-{role.value}",
                    path=_SKILLS_ROOT / role.value / "SKILL.md",
                    description=f"Classic werewolf rules for the {role.value} role.",
                ),
            ),
        )
