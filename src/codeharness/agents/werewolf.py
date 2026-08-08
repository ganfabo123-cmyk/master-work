"""One configurable Agent class for all werewolf players."""

from __future__ import annotations

from pathlib import Path

from ..base_agent import LLMAgent, SkillSpec
from ..llm import LLMClient
from ..core.room import Room
from ..policy.werewolf.prompt import WerewolfPromptBuilder
from ..policy.werewolf.tool import WerewolfPlayerTools
from ..state.werewolf import Role, WerewolfGameState


_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills" / "werewolf"


class WerewolfPlayerAgent(LLMAgent):
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
