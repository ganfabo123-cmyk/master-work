"""仅导入和验证本地向量；本阶段不调用embedding服务。"""

import json
import math
from pathlib import Path
from collections.abc import Mapping, Sequence

from models import Skill, ValidationError, VectorRecord


def validate_vector(vector: object, dimension: int, skill_id: str) -> tuple[float, ...]:
    if not isinstance(vector, list) or len(vector) != dimension:
        raise ValidationError(f"{skill_id}: 向量维度必须为{dimension}")
    try:
        valid = all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in vector)
        norm = math.hypot(*vector) if valid else 0.0
    except (OverflowError, TypeError):
        valid, norm = False, 0.0
    if not valid or not math.isfinite(norm) or norm == 0:
        raise ValidationError(f"{skill_id}: 向量必须为有限数值且范数非零")
    return tuple(float(v) for v in vector)


def import_vectors(cache_path: Path, skills: Sequence[Skill], model: str, dimension: int) -> dict[str, VectorRecord]:
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("version") != 1:
        raise ValidationError("不支持的向量缓存格式")
    if payload.get("model") != model:
        raise ValidationError(f"向量模型不一致，要求{model}")
    entries = payload.get("entries")
    if not isinstance(entries, Mapping):
        raise ValidationError("向量缓存缺少entries")
    records = {}
    errors = []
    for skill in skills:
        try:
            entry = entries.get(skill.skill_id)
            if not isinstance(entry, Mapping):
                raise ValidationError(f"{skill.skill_id}: 缺少向量")
            if entry.get("sha256") != skill.description_sha256:
                raise ValidationError(f"{skill.skill_id}: description指纹已失效")
            vector = validate_vector(entry.get("vector"), dimension, skill.skill_id)
            embedded_at = entry.get("embedded_at")
            if not isinstance(embedded_at, str) or not embedded_at:
                raise ValidationError(f"{skill.skill_id}: 缺少embedded_at")
            records[skill.skill_id] = VectorRecord(skill.skill_id, skill.description_sha256, vector, embedded_at)
        except ValidationError as exc:
            errors.append(str(exc))
    if errors:
        raise ValidationError("向量导入失败:\n" + "\n".join(errors))
    return records
