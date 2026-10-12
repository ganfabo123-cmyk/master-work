#!/usr/bin/env python3
"""Analyze the opening event and first sentence of materialized raw slices.

This script deliberately reads only the raw slice files referenced by the
token-stat records.  It never reconstructs text from token frequencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable


TEXT_KEYS = ("text", "content", "message", "body", "input", "value")
ROLE_KEYS = ("role", "speaker", "author_role", "source_role", "sender_role")
META_KINDS = {"metadata", "meta", "header", "system", "init", "snapshot", "trace_metadata"}
# Require whitespace/end after Latin punctuation; this preserves v1.2/path.py.
SENTENCE_END = re.compile(r"(?:(?<=[。！？])|(?<=[.!?])(?=\s|$))[\"'”’）)】]*\s*")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        pieces = [text_value(item) for item in value]
        return "\n".join(piece for piece in pieces if piece)
    if isinstance(value, dict):
        for key in ("text", "content", "value", "input"):
            if key in value:
                result = text_value(value[key])
                if result:
                    return result
    return ""


def role_of(record: dict[str, Any]) -> str | None:
    for key in ROLE_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    for key in ("message", "event", "data"):
        value = record.get(key)
        if isinstance(value, dict):
            role = role_of(value)
            if role:
                return role
    return None


def kind_of(record: dict[str, Any]) -> str | None:
    for key in ("event_type", "type", "kind", "record_type"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    category = record.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip().lower()
    return None


def text_of(record: dict[str, Any]) -> str:
    # A message envelope is common in JSONL exports; inspect it first.
    for key in TEXT_KEYS:
        if key in record:
            value = record[key]
            if isinstance(value, dict) and key == "message":
                value = value.get("content", value.get("text", ""))
            result = text_value(value)
            if result:
                return result
    return ""


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    """Yield event-like dicts without treating token-frequency maps as events."""
    if isinstance(value, list):
        for item in value:
            yield from iter_records(item)
        return
    if not isinstance(value, dict):
        return
    for key in ("events", "messages", "records", "trace", "items", "data"):
        child = value.get(key)
        if isinstance(child, (list, dict)):
            yielded = list(iter_records(child))
            if yielded:
                yield from yielded
                return
    if text_of(value) or role_of(value) or kind_of(value):
        yield value


def first_sentence(text: str) -> str | None:
    clean = " ".join(text.split())
    if not clean:
        return None
    match = SENTENCE_END.search(clean)
    return clean[: match.start()].strip() if match else clean


def is_metadata(record: dict[str, Any]) -> bool:
    kind = kind_of(record)
    if kind in META_KINDS or (kind and kind.startswith("record:")):
        return True
    # System messages are metadata for the requested user-input distinction.
    return role_of(record) == "system"


def is_user(record: dict[str, Any]) -> bool:
    # Exported tool results may use the user protocol role. The explicit
    # trajectory category is authoritative for actual user text.
    category = record.get("category")
    if isinstance(category, str) and category.strip():
        return category.strip().lower() == "user_text"
    role = role_of(record)
    kind = kind_of(record) or ""
    if kind in {"tool_result", "tool_use", "tool_call"} or kind.startswith("tool_call:"):
        return False
    return role in {"user", "human"} or kind in {"user_text", "user_input", "user-message", "user_message", "input"}


def resolve_source(source_file: str, stats_path: Path, roots: list[Path]) -> Path | None:
    normalized = source_file.replace("\\", "/")
    candidates = [Path(source_file), Path(normalized)]
    for root in [stats_path.parent, *roots]:
        candidates.extend((root / candidate for candidate in (Path(source_file), Path(normalized))))
        # The source path is often relative to the experiment directory.
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def analyze(stat_path: Path, roots: list[Path]) -> dict[str, Any]:
    stat = load(stat_path)
    source_name = str(stat.get("source_file", ""))
    source = resolve_source(source_name, stat_path, roots) if source_name else None
    base = {
        "slice_file": str(stat_path),
        "source_file": source_name,
        "source_path": str(source) if source else None,
        "segment_index": stat.get("segment_index"),
    }
    if source is None:
        return {**base, "status": "missing_source", "event_count": None,
                "first_event_type": None, "first_event_category": None, "first_event_role": None,
                "first_event_is_user_input": None, "first_event_text": None,
                "first_body_event_type": None, "first_body_event_category": None, "first_body_event_role": None,
                "first_body_is_user_input": None, "first_sentence": None,
                "first_sentence_role": None, "first_sentence_event_position": None,
                "first_user_input_sentence": None, "first_user_input_event_position": None}
    try:
        records = list(iter_records(load(source)))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        return {**base, "status": "unreadable_source", "error": str(exc), "event_count": None}
    # Metadata can carry text (titles, snapshots, system records), so exclude
    # it from the substantive-body opening while retaining the true first event.
    body = [record for record in records if text_of(record) and not is_metadata(record)]
    first = records[0] if records else {}
    first_body_index = next((index for index, record in enumerate(records) if text_of(record) and not is_metadata(record)), None)
    first_body = records[first_body_index] if first_body_index is not None else {}
    user_records = [(index, record) for index, record in enumerate(records) if text_of(record) and not is_metadata(record) and is_user(record)]
    first_user = user_records[0][1] if user_records else {}
    first_user_pos = user_records[0][0] + 1 if user_records else None
    sentence_record = first_body
    return {**base, "status": "ok", "event_count": len(records), "body_event_count": len(body),
            "first_event_type": kind_of(first), "first_event_category": first.get("category"), "first_event_role": role_of(first),
            "first_event_is_user_input": is_user(first), "first_event_text": text_of(first) or None,
            "first_body_event_type": kind_of(first_body), "first_body_event_category": first_body.get("category"), "first_body_event_role": role_of(first_body),
            "first_body_is_user_input": is_user(first_body),
            "first_sentence": first_sentence(text_of(sentence_record)),
            "first_sentence_role": role_of(sentence_record),
            "first_sentence_event_position": first_body_index + 1 if first_body_index is not None else None,
            "first_user_input_sentence": first_sentence(text_of(first_user)) if first_user else None,
            "first_user_input_event_position": first_user_pos}


def write_outputs(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "slice-opening-analysis.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = sorted({key for row in rows for key in row})
    with (output_dir / "slice-opening-analysis.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    total = len(rows)
    ok = [row for row in rows if row.get("status") == "ok"]
    summary = {
        "total_stat_slices": total,
        "source_available": len(ok),
        "source_missing_or_unreadable": total - len(ok),
        "first_event_is_user_input": sum(row.get("first_event_is_user_input") is True for row in ok),
        "first_body_event_is_user_input": sum(row.get("first_body_is_user_input") is True for row in ok),
        "first_sentence_available": sum(bool(row.get("first_sentence")) for row in ok),
        "first_user_input_sentence_available": sum(bool(row.get("first_user_input_sentence")) for row in ok),
        "first_event_user_input_rate": (sum(row.get("first_event_is_user_input") is True for row in ok) / len(ok)) if ok else None,
        "first_body_user_input_rate": (sum(row.get("first_body_is_user_input") is True for row in ok) / len(ok)) if ok else None,
        "all_available_first_events_are_user_input": (all(row.get("first_event_is_user_input") is True for row in ok)) if ok else None,
        "all_available_first_body_events_are_user_input": (all(row.get("first_body_is_user_input") is True for row in ok)) if ok else None,
        "missing_source_files": [row["source_file"] for row in rows if row.get("status") != "ok"],
        "method": "raw source JSON only; no token-frequency reconstruction",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Slice opening analysis", "", f"- Total token-stat slices: {total}", f"- Raw sources available: {len(ok)}", f"- Missing/unreadable raw sources: {total-len(ok)}", "- Method: raw source JSON only; token frequencies are never used.", ""]
    if summary["missing_source_files"]:
        lines += ["## Missing source files", ""] + [f"- `{item}`" for item in summary["missing_source_files"]]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats-dir", type=Path, default=base / "token-frequency-banded-v3-exclusive-no-symbols" / "segments")
    parser.add_argument("--output-dir", type=Path, default=base / "slice-opening-analysis")
    parser.add_argument("--source-root", action="append", type=Path, default=[])
    args = parser.parse_args()
    stat_paths = sorted(args.stats_dir.resolve().glob("*.json"))
    roots = [base, base.parent, Path.cwd(), *[path.resolve() for path in args.source_root]]
    rows = [analyze(path, roots) for path in stat_paths]
    write_outputs(rows, args.output_dir.resolve())
    print(json.dumps({"total": len(rows), "ok": sum(row.get("status") == "ok" for row in rows), "output": str(args.output_dir.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
