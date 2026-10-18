"""Register generated Skills into the existing management system.

The registry is the boundary between Skill generation and management.  It
builds a complete, versioned corpus and description-vector cache in a new
batch directory, runs the unchanged management CLI against that batch, and
only then activates the generated manager configuration.

Run without arguments after editing ``registry-config.json``::

    python register_skills.py
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "registry-config.json"
EXPECTED_MODEL = "text-embedding-v4"
EXPECTED_DIMENSION = 1024


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing registry config: {path}. Copy registry-config.example.json to registry-config.json first.")
    config = read_json(path)
    if not isinstance(config, dict):
        raise ValueError("registry-config.json must contain an object")
    for key in ("source_output", "manager_config", "registry_root"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"registry config requires a non-empty '{key}' path")
        config[key] = str(resolve_path(config[key], path.parent))
    if not isinstance(config.get("activate_manager_config", True), bool):
        raise ValueError("activate_manager_config must be boolean")
    config["activate_manager_config"] = config.get("activate_manager_config", True)
    manager_python = config.get("manager_python")
    if manager_python is not None and (not isinstance(manager_python, str) or not manager_python.strip()):
        raise ValueError("manager_python must be a non-empty executable path")
    config["manager_python"] = manager_python or sys.executable

    embedding = config.setdefault("manager_embedding", {})
    if not isinstance(embedding, dict):
        raise ValueError("manager_embedding must be an object")
    embedding.setdefault("endpoint", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    embedding.setdefault("api_key_env", "DASHSCOPE_API_KEY")
    embedding.setdefault("batch_size", 32)
    embedding.setdefault("timeout_seconds", 120)
    embedding.setdefault("use_system_proxy", False)
    if not isinstance(embedding["endpoint"], str) or not embedding["endpoint"].strip():
        raise ValueError("manager_embedding.endpoint must be non-empty")
    if not isinstance(embedding["api_key_env"], str) or not embedding["api_key_env"].strip():
        raise ValueError("manager_embedding.api_key_env must be non-empty")
    if type(embedding["batch_size"]) is not int or embedding["batch_size"] < 1:
        raise ValueError("manager_embedding.batch_size must be a positive integer")
    if isinstance(embedding["timeout_seconds"], bool) or not isinstance(embedding["timeout_seconds"], (int, float)) or embedding["timeout_seconds"] <= 0:
        raise ValueError("manager_embedding.timeout_seconds must be positive")
    if not isinstance(embedding["use_system_proxy"], bool):
        raise ValueError("manager_embedding.use_system_proxy must be boolean")

    default_triggers = config.get("default_triggers", [])
    if not isinstance(default_triggers, list) or not all(isinstance(item, str) and item.strip() for item in default_triggers):
        raise ValueError("default_triggers must be a list of non-empty strings")
    config["default_triggers"] = default_triggers
    return config


def load_manager_modules(manager_config_path: Path):
    manager_root = manager_config_path.parent.resolve()
    if str(manager_root) not in sys.path:
        sys.path.insert(0, str(manager_root))
    corpus = importlib.import_module("corpus")
    embedding_client = importlib.import_module("embedding_client")
    return corpus, embedding_client


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int]:
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md is missing frontmatter")
    closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if closing is None:
        raise ValueError("SKILL.md frontmatter is not closed")
    return 0, closing


def ensure_triggers(content: str, triggers: list[str]) -> str:
    """Add the manager's required triggers field without rewriting existing metadata."""
    lines = content.splitlines()
    _, closing = _frontmatter_bounds(lines)
    if any(line.strip().startswith("triggers:") for line in lines[1:closing]):
        return content if content.endswith("\n") else content + "\n"
    insert = ["triggers: []"] if not triggers else ["triggers:"] + [f'  - {json.dumps(item, ensure_ascii=False)}' for item in triggers]
    normalized = lines[:closing] + insert + lines[closing:]
    return "\n".join(normalized).rstrip("\n") + "\n"


def source_index_path(source_output: Path, primary_input: str) -> Path:
    candidates = [source_output / f"{primary_input}-skill-index.jsonl"]
    if primary_input == "C":
        candidates.append(source_output / "C-skill-index.jsonl")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValueError(f"Missing generated Skill index for input {primary_input}: {candidates[0]}")


def load_source_rows(source_output: Path, primary_input: str) -> list[dict[str, Any]]:
    path = source_index_path(source_output, primary_input)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"Generated Skill index is empty or malformed: {path}")
    return rows


def _source_path(source_output: Path, row: dict[str, Any]) -> Path:
    value = row.get("markdown_path")
    if isinstance(value, str) and value.strip() and Path(value).is_file():
        return Path(value)
    name = row.get("name")
    if isinstance(name, str):
        fallback = source_output / "skills" / name / "SKILL.md"
        if fallback.is_file():
            return fallback
    raise ValueError(f"Generated Skill source is missing: {row.get('name')!r}")


def build_corpus(source_output: Path, rows: list[dict[str, Any]], destination: Path,
                 default_triggers: list[str], manager_corpus: Any) -> tuple[Path, Path, list[Any]]:
    corpus_root = destination / "corpus"
    index_path = corpus_root / "index.jsonl"
    corpus_root.mkdir(parents=True, exist_ok=True)
    names: set[str] = set()
    index_rows = []
    for row in rows:
        name = row.get("name")
        if not isinstance(name, str) or manager_corpus.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError(f"Invalid Skill name: {name!r}")
        if name in names:
            raise ValueError(f"Duplicate Skill name: {name}")
        names.add(name)
        source = _source_path(source_output, row)
        content = source.read_text(encoding="utf-8")
        normalized = ensure_triggers(content, default_triggers)
        target = corpus_root / "skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(normalized, encoding="utf-8", newline="\n")
        payload = target.read_bytes()
        source_files = row.get("source_files", [])
        sessions = sorted({item.get("session_id") for item in source_files
                           if isinstance(item, dict) and isinstance(item.get("session_id"), str) and item["session_id"]})
        if not sessions:
            raise ValueError(f"{name}: generated index has no source_sessions")
        group_id = row.get("group_id") or row.get("source_group_id")
        if not isinstance(group_id, str) or not group_id:
            raise ValueError(f"{name}: generated index has no group_id")
        error_key = row.get("error_key") or row.get("group_key") or group_id
        model = row.get("model") or "unknown"
        status = row.get("status") or "candidate_needs_review"
        index_rows.append({
            "name": name,
            "group_id": group_id,
            "error_key": str(error_key),
            "model": str(model),
            "arm": "B-selected",
            "status": str(status),
            "source_sessions": sessions,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "origin_path": str(source.resolve()),
            "local_path": f"skills/{name}/SKILL.md",
        })
    write_jsonl(index_path, index_rows)
    skills = manager_corpus.load_corpus(corpus_root / "skills", index_path)
    return corpus_root / "skills", index_path, skills


def build_manager_config(base_path: Path, batch_dir: Path, corpus_root: Path, index_path: Path,
                         embedding_cache: Path, data_dir: Path) -> dict[str, Any]:
    config = read_json(base_path)
    if not isinstance(config, dict):
        raise ValueError("manager config must contain an object")
    config["corpus_root"] = str(corpus_root.resolve())
    config["index_path"] = str(index_path.resolve())
    config["embedding_cache"] = str(embedding_cache.resolve())
    config["data_dir"] = str(data_dir.resolve())
    generated = batch_dir / "manager-config.json"
    write_json(generated, config)
    return config


def build_embedding_cache(skills: list[Any], destination: Path, settings: dict[str, Any], embedding_client: Any) -> None:
    api_key = os.getenv(settings["api_key_env"], "").strip()
    if not api_key:
        raise ValueError(f"Environment variable {settings['api_key_env']} is empty")
    if settings.get("model", EXPECTED_MODEL) != EXPECTED_MODEL:
        raise ValueError(f"manager embedding model must be {EXPECTED_MODEL}")
    provider = embedding_client.EmbeddingApiClient(
        embedding_client.EmbeddingApiConfig(
            endpoint=settings["endpoint"], model=EXPECTED_MODEL, api_key=api_key,
            batch_size=settings["batch_size"], timeout_seconds=settings["timeout_seconds"],
            use_system_proxy=settings["use_system_proxy"]),
        dimension=EXPECTED_DIMENSION,
    )
    vectors = provider.embed([skill.description for skill in skills])
    if len(vectors) != len(skills):
        raise ValueError("Description embedding count does not match Skill count")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {"version": 1, "model": EXPECTED_MODEL, "dimension": EXPECTED_DIMENSION, "entries": {}}
    for skill, vector in zip(skills, vectors):
        if len(vector) != EXPECTED_DIMENSION:
            raise ValueError(f"{skill.name}: description embedding dimension is not {EXPECTED_DIMENSION}")
        payload["entries"][skill.skill_id] = {
            "skill_id": skill.skill_id, "sha256": skill.description_sha256,
            "vector": vector, "embedded_at": now,
        }
    write_json(destination, payload)


def run_manager(manager_config: Path, manager_python: str, operation: str) -> dict[str, Any]:
    manager_root = manager_config.parent
    manager_script = manager_root / "manager.py"
    if not manager_script.is_file():
        raise ValueError(f"Missing management entrypoint: {manager_script}")
    result = subprocess.run([manager_python, str(manager_script), operation, "--config", str(manager_config)],
                            cwd=str(manager_root), capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"manager.py {operation} failed:\n{result.stdout}\n{result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"manager.py {operation} returned non-JSON output: {result.stdout}") from error


def activate_config(base_path: Path, generated_config: dict[str, Any], backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(base_path, backup_path)
    write_json(base_path, generated_config)


def run(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = load_config(config_path)
    source_output = Path(config["source_output"])
    source_manifest_path = source_output / "manifest.json"
    if not source_manifest_path.is_file():
        raise ValueError(f"Missing upstream manifest: {source_manifest_path}")
    source_manifest = read_json(source_manifest_path)
    if source_manifest.get("status") != "completed":
        raise ValueError(f"Upstream run is not completed: {source_manifest.get('status')}")
    primary_input = config.get("primary_input") or source_manifest.get("primary_input")
    if primary_input not in {"A", "B", "C"}:
        raise ValueError(f"Invalid primary_input: {primary_input!r}")
    rows = load_source_rows(source_output, primary_input)
    manager_config_path = Path(config["manager_config"])
    manager_corpus, embedding_client = load_manager_modules(manager_config_path)
    base_manager_config = read_json(manager_config_path)
    if base_manager_config.get("embedding_model") != EXPECTED_MODEL or base_manager_config.get("embedding_dimension") != EXPECTED_DIMENSION:
        raise ValueError("manager config must use text-embedding-v4 with dimension 1024")

    batch_id = datetime.now(timezone.utc).strftime("batch-%Y%m%d-%H%M%S")
    registry_root = Path(config["registry_root"])
    batch_dir = registry_root / "runs" / batch_id
    if batch_dir.exists():
        raise ValueError(f"Registry batch already exists: {batch_dir}")
    batch_dir.mkdir(parents=True, exist_ok=False)
    registry_manifest = {"status": "staging", "batch_id": batch_id,
                         "source_output": str(source_output.resolve()), "primary_input": primary_input,
                         "source_manifest": str(source_manifest_path.resolve()), "skill_count": len(rows)}
    write_json(batch_dir / "registry-manifest.json", registry_manifest)
    try:
        corpus_root, index_path, skills = build_corpus(source_output, rows, batch_dir,
                                                       config["default_triggers"], manager_corpus)
        embedding_cache = batch_dir / "embedding_cache.json"
        data_dir = batch_dir / "data"
        generated_config = build_manager_config(manager_config_path, batch_dir, corpus_root, index_path,
                                                embedding_cache, data_dir)
        build_embedding_cache(skills, embedding_cache, config["manager_embedding"], embedding_client)
        manager_results = {}
        generated_manager_config = batch_dir / "manager-config.json"
        for operation in ("initialize", "cluster", "verify"):
            manager_results[operation] = run_manager(generated_manager_config, config["manager_python"], operation)
        if config["activate_manager_config"]:
            activate_config(manager_config_path, generated_config, batch_dir / "previous-manager-config.json")
        registry_manifest.update({"status": "published", "skill_count": len(skills),
                                  "corpus_root": str(corpus_root.resolve()), "index_path": str(index_path.resolve()),
                                  "embedding_cache": str(embedding_cache.resolve()), "data_dir": str(data_dir.resolve()),
                                  "manager_config": str(generated_manager_config.resolve()),
                                  "manager_results": manager_results,
                                  "activated": config["activate_manager_config"]})
        write_json(registry_root / "ACTIVE.json", registry_manifest)
        write_json(batch_dir / "registry-manifest.json", registry_manifest)
        return registry_manifest
    except Exception as error:
        registry_manifest.update({"status": "failed", "error": str(error)})
        write_json(batch_dir / "registry-manifest.json", registry_manifest)
        raise


def main() -> int:
    try:
        result = run()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"register_skills failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "batch_id": result["batch_id"],
                      "skills": result["skill_count"], "activated": result["activated"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
