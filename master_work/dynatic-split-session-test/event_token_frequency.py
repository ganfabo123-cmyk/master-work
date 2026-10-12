"""Local, deterministic per-event token counts for materialized slices."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from token_frequency import tokenize


def argument_values(value: Any):
    """Count argument values, not schema keys or event metadata."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from argument_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from argument_values(child)
    elif value is not None:
        yield json.dumps(value)


def count_event(event: dict, include_symbols: bool = False) -> dict:
    fields = {}
    if isinstance(event.get("text"), str):
        fields["text"] = [event["text"]]
    if "arguments" in event:
        fields["arguments"] = list(argument_values(event["arguments"]))
    frequencies = {}
    total = Counter()
    for field, values in fields.items():
        counter = Counter()
        for value in values:
            counter.update(tokenize(value, include_symbols=include_symbols))
        frequencies[field] = dict(counter.most_common())
        total.update(counter)
    return {
        "payload_status": "present" if any(v for values in fields.values() for v in values) else "empty_payload" if fields else "payload_not_exported",
        "counted_fields": list(fields),
        "character_count": sum(len(v) for values in fields.values() for v in values),
        "token_count": total.total(),
        "unique_token_count": len(total),
        "field_token_frequencies": frequencies,
        "token_frequencies": dict(total.most_common()),
    }


def write_json(path: Path, data: Any):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(slices_dir: Path, output: Path, include_symbols: bool = False):
    files = sorted(slices_dir.rglob("segment-*.json"))
    if not files:
        raise ValueError(f"No segment files: {slices_dir}")
    output.mkdir(parents=True, exist_ok=True)
    seen = {}
    mappings = []
    totals = defaultdict(Counter)
    document_frequencies = defaultdict(Counter)
    categories = Counter()
    statuses = Counter()
    memberships = 0
    with (output / "events.jsonl").open("w", encoding="utf-8") as stream:
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            session = path.parent.name
            events = data["events"]
            if data["end_event"] - data["start_event"] + 1 != len(events):
                raise ValueError(f"Invalid event range: {path}")
            refs = []
            for offset, event in enumerate(events):
                index = data["start_event"] + offset
                event_id = f"{session}::event-{index}"
                fingerprint = hashlib.sha256(json.dumps(event, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                refs.append(event_id)
                memberships += 1
                if event_id in seen:
                    if seen[event_id] != fingerprint:
                        raise ValueError(f"Conflicting overlapping event: {event_id}")
                    continue
                seen[event_id] = fingerprint
                counts = count_event(event, include_symbols)
                category = event.get("category", "unknown")
                row = {
                    "event_id": event_id, "session_key": session,
                    "event_index": index,
                    "source_index": event.get("source_index"),
                    "source_part_index": event.get("source_part_index"),
                    "category": category, "role": event.get("role"),
                    "part_type": event.get("part_type"),
                    "tool_name": event.get("tool_name"),
                    **counts,
                }
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                categories[category] += 1
                statuses[counts["payload_status"]] += 1
                totals[category].update(counts["token_frequencies"])
                document_frequencies[category].update(counts["token_frequencies"].keys())
            mappings.append({
                "slice_id": f"{session}__{path.stem}",
                "source_file": str(path.resolve()),
                "start_event": data["start_event"], "end_event": data["end_event"],
                "core_start_event": data.get("core_start_event"),
                "core_end_event": data.get("core_end_event"),
                "event_ids": refs,
            })
    write_json(output / "slice-events.json", mappings)
    write_json(output / "by-category.json", {
        category: {
            "event_count": categories[category],
            "token_count": totals[category].total(),
            "token_frequencies": dict(totals[category].most_common()),
            "event_document_frequency": dict(document_frequencies[category].most_common()),
        } for category in sorted(categories)
    })
    summary = {
        "slice_count": len(files), "session_count": len({p.parent.name for p in files}),
        "event_occurrences_in_slices": memberships, "unique_event_count": len(seen),
        "overlap_occurrences_deduplicated": memberships - len(seen),
        "token_count": sum(c.total() for c in totals.values()),
        "events_by_category": dict(categories), "events_by_payload_status": dict(statuses),
        "tokenizer": "token_frequency.tokenize; regex tokens, not model tokens; case-sensitive; contiguous CJK runs",
        "include_symbols": include_symbols,
        "counting_policy": "text and recursive argument values counted separately and combined; no metadata, argument keys, or tool names counted",
        "deduplication": "session directory + 1-based trajectory event index; duplicate payload equality checked",
        "source_root": str(slices_dir.resolve()),
    }
    write_json(output / "summary.json", summary)
    (output / "README.md").write_text(
        "# 事件级词频统计\n\n"
        f"{len(files)} 个切片，{len(seen)} 个去重事件。\n\n"
        "- `events.jsonl`：一行一个事件，保留源位置、类型、正文和参数各自词频及合计。\n"
        "- `slice-events.json`：切片到有序事件 ID 的映射，含核心区间与重叠区间位置。\n"
        "- `by-category.json`：按精确事件类型汇总词频和词出现的事件数，均排除 overlap 重复。\n"
        "- `summary.json`：数量、分词规则、统计口径和输入目录。\n\n"
        "正文与工具参数值计数；参数键、工具名、角色、事件类型等只作元数据，不混入词频。"
        "默认不计独立符号，保留大小写，中文连续字符为一项；token 是正则词项，不是模型 token。"
        "`payload_not_exported` 表示事件没有可统计字段，不代表原始行为没有内容。"
        "本次输入的工具返回及多数 thinking 事件没有导出正文。\n",
        encoding="utf-8",
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slices-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-symbols", action="store_true")
    args = parser.parse_args()
    result = run(args.slices_dir, args.output, args.include_symbols)
    print(json.dumps({k: result[k] for k in ("slice_count", "unique_event_count", "overlap_occurrences_deduplicated", "token_count")}))


if __name__ == "__main__":
    main()
