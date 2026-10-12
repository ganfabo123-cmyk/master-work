"""Create compact, evidence-preserving traces for Skill extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
LONG_ID = re.compile(r"\b(?:toolu|call|run|sess|session)[_-][A-Za-z0-9_-]{12,}\b", re.I)
ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/Users/|/home/|/tmp/)[^\s`\"']+")
LONG_NUMBER = re.compile(r"\b\d{6,}\b")
CODE_BLOCK = re.compile(r"```[^\n]*\n.*?```", re.S)


def normalize(value: str) -> str:
    value = UUID.sub("<UUID>", value)
    value = LONG_ID.sub("<ID>", value)
    value = ABS_PATH.sub(lambda m: Path(m.group(0).replace("\\", "/")).name or "<PATH>", value)
    return LONG_NUMBER.sub("<N>", value)


def shorten_text(text: str, limit: int = 1200) -> str:
    text = normalize(text.strip())
    # Source code and generated documents are valuable only through their file/action context.
    text = CODE_BLOCK.sub("[code omitted]", text)
    if len(text) <= limit:
        return text
    return text[: limit // 2].rstrip() + " ... [text omitted] ... " + text[-limit // 2 :].lstrip()


def argument_summary(event: dict) -> dict:
    args = event.get("arguments") or {}
    if not isinstance(args, dict):
        return {"arguments": shorten_text(str(args), 500)}
    keep = {}
    for key, value in args.items():
        key_l = str(key).lower()
        if key_l in {"file_path", "path", "pattern", "query", "command", "description", "replace_all", "old_string", "new_string"}:
            if key_l in {"old_string", "new_string"}:
                keep[key] = f"<text length={len(str(value))}>"
            elif key_l == "command":
                keep[key] = shorten_text(str(value), 500)
            else:
                keep[key] = shorten_text(str(value), 300)
        elif key_l in {"todos", "task", "tasks"}:
            keep[key] = shorten_text(json.dumps(value, ensure_ascii=False), 700)
    return keep


def clean_event(event: dict) -> tuple[dict | None, str]:
    category = str(event.get("category", "unknown"))
    if category.startswith("record:"):
        return None, "record_metadata"
    if category == "tool_result":
        result_text = event.get("text") or event.get("content")
        if result_text:
            return {"kind": "tool_result", "text": shorten_text(str(result_text), 900)}, "kept_tool_result"
        # The export normally has no result body; retaining the marker adds no Skill evidence.
        return None, "empty_tool_result"
    if category in {"user_text", "assistant_text"}:
        text = shorten_text(str(event.get("text", "")))
        if not text:
            return None, "empty_text"
        return {"kind": "user" if category == "user_text" else "assistant", "text": text}, "kept_text"
    if category.startswith("tool_call:"):
        return {"kind": "tool", "tool": event.get("tool_name") or category.split(":", 1)[1], "arguments": argument_summary(event)}, "kept_tool_call"
    if isinstance(event.get("text"), str) and event["text"].strip():
        return {"kind": category, "text": shorten_text(event["text"])}, "kept_other_text"
    return None, "unusable_event"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slices-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.slices_dir.rglob("segment-*.json"))
    args.output.mkdir(parents=True, exist_ok=True)
    stats = Counter(); rows = []
    for source in files:
        data = json.loads(source.read_text(encoding="utf-8")); cleaned = []
        previous_hash = None
        for event in data.get("events", []):
            item, reason = clean_event(event); stats[reason] += 1
            if item is None:
                continue
            digest = hashlib.sha1(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if digest == previous_hash:
                stats["duplicate_event"] += 1
                continue
            previous_hash = digest; cleaned.append(item)
        sid = f"{source.parent.name}__{source.stem}"
        row = {"slice_id": sid, "source_file": str(source), "original_event_count": len(data.get("events", [])), "cleaned_event_count": len(cleaned), "events": cleaned}
        (args.output / f"{sid}.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rows.append({k: row[k] for k in ("slice_id", "original_event_count", "cleaned_event_count")})
    summary = {"algorithm_version": "skill-trace-cleaning-v1", "slice_count": len(rows), "event_stats": dict(stats), "input_event_count": sum(x["original_event_count"] for x in rows), "cleaned_event_count": sum(x["cleaned_event_count"] for x in rows), "policy": "drop metadata records and empty tool results; preserve user/assistant intent, tool names, paths/commands, task lists; redact IDs/absolute paths and truncate code-heavy text"}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
