"""将名单、语料状态、向量作为同一代快照发布。"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from collections.abc import Mapping

from corpus import EXPECTED_COUNT, parse_skill
from embeddings import validate_vector
from models import Skill, ValidationError, VectorRecord, text_hash
from clustering import unit
from nodes import validate_layout
from feedback import replay, validate_feedback
from signatures import validate_channel_policy
from signature_mining import validate_signature_management
from maintenance import validate_maintenance


def build_snapshot(skills: list[Skill], vectors: dict[str, VectorRecord], model: str, dimension: int) -> dict:
    return {
        "manifest": {
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model,
            "dimension": dimension,
            "members": [{"skill_id": s.skill_id, "source_path": s.source_path,
                         "provenance": s.provenance} for s in skills],
        },
        "state": {"version": 1, "skills": {s.skill_id: s.to_dict() for s in skills}},
        "vectors": {"version": 1, "entries": {key: v.to_dict() for key, v in vectors.items()}},
    }


def validate_snapshot(snapshot: dict) -> None:
    try:
        manifest, state, vectors = (snapshot[key] for key in ("manifest", "state", "vectors"))
        if any(part["version"] != 1 for part in (manifest, state, vectors)):
            raise ValidationError("不支持的快照版本")
        if not isinstance(manifest["model"], str) or not manifest["model"]:
            raise ValidationError("快照模型无效")
        dimension = manifest["dimension"]
        if type(dimension) is not int or dimension <= 0:
            raise ValidationError("快照维度无效")
        members = manifest["members"]
        ids = [item["skill_id"] for item in members]
        if len(ids) != EXPECTED_COUNT or len(set(ids)) != EXPECTED_COUNT:
            raise ValidationError("快照名单必须为35个唯一skill")
        if set(state["skills"]) != set(ids) or set(vectors["entries"]) != set(ids):
            raise ValidationError("名单、语料状态与向量成员不一致")
        for member in members:
            skill_id = member["skill_id"]
            skill = state["skills"][skill_id]
            entry = vectors["entries"][skill_id]
            if skill["skill_id"] != skill_id or skill_id != "skill:" + skill["name"]:
                raise ValidationError(f"{skill_id}: ID不一致")
            if member["source_path"] != skill["source_path"] or member["provenance"] != skill["provenance"]:
                raise ValidationError(f"{skill_id}: 出处映射不一致")
            if skill["provenance"]["name"] != skill["name"] or skill["provenance"]["arm"] != "B-selected":
                raise ValidationError(f"{skill_id}: 非名单内B-selected项")
            name, description, triggers, body = parse_skill(skill["full_content"])
            if (name, description, triggers, body) != (skill["name"], skill["description"], tuple(skill["triggers"]), skill["body"]):
                raise ValidationError(f"{skill_id}: 保存字段与原文不一致")
            if text_hash(skill["full_content"]) != skill["content_sha256"] or text_hash(description) != skill["description_sha256"]:
                raise ValidationError(f"{skill_id}: 内容指纹不一致")
            if entry["skill_id"] != skill_id or entry["sha256"] != skill["description_sha256"]:
                raise ValidationError(f"{skill_id}: 向量指纹不一致")
            if not isinstance(entry["embedded_at"], str) or not entry["embedded_at"]:
                raise ValidationError(f"{skill_id}: 缺少向量生成时间")
            validate_vector(list(entry["vector"]), dimension, skill_id)
        if "clustering" in state:
            validate_layout(state["clustering"], {
                skill_id: unit(vectors["entries"][skill_id]["vector"]) for skill_id in ids})
        validate_feedback(snapshot)
        validate_channel_policy(snapshot)
        validate_signature_management(snapshot)
        validate_maintenance(snapshot)
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"快照结构无效: {exc}") from exc


class SnapshotStore:
    """CURRENT原子替换是唯一发布点；读者始终读取完整的一代。"""

    def __init__(self, root: Path):
        self.root = root

    def publish(self, snapshot: dict) -> str:
        validate_snapshot(snapshot)
        generations = self.root / "snapshots"
        generations.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="generation-", dir=generations))
        for name, payload in snapshot.items():
            is_log = name in ("observations", "ratings", "maintenance_log")
            path = directory / f"{name}.{'jsonl' if is_log else 'json'}"
            with path.open("w", encoding="utf-8", newline="\n") as stream:
                if is_log:
                    for record in payload:
                        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                else:
                    json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
                    stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        if "signature_management" in snapshot["state"]:
            for skill in snapshot["state"]["skills"].values():
                path = self._skill_path(directory, skill)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8", newline="") as stream:
                    stream.write(skill["full_content"])
                    stream.flush()
                    os.fsync(stream.fileno())
        # 回读通过才切换指针。失败快照保留为未发布产物，不影响旧CURRENT。
        self._read_generation(directory)
        fd, temporary = tempfile.mkstemp(prefix=".CURRENT-", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(directory.name + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / "CURRENT")
        finally:
            Path(temporary).unlink(missing_ok=True)
        return directory.name

    def _read_generation(self, directory: Path, rebuild_feedback=False) -> dict:
        try:
            snapshot = {name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
                        for name in ("manifest", "state", "vectors")}
            if "feedback" in snapshot["state"]:
                for name in ("observations", "ratings"):
                    snapshot[name] = [json.loads(line) for line in (directory / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            if "signature_management" in snapshot["state"]:
                for name in ("signature_index", "review_queue"):
                    snapshot[name] = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
                for skill in snapshot["state"]["skills"].values():
                    if self._skill_path(directory, skill).read_bytes().decode("utf-8") != skill["full_content"]:
                        raise ValidationError("管理副本SKILL.md与状态不一致")
            if "maintenance" in snapshot["state"]:
                snapshot["maintenance_queue"] = json.loads((directory / "maintenance_queue.json").read_text(encoding="utf-8"))
                snapshot["maintenance_log"] = [json.loads(line) for line in (directory / "maintenance_log.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, ValueError) as exc:
            raise ValidationError(f"快照读取失败: {exc}") from exc
        if rebuild_feedback and "feedback" in snapshot["state"]:
            snapshot["state"]["feedback"] = replay(snapshot, snapshot["observations"], snapshot["ratings"], snapshot["state"]["feedback"]["options"])
        validate_snapshot(snapshot)
        return snapshot

    @staticmethod
    def _skill_path(directory, skill):
        name = skill["name"]
        if not isinstance(name, str) or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
            raise ValidationError("管理副本skill名称无效")
        return directory / "skills" / name / "SKILL.md"

    def read(self, rebuild_feedback=False) -> dict:
        generation = (self.root / "CURRENT").read_text(encoding="utf-8").strip()
        if re.fullmatch(r"generation-[a-z0-9_]+", generation) is None:
            raise ValidationError("CURRENT快照指针无效")
        directory = (self.root / "snapshots" / generation).resolve()
        if not directory.is_relative_to((self.root / "snapshots").resolve()):
            raise ValidationError("快照路径越界")
        return self._read_generation(directory, rebuild_feedback)
