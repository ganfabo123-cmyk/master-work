"""第一阶段的数据契约；不包含检索或未来阶段的占位模型。"""

from dataclasses import asdict, dataclass
import hashlib
from typing import Any


class ValidationError(ValueError):
    """输入或管理状态不满足契约，禁止发布该状态。"""


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    description: str
    triggers: tuple[str, ...]
    body: str
    full_content: str
    source_path: str
    description_sha256: str
    content_sha256: str
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VectorRecord:
    skill_id: str
    sha256: str
    vector: tuple[float, ...]
    embedded_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
