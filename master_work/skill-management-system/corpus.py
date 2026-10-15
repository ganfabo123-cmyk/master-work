"""限定名单的语料加载；不扫描并吸收额外目录，不改写来源。"""

import hashlib
import json
from pathlib import Path
import re

from models import Skill, ValidationError, text_hash


EXPECTED_COUNT = 35
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def parse_skill(content: str) -> tuple[str, str, tuple[str, ...], str]:
    """读取当前语料使用的有限frontmatter格式；不声称支持完整YAML。"""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError("缺少frontmatter开头")
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        raise ValidationError("frontmatter未闭合")
    fields: dict[str, str] = {}
    triggers: list[str] = []
    in_triggers = False
    for line in lines[1:closing]:
        if not line.strip():
            continue
        if line.startswith("  - ") and in_triggers:
            value = line[4:].strip()
            if len(value) < 2 or value[0] not in "\"'" or value[-1] != value[0]:
                raise ValidationError("trigger必须是带引号的单行字符串")
            try:
                value = json.loads(value) if value[0] == '"' else value[1:-1]
            except json.JSONDecodeError:
                value = value[1:-1]  # 兼容既有语料中的字面反斜杠/引号
            if not value.strip():
                raise ValidationError("trigger不能为空")
            triggers.append(value)
            continue
        match = re.fullmatch(r"(name|description|triggers):\s*(.*)", line)
        if match is None:
            raise ValidationError(f"不支持的frontmatter行: {line}")
        key, value = match.groups()
        if key in fields:
            raise ValidationError(f"frontmatter字段重复: {key}")
        fields[key] = value
        in_triggers = key == "triggers"
        if in_triggers and value not in ("", "[]"):
            raise ValidationError("triggers必须为列表")
    for key in ("name", "description", "triggers"):
        if key not in fields:
            raise ValidationError(f"缺少字段: {key}")
    name = fields["name"].strip("'\"")
    # 与现有description缓存的文本口径一致，不拼接name或triggers。
    description = fields["description"].strip("'\"")
    if not description or description in ("|", ">", "|-", ">-"):
        raise ValidationError("当前语料要求非空的单行description")
    body = "\n".join(lines[closing + 1:]).strip()
    if not body:
        raise ValidationError("skill正文为空")
    return name, description, tuple(triggers), body


def load_corpus(root: Path, index_path: Path) -> list[Skill]:
    root = root.resolve()
    rows = []
    for number, line in enumerate(index_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"索引第{number}行不是JSON") from exc
        if not isinstance(row, dict):
            raise ValidationError(f"索引第{number}行不是对象")
        rows.append(row)
    if len(rows) != EXPECTED_COUNT:
        raise ValidationError(f"名单必须为{EXPECTED_COUNT}项，实际{len(rows)}项")
    skills = []
    seen = set()
    for row in rows:
        name = row.get("name")
        if not isinstance(name, str) or NAME_PATTERN.fullmatch(name) is None:
            raise ValidationError(f"非法skill名称: {name!r}")
        if name in seen:
            raise ValidationError(f"名单名称重复: {name}")
        seen.add(name)
        if row.get("arm") != "B-selected":
            raise ValidationError(f"非B-selected项: {name}")
        for field in ("group_id", "error_key", "model", "status", "sha256", "origin_path", "local_path"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValidationError(f"{name}: 缺少出处字段{field}")
        if not isinstance(row.get("source_sessions"), list) or not row["source_sessions"] or not all(isinstance(s, str) and s for s in row["source_sessions"]):
            raise ValidationError(f"{name}: source_sessions无效")
        source = (root / name / "SKILL.md").resolve()
        if not source.is_relative_to(root):
            raise ValidationError(f"语料路径越界: {name}")
        try:
            payload = source.read_bytes()
            content = payload.decode("utf-8")
            parsed_name, description, triggers, body = parse_skill(content)
        except (OSError, UnicodeError, ValidationError) as exc:
            raise ValidationError(f"{name}: {exc}") from exc
        if parsed_name != name:
            raise ValidationError(f"frontmatter名称与名单不一致: {name}")
        skills.append(Skill(
            skill_id=f"skill:{name}", name=name, description=description,
            triggers=triggers, body=body, full_content=content,
            source_path=str(source), description_sha256=text_hash(description),
            content_sha256=hashlib.sha256(payload).hexdigest(), provenance=row,
        ))
    return skills
