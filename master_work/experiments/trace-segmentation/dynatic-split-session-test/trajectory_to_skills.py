"""Run the raw-trajectory to Skill extraction pipeline from config.json.

The command intentionally has no runtime flags.  Edit the JSON configuration
next to this file, then run ``python trajectory_to_skills.py``.  Existing
experimental scripts remain usable independently; this module only wires the
canonical stages together and records their intermediate artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

import embed_messages_dashscope as embedder
import error_skill_extraction as extraction
import strategy_clustering as clustering


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
LOGICAL_ARMS = ("A", "B", "C")
LEGACY_ARMS = {
    "A": "A-original",
    "B": "C-context-collapsed",
    "C": "B-selected",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        raise ValueError(f"Missing config file: {path}. Copy config.example.json to config.json first.")
    config = read_json(path)
    if not isinstance(config, dict):
        raise ValueError("config.json must contain an object")
    for key in ("input", "output"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"config.json requires a non-empty '{key}' path")
        config[key] = str(resolve_path(config[key], path.parent))

    embedding = config.setdefault("embedding", {})
    ratio = embedding.get("ratio", 1.0)
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 < ratio <= 1:
        raise ValueError("embedding.ratio must be in (0, 1]")
    embedding["ratio"] = float(ratio)
    embedding.setdefault("seed", 42)
    if type(embedding["seed"]) is not int:
        raise ValueError("embedding.seed must be an integer")
    embedding.setdefault("model", embedder.DEFAULT_MODEL)
    embedding.setdefault("base_url", embedder.DEFAULT_BASE_URL)
    embedding.setdefault("dimensions", None)
    embedding.setdefault("batch_size", 20)
    embedding.setdefault("timeout", 120)
    embedding.setdefault("retries", 4)
    embedding.setdefault("sleep_seconds", 2.0)
    if not isinstance(embedding.get("api_key"), str) or not embedding["api_key"].strip():
        embedding["api_key"] = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not embedding["api_key"]:
        raise ValueError("embedding.api_key is empty; fill it in config.json")

    clustering_config = config.setdefault("clustering", {})
    strategy = clustering_config.get("strategy", "native-code")
    if not isinstance(strategy, str) or strategy not in clustering.STRATEGY_REGISTRY:
        raise ValueError(f"clustering.strategy is not a registered strategy: {strategy!r}")
    clustering_config["strategy"] = strategy

    segmentation = config.setdefault("segmentation", {})
    segmentation.setdefault("windows", [13, 25, 37])
    segmentation.setdefault("fdr", 0.10)
    segmentation.setdefault("min_stability", 2 / 3)
    segmentation.setdefault("min_gap", 30)
    segmentation.setdefault("min_segment", 30)
    segmentation.setdefault("overlap_events", 25)
    segmentation.setdefault("max_splits", 100)
    segmentation.setdefault("length_bands", "0:0.10,500:0.30,800:0.45")

    extraction_config = config.setdefault("extraction", {})
    inputs = extraction_config.get("inputs", ["A", "B", "C"])
    if not isinstance(inputs, list) or not inputs or any(item not in LOGICAL_ARMS for item in inputs):
        raise ValueError("extraction.inputs must be a nonempty list containing only A, B, or C")
    extraction_config["inputs"] = list(dict.fromkeys(inputs))
    primary = extraction_config.get("primary_input", extraction_config["inputs"][-1])
    if primary not in extraction_config["inputs"]:
        raise ValueError("extraction.primary_input must be included in extraction.inputs")
    extraction_config["primary_input"] = primary
    extraction_config.setdefault("selection_strategy", "group-context")
    extraction_config.setdefault("prompt", str(HERE / "error-skill-extraction-prompt.txt"))
    extraction_config["prompt"] = str(resolve_path(extraction_config["prompt"], path.parent))
    api = extraction_config.setdefault("api", {})
    for key in ("api_key", "base_url", "model"):
        if not isinstance(api.get(key), str) or not api[key].strip():
            raise ValueError(f"extraction.api.{key} is empty; fill it in config.json")
    api.setdefault("userAgent", extraction.DEFAULT_USER_AGENT)
    return config


def _event(category: str, role: str, part_type: str, source_index: int, source_part_index: int,
           **details: Any) -> dict[str, Any]:
    return {"category": category, "role": role, "part_type": part_type,
            "source_index": source_index, "source_part_index": source_part_index, **details}


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    tool_names: dict[str, str] = {}
    for source_index, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines()):
        if not line.strip():
            continue
        record = json.loads(line)
        message = record.get("message", record)
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", record.get("role", "unknown")))
        content = message.get("content", record.get("content", []))
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if not isinstance(content, list):
            continue
        for part_index, part in enumerate(content):
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "text"))
            if part_type in {"tool_use", "tool_call"}:
                name = str(part.get("name", part.get("tool_name", "unknown")))
                tool_id = str(part.get("tool_use_id", part.get("id", "")))
                if tool_id:
                    tool_names[tool_id] = name
                events.append(_event("tool_call:" + name, role, part_type, source_index, part_index,
                                     tool_name=name, arguments=part.get("input", part.get("arguments", {})),
                                     tool_use_id=tool_id))
            elif part_type in {"tool_result", "tool-result"} or role == "tool":
                tool_id = str(part.get("tool_use_id", part.get("id", "")))
                events.append(_event("tool_result", role, part_type, source_index, part_index,
                                     tool_name=tool_names.get(tool_id, ""), tool_use_id=tool_id,
                                     content=part.get("content", part.get("output", part.get("text", "")))))
            elif part_type in {"thinking", "reasoning"}:
                events.append(_event(f"{role}_{part_type}", role, part_type, source_index, part_index,
                                     thinking=part.get("thinking", part.get("text", "")),
                                     text=part.get("text", part.get("thinking", ""))))
            else:
                events.append(_event(f"{role}_text", role, part_type, source_index, part_index,
                                     text=part.get("text", "")))
    return events


def _parse_opencode(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    events: list[dict[str, Any]] = []
    for source_index, message in enumerate(data.get("messages", [])):
        if not isinstance(message, dict):
            continue
        role = str(message.get("info", {}).get("role", "unknown"))
        for part_index, part in enumerate(message.get("parts", [])):
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "unknown"))
            if part_type == "tool":
                name = str(part.get("tool", "unknown"))
                state = part.get("state", {}) if isinstance(part.get("state", {}), dict) else {}
                events.append(_event("tool_call:" + name, role, part_type, source_index, part_index,
                                     tool_name=name, arguments=state.get("input", {}),
                                     tool_use_id=str(part.get("id", ""))))
                output = state.get("output", state.get("error", ""))
                events.append(_event("tool_result", "tool", "tool_result", source_index, part_index,
                                     tool_name=name, tool_use_id=str(part.get("id", "")), content=output))
            elif part_type in {"thinking", "reasoning"}:
                text = part.get("thinking", part.get("text", ""))
                events.append(_event(f"{role}_{part_type}", role, part_type, source_index, part_index,
                                     thinking=text, text=text))
            else:
                events.append(_event(f"{role}_text", role, part_type, source_index, part_index,
                                     text=part.get("text", "")))
    return events


def discover_trajectories(input_path: Path) -> list[dict[str, Any]]:
    paths = [input_path] if input_path.is_file() else sorted(
        path for suffix in ("*.jsonl", "*.json") for path in input_path.rglob(suffix)
    )
    if not paths:
        raise ValueError(f"No .json or .jsonl trajectories found under {input_path}")
    trajectories = []
    seen = set()
    for path in paths:
        try:
            if path.suffix.casefold() == ".jsonl":
                events = _parse_jsonl(path)
            else:
                payload = read_json(path)
                if isinstance(payload, dict) and isinstance(payload.get("trajectories"), list):
                    for item in payload["trajectories"]:
                        if not isinstance(item, dict) or not isinstance(item.get("events"), list):
                            continue
                        harness = str(item.get("harness") or path.parent.name)
                        sid = str(item.get("session_id") or path.stem)
                        key = f"{harness}__{sid}"
                        if key in seen:
                            raise ValueError(f"Duplicate trajectory id: {key}")
                        seen.add(key)
                        trajectories.append({"harness": harness, "session_id": sid, "events": item["events"],
                                             "source_file": str(path.resolve())})
                    continue
                events = _parse_opencode(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot parse trajectory {path}: {error}") from error
        if not events:
            continue
        harness, sid = path.parent.name, path.stem
        key = f"{harness}__{sid}"
        if key in seen:
            raise ValueError(f"Duplicate trajectory id: {key}")
        seen.add(key)
        trajectories.append({"harness": harness, "session_id": sid, "events": events,
                             "source_file": str(path.resolve())})
    if not trajectories:
        raise ValueError("No non-empty trajectories were found")
    return sorted(trajectories, key=lambda item: (item["harness"], item["session_id"]))


def select_trajectories(trajectories: list[dict[str, Any]], ratio: float, seed: int) -> list[dict[str, Any]]:
    if ratio >= 1:
        return trajectories
    selected = []
    for trajectory in trajectories:
        key = f"{seed}:{trajectory['harness']}__{trajectory['session_id']}".encode()
        score = int(hashlib.sha256(key).hexdigest()[:16], 16) / float(16 ** 16)
        if score < ratio:
            selected.append(trajectory)
    if not selected:
        selected.append(min(trajectories, key=lambda item: hashlib.sha256(
            f"{seed}:{item['harness']}__{item['session_id']}".encode()).hexdigest()))
    return selected


def write_trajectory_dataset(path: Path, trajectories: list[dict[str, Any]]) -> None:
    write_json(path, {"session_count": len(trajectories), "trajectories": [
        {key: value for key, value in trajectory.items() if key != "source_file"}
        for trajectory in trajectories
    ]})


def write_expanded_and_raw(root: Path, trajectories: list[dict[str, Any]]) -> tuple[Path, Path]:
    expanded = root / "expanded-sessions"
    raw_root = root / "raw-sessions"
    expanded.mkdir(parents=True, exist_ok=True)
    for trajectory in trajectories:
        harness, sid = trajectory["harness"], trajectory["session_id"]
        source = Path(trajectory.get("source_file", ""))
        raw_path = raw_root / harness / f"{sid}.jsonl"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        preserved = False
        if source.is_file() and source.suffix.casefold() == ".jsonl":
            shutil.copyfile(source, raw_path)
            preserved = True
        elif source.is_file() and source.suffix.casefold() == ".json":
            try:
                source_payload = read_json(source)
            except (OSError, ValueError, json.JSONDecodeError):
                source_payload = None
            if isinstance(source_payload, dict) and isinstance(source_payload.get("messages"), list):
                raw_path = raw_path.with_suffix(".json")
                shutil.copyfile(source, raw_path)
                preserved = True
        if not preserved:
            raw_path.write_text("".join(json.dumps(event, ensure_ascii=False) + "\n"
                                                for event in trajectory["events"]), encoding="utf-8")
        segment = expanded / f"{harness}__{sid}__segment-01.json"
        segment.write_text(json.dumps({"harness": harness, "session_id": sid,
                                       "source_file": f"{harness}/{sid}.jsonl",
                                       "events": trajectory["events"]}, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    write_json(expanded / "index.json", {"session_count": len(trajectories),
                                         "source": "trajectory_to_skills.py"})
    return expanded, raw_root


def embed_selected(trajectories: list[dict[str, Any]], output: Path, settings: dict[str, Any]) -> None:
    rows = []
    for trajectory in trajectories:
        for event_index, event in enumerate(trajectory["events"]):
            rows.append({"session_id": trajectory["session_id"], "harness": trajectory["harness"],
                         "event_index": event_index, "source_index": event.get("source_index"),
                         "category": event.get("category"), "input_text": embedder.event_to_text(event)})
    existing = {}
    if settings.get("resume") and output.is_file():
        existing = {(row["session_id"], row["event_index"]): row for row in
                    (json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip())}
    pending = [row for row in rows if (row["session_id"], row["event_index"]) not in existing]
    for start in range(0, len(pending), int(settings["batch_size"])):
        batch = pending[start:start + int(settings["batch_size"])]
        last_error = None
        for attempt in range(int(settings["retries"]) + 1):
            try:
                vectors = embedder.request_embeddings(
                    settings["base_url"], settings["api_key"], settings["model"],
                    [row["input_text"] for row in batch], settings.get("dimensions"), int(settings["timeout"]))
                last_error = None
                break
            except (OSError, RuntimeError, ValueError) as error:
                last_error = error
                if attempt < int(settings["retries"]):
                    time.sleep(float(settings["sleep_seconds"]) * (attempt + 1))
        if last_error is not None:
            raise RuntimeError(f"embedding batch starting at {start} failed") from last_error
        if len(vectors) != len(batch):
            raise ValueError("Embedding service returned a different number of vectors")
        for row, vector in zip(batch, vectors):
            existing[(row["session_id"], row["event_index"])] = {**row, "embedding": vector}
    if len(existing) != len(rows):
        raise ValueError("Embedding output is incomplete")
    ordered = [existing[(row["session_id"], row["event_index"])] for row in rows]
    write_jsonl(output, ordered)
    write_json(output.with_suffix(".meta.json"), {"event_count": len(ordered),
        "session_count": len(trajectories), "ratio": settings["ratio"], "seed": settings["seed"],
        "model": settings["model"], "dimensions": settings.get("dimensions"),
        "representation": "serialized complete normalized event fields"})


def run_segmentation(dataset: Path, embeddings: Path, output: Path, slices: Path, settings: dict[str, Any]) -> None:
    args = [sys.executable, str(HERE / "calibrated_confidence_segmentation.py"),
            "--input", str(dataset), "--embeddings", str(embeddings), "--output", str(output),
            "--output-dir", str(slices), "--windows", ",".join(map(str, settings["windows"])),
            "--fdr", str(settings["fdr"]), "--min-stability", str(settings["min_stability"]),
            "--min-gap", str(settings["min_gap"]), "--min-segment", str(settings["min_segment"]),
            "--overlap-events", str(settings["overlap_events"]), "--max-splits", str(settings["max_splits"]),
            "--length-bands", str(settings["length_bands"])]
    subprocess.run(args, cwd=str(HERE), check=True)


def copy_skill_outputs(extraction_root: Path, destination: Path, manifest: dict[str, Any], logical_arm: str) -> list[dict[str, Any]]:
    destination.mkdir(parents=True, exist_ok=True)
    legacy_arm = LEGACY_ARMS[logical_arm]
    index_path = extraction_root / "skill-index.jsonl"
    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = [entry for entry in entries if entry.get("arm") == legacy_arm]
    output_entries = []
    for entry in entries:
        source = Path(entry["markdown_path"])
        target = destination / entry["name"] / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError(f"Skill name collision with different content: {entry['name']}")
        if not target.exists():
            shutil.copyfile(source, target)
        output_entries.append({**entry, "arm": logical_arm, "markdown_path": str(target.resolve()),
                               "source_group_id": entry.get("group_id")})
    write_jsonl(destination.parent / f"{logical_arm}-skill-index.jsonl", output_entries)
    return output_entries


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if "key" in key.casefold() or "token" in key.casefold() else redact(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def run(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = load_config(config_path)
    output = Path(config["output"])
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output already exists and is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    stages = output / "stages"
    trajectories = discover_trajectories(Path(config["input"]))
    selected = select_trajectories(trajectories, config["embedding"]["ratio"], config["embedding"]["seed"])
    write_trajectory_dataset(stages / "trajectories.json", trajectories)
    write_trajectory_dataset(stages / "selected-trajectories.json", selected)
    expanded, raw_root = write_expanded_and_raw(stages, selected)

    embedding_path = stages / "embeddings.jsonl"
    embed_selected(selected, embedding_path, config["embedding"])
    segmentation_output = stages / "segmentation.json"
    slices = stages / "slices"
    run_segmentation(stages / "selected-trajectories.json", embedding_path, segmentation_output, slices,
                     config["segmentation"])

    strategy = config["clustering"]["strategy"]
    cluster_output = stages / "clustering"
    clustering_summary = clustering.run(expanded, slices, cluster_output, strategies=(strategy,))
    group_path = cluster_output / f"sessions-{len(selected)}" / strategy / "groups.json"

    extraction_root = stages / "extraction"
    extraction_config = config["extraction"]
    logical_inputs = extraction_config["inputs"]
    legacy_inputs = [LEGACY_ARMS[item] for item in logical_inputs]
    if group_path.is_file() and read_json(group_path):
        prepared = extraction.prepare(group_path, slices, raw_root, extraction_root,
                                      Path(extraction_config["prompt"]), extraction_config["selection_strategy"],
                                      arms=legacy_inputs)
        if extraction_config.get("prepare_only", False):
            extraction_summary = {"status": "prepared", "manifest": prepared}
        else:
            extraction_summary = extraction.run_prepared(extraction_root, extraction_config["api"])
    else:
        extraction_root.mkdir(parents=True, exist_ok=True)
        write_jsonl(extraction_root / "skill-index.jsonl", [])
        extraction_summary = {"status": "no_groups", "candidate_count": 0}

    primary = extraction_config["primary_input"]
    primary_entries = []
    if extraction_summary.get("status") != "prepared":
        primary_entries = copy_skill_outputs(extraction_root, output / "skills", extraction_summary, primary)
        for logical in logical_inputs:
            if logical != primary:
                copy_skill_outputs(extraction_root, output / "alternatives" / logical, extraction_summary, logical)
    manifest = {"pipeline_version": "trajectory-to-skills-v1", "status": extraction_summary.get("status"),
                "config": redact(config), "input_trajectory_count": len(trajectories),
                "embedded_trajectory_count": len(selected), "strategy": strategy,
                "selected_inputs": logical_inputs, "primary_input": primary,
                "skill_count": len(primary_entries), "stages": {
                    "trajectories": str((stages / "trajectories.json").resolve()),
                    "selected_trajectories": str((stages / "selected-trajectories.json").resolve()),
                    "embeddings": str(embedding_path.resolve()), "segmentation": str(segmentation_output.resolve()),
                    "slices": str(slices.resolve()), "clustering": str(cluster_output.resolve()),
                    "extraction": str(extraction_root.resolve())},
                "clustering_summary": clustering_summary, "extraction_summary": extraction_summary}
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    try:
        result = run()
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"trajectory_to_skills failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "skills": result["skill_count"],
                      "output": result["config"]["output"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
