"""Durable state for one classic eight-player werewolf game."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from random import Random, SystemRandom

from ...core.base_state import State


class Role(StrEnum):
    WOLF = "wolf"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    VILLAGER = "villager"


class Phase(StrEnum):
    PREPARATION = "preparation"
    NIGHT_WOLF_DISCUSSION = "night_wolf_discussion"
    NIGHT_WOLF_KILL = "night_wolf_kill"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    HUNTER_SHOT = "hunter_shot"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    REVIEW = "review"
    FINISHED = "finished"


class Winner(StrEnum):
    WOLVES = "wolves"
    VILLAGERS = "villagers"
    DRAW = "draw"


@dataclass(slots=True)
class PlayerState:
    name: str
    role: Role
    alive: bool = True


@dataclass(slots=True)
class Death:
    player: str
    cause: str


@dataclass(slots=True)
class WerewolfGameState(State):
    round_no: int = 1
    phase: Phase = Phase.PREPARATION
    players: dict[str, PlayerState] = field(default_factory=dict)
    witch_has_antidote: bool = True
    witch_has_poison: bool = True
    wolf_target: str | None = None
    pending_deaths: list[Death] = field(default_factory=list)
    hunter_name: str | None = None
    continue_phase: Phase | None = None
    winner: Winner | None = None
    consumed_action_ids: set[str] = field(default_factory=set)

    @classmethod
    def initial(cls, task_id: str, session_id: str) -> "WerewolfGameState":
        return cls.classic_eight_players(task_id=task_id, session_id=session_id)

    @property
    def is_terminal(self) -> bool:
        return self.phase is Phase.FINISHED or self.winner is not None

    def process(self, action: object) -> "WerewolfGameState":
        raise NotImplementedError("Werewolf State transitions are owned by WerewolfEnvironment.step()")

    @classmethod
    def classic_eight_players(cls, *, task_id: str = "", session_id: str = "") -> "WerewolfGameState":
        roles = {
            "player-1": Role.WOLF,
            "player-2": Role.WOLF,
            "player-3": Role.SEER,
            "player-4": Role.WITCH,
            "player-5": Role.HUNTER,
            "player-6": Role.VILLAGER,
            "player-7": Role.VILLAGER,
            "player-8": Role.VILLAGER,
        }
        return cls(task_id=task_id, session_id=session_id, players={name: PlayerState(name, role) for name, role in roles.items()})

    @classmethod
    def random_eight_players(
        cls,
        *,
        task_id: str = "",
        session_id: str = "",
        randomizer: Random | None = None,
    ) -> "WerewolfGameState":
        """Create a classic composition while assigning roles independently per game."""
        names = [f"player-{number}" for number in range(1, 9)]
        roles = [Role.WOLF, Role.WOLF, Role.SEER, Role.WITCH, Role.HUNTER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]
        (randomizer or SystemRandom()).shuffle(roles)
        return cls(
            task_id=task_id,
            session_id=session_id,
            players={name: PlayerState(name, role) for name, role in zip(names, roles, strict=True)},
        )

    def alive_players(self) -> tuple[str, ...]:
        return tuple(name for name, player in self.players.items() if player.alive)

    def alive_wolves(self) -> tuple[str, ...]:
        return tuple(name for name, player in self.players.items() if player.alive and player.role is Role.WOLF)

    def role_of(self, name: str) -> Role:
        return self.players[name].role

    def is_alive(self, name: str) -> bool:
        return name in self.players and self.players[name].alive

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["consumed_action_ids"] = sorted(self.consumed_action_ids)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "WerewolfGameState":
        players_raw = data.get("players", {})
        if not isinstance(players_raw, dict):
            raise ValueError("werewolf state has invalid players")
        players = {
            name: PlayerState(name=name, role=Role(player["role"]), alive=bool(player.get("alive", True)))
            for name, player in players_raw.items()
            if isinstance(name, str) and isinstance(player, dict)
        }
        deaths_raw = data.get("pending_deaths", [])
        deaths = [Death(player=str(item["player"]), cause=str(item["cause"])) for item in deaths_raw if isinstance(item, dict)]
        return cls(
            task_id=str(data.get("task_id", "")),
            session_id=str(data.get("session_id", "")),
            round_no=int(data.get("round_no", 1)),
            phase=Phase(str(data.get("phase", Phase.PREPARATION))),
            players=players,
            witch_has_antidote=bool(data.get("witch_has_antidote", True)),
            witch_has_poison=bool(data.get("witch_has_poison", True)),
            wolf_target=data.get("wolf_target") if isinstance(data.get("wolf_target"), str) else None,
            pending_deaths=deaths,
            hunter_name=data.get("hunter_name") if isinstance(data.get("hunter_name"), str) else None,
            continue_phase=Phase(str(data["continue_phase"])) if data.get("continue_phase") else None,
            winner=Winner(str(data["winner"])) if data.get("winner") else None,
            consumed_action_ids=set(str(value) for value in data.get("consumed_action_ids", []) if isinstance(value, str)),
        )


def phase_announcement(state: WerewolfGameState) -> str:
    return {
        Phase.PREPARATION: "你已拿到身份。请认真准备并思考策略；如需参考过往复盘，可调用 list_experiences 查看自己的历史经验摘要，再用 get_experience 阅读详情。准备完成后直接结束本回合，等待游戏正式开始。",
        Phase.NIGHT_WOLF_DISCUSSION: f"第 {state.round_no} 夜：狼人请私下协商。",
        Phase.NIGHT_WOLF_KILL: "狼人协商结束，请提交击杀目标。",
        Phase.NIGHT_SEER: "预言家请查验。",
        Phase.NIGHT_WITCH: "女巫请行动。",
        Phase.HUNTER_SHOT: "猎人进入开枪阶段。",
        Phase.DAY_DISCUSSION: f"第 {state.round_no} 天：请公开讨论。",
        Phase.DAY_VOTE: "讨论结束，请投票放逐一名玩家。",
        Phase.REVIEW: "游戏结算已发送，请完成复盘。",
    }[state.phase]


def actors_for_phase(state: WerewolfGameState) -> tuple[str, ...]:
    if state.phase is Phase.PREPARATION:
        return tuple(state.players)
    if state.phase in {Phase.NIGHT_WOLF_DISCUSSION, Phase.NIGHT_WOLF_KILL}:
        return state.alive_wolves()
    if state.phase is Phase.NIGHT_SEER:
        return tuple(name for name in state.alive_players() if state.role_of(name) is Role.SEER)
    if state.phase is Phase.NIGHT_WITCH:
        return tuple(name for name in state.alive_players() if state.role_of(name) is Role.WITCH)
    if state.phase in {Phase.DAY_DISCUSSION, Phase.DAY_VOTE}:
        return state.alive_players()
    if state.phase is Phase.HUNTER_SHOT and state.hunter_name is not None:
        return (state.hunter_name,)
    if state.phase is Phase.REVIEW:
        return tuple(state.players)
    return ()


def player_visible_state(state: WerewolfGameState) -> dict[str, object]:
    return {"round_no": state.round_no, "phase": state.phase.value, "alive_players": state.alive_players()}
