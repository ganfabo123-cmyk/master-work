# -*- coding: utf-8 -*-
"""从 skills-result 运行目录提取 B-selected（B组）skills 作为实验语料。

用法：
    python extract_skills_b.py

做四件事：
1. 读取 skills-result/20261014-210632/20261014-210632/skill-index.jsonl，过滤 arm == "B-selected"；
2. 校验：名字唯一、SKILL.md 存在、frontmatter 含 name/description 且 name 与目录一致；
3. 字节级复制到本目录 skills_b/<name>/SKILL.md（不去重——跨 group 的同主题近重复
   正是检索实验需要的对比组素材）；
4. 写 skills_b/index.jsonl，逐条记录出处元数据（group_id/error_key/来源 session/
   模型/字节数/sha256），供实验评估对账。

注意：目标文件已存在时跳过复制（本语料在提取后补写过 frontmatter triggers 签名，
见 add_triggers_skills_b.py；重跑本脚本不会覆盖这些策划内容）。index.jsonl 每次重跑
都会按原始运行目录的元数据重新生成；其中 bytes/sha256 记录的是提取时刻的原始内容
指纹，本地文件此后的编辑（triggers）不反映在其中。

只读原始运行目录，不修改其中任何文件。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

SKILL_RESULT_ROOT = (
    Path(__file__).resolve().parent.parent
    / "skills-result" / "20261014-210632" / "20261014-210632"
)
SKILL_INDEX = SKILL_RESULT_ROOT / "skill-index.jsonl"
# skill-index.jsonl 里的 markdown_path 是生成机上的绝对路径前缀，映射到本仓库副本
ORIGIN_PREFIX = r"C:\Users\35153\PycharmProjects\master-work\skill-runs\20261014-210632"

OUTPUT_ROOT = Path(__file__).resolve().parent / "skills_b"
ARM = "B-selected"


def _local_path(origin: str) -> Path:
    if not origin.startswith(ORIGIN_PREFIX):
        raise ValueError(f"markdown_path 不在预期运行目录下：{origin}")
    return SKILL_RESULT_ROOT / origin[len(ORIGIN_PREFIX):].lstrip("\\/")


def _frontmatter_field(content: str, field: str) -> str | None:
    """极简 frontmatter 单行字段提取（与 retrieval_program 的解析约定一致）。"""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    closing = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing = i
            break
    if closing is None:
        return None
    prefix = field + ":"
    for line in lines[1:closing]:
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def main() -> None:
    rows = [
        json.loads(line)
        for line in SKILL_INDEX.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [row for row in rows if row.get("arm") == ARM]
    print(f"skill-index.jsonl 共 {len(rows)} 条，其中 {ARM} {len(selected)} 条")

    names = [row["name"] for row in selected]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise SystemExit(f"B 组内存在重名 skill，需要先决定冲突策略：{duplicates}")

    OUTPUT_ROOT.mkdir(exist_ok=True)
    records: list[dict] = []
    extracted = 0
    skipped = 0
    for row in selected:
        src = _local_path(row["markdown_path"])
        if not src.is_file():
            raise SystemExit(f"SKILL.md 缺失：{src}")
        content = src.read_text(encoding="utf-8")

        fm_name = _frontmatter_field(content, "name")
        description = _frontmatter_field(content, "description")
        if fm_name != row["name"]:
            raise SystemExit(f"frontmatter name 与索引不一致：{fm_name!r} != {row['name']!r}（{src}）")
        if not description:
            raise SystemExit(f"SKILL.md 缺少 description：{src}")

        dest_dir = OUTPUT_ROOT / row["name"]
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / "SKILL.md"
        if dest.exists():
            # 保护已策划的本地语料（triggers 签名等后处理）；如需强制重提取请先删除
            skipped += 1
        else:
            shutil.copyfile(src, dest)
            extracted += 1

        payload = src.read_bytes()
        sessions = sorted({
            f["session_id"]
            for f in row.get("source_files", [])
            if f.get("session_id")
        })
        records.append({
            "name": row["name"],
            "group_id": row.get("group_id"),
            "error_key": row.get("error_key"),
            "model": row.get("model"),
            "arm": row.get("arm"),
            "status": row.get("status"),
            "source_sessions": sessions,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "origin_path": row.get("markdown_path"),
            "local_path": f"skills_b/{row['name']}/SKILL.md",
        })

    index_path = OUTPUT_ROOT / "index.jsonl"
    index_path.write_text(
        "\n".join(json.dumps(rec, ensure_ascii=False) for rec in records) + "\n",
        encoding="utf-8",
    )

    print(f"已提取 {extracted} 个，跳过已存在 {skipped} 个 -> {OUTPUT_ROOT}")
    print(f"出处索引 -> {index_path}")
    print("\n按 error_key 分布：")
    by_key: dict[str, int] = {}
    for rec in records:
        by_key[rec["error_key"] or "(none)"] = by_key.get(rec["error_key"] or "(none)", 0) + 1
    for key, count in sorted(by_key.items()):
        print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
