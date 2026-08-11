"""Pydantic contracts for ROOM participants and messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentProfile(BaseModel):
    """Developer-declared metadata used to register and invite an Agent."""

    schema_version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, description="Session 内唯一的 Agent ID。")
    display_name: str | None = Field(default=None, description="可重复的展示名称；缺省时使用 name。")
    introduction: str = Field(description="Agent 能力与职责的简短介绍。")
    skill: tuple[str, ...] = Field(default=(), description="Agent 擅长处理的技能标签。")
    role: str = Field(description="Agent 在协作中的身份，例如 planner 或 reviewer。")
    kwargs: dict[str, Any] = Field(default_factory=dict, description="开发者定义的其他可扩展 Agent 属性。")

    @field_validator("name", "introduction", "role", "display_name")
    @classmethod
    def require_nonempty_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("profile text fields cannot be empty")
        return normalized


class RoomMessage(BaseModel):
    """One ROOM message sent by an Agent or a future human participant.

    ``at`` is a single name, a tuple of names for a private group, or ``all``.
    """

    message_id: str = Field(default_factory=lambda: uuid4().hex, description="消息唯一标识。")
    name: str = Field(min_length=1, description="发送者名称；必须是 ROOM 当前成员。")
    at: str | tuple[str, ...] = Field(
        description="接收者 Agent 名称、接收者名称列表，或 all 表示广播给 ROOM 全体成员。"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="消息创建时间，使用带时区的时间戳。")
    txt: str | None = Field(default=None, description="可选文本内容。")
    image: str | None = Field(default=None, description="可选图片内容或图片引用；具体获取方式由后续实现决定。")
    audio: str | None = Field(default=None, description="可选音频内容或音频引用；具体获取方式由后续实现决定。")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message names cannot be empty")
        return normalized

    @field_validator("at", mode="before")
    @classmethod
    def normalize_recipients(cls, value: object) -> str | tuple[str, ...]:
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("recipient cannot be empty")
            return normalized
        if not isinstance(value, (list, tuple)):
            raise ValueError("recipient must be a name, a list of names, or all")
        recipients = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
        if len(recipients) != len(value):
            raise ValueError("each recipient must be a non-empty name")
        if not recipients:
            raise ValueError("recipient list cannot be empty")
        if len(set(recipients)) != len(recipients):
            raise ValueError("recipient list cannot contain duplicates")
        return recipients

    @model_validator(mode="after")
    def require_content(self) -> "RoomMessage":
        if not any(_has_content(content) for content in (self.txt, self.image, self.audio)):
            raise ValueError("a ROOM message requires at least one of txt, image, or audio")
        return self


def _has_content(value: str | None) -> bool:
    return value is not None and bool(value.strip())
