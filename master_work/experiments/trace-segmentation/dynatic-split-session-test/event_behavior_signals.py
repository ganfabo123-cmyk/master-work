"""Rank cheap, auditable task signals from event-level token frequencies."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

from token_frequency import tokenize


STOP_WORDS = set("""
a an and are as at be been but by can could did do does for from had has have
here how i if in into is it its me my no not of on or our out so that the
their them there these this those to us was we were what when where which who
will with would you your also all any each every just more most much now one
other some such than then they very via while yet
""".split())
ACTION_WORDS = set("""
add build commit configure create debug deploy edit fix generate implement install
migrate optimize patch push refactor remove repair replace resolve review run search
test update validate verify write
""".split())
CHANNELS = ("user", "assistant", "unknown", "tool")
CHANNEL_WEIGHTS = {"user": 2.0, "assistant": 1.5, "unknown": 1.0, "tool": 0.6}
CHANNEL_CAPS = {"user": 3, "assistant": 6, "unknown": 6, "tool": 8}


def channel(category: str) -> str | None:
    if category == "user_text":
        return "user"
    if category == "assistant_text":
        return "assistant"
    if category == "unknown_text":
        return "unknown"
    if category.startswith("tool_call:"):
        return "tool"
    return None


def useful(token: str) -> bool:
    if token in STOP_WORDS or len(token) < 2 or token.isnumeric():
        return False
    if re.fullmatch(r"\d+(?:\.\d+)+", token):
        return False
    if len(token) >= 5 and re.fullmatch(r"[a-f0-9]+", token) and any(char.isdigit() for char in token):
        return False
    if token.startswith("http") or len(token) > 48:
        return False
    return True


def load_events(path: Path) -> dict[str, dict]:
    events = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            events[event["event_id"]] = event
    return events


def collect_slice(mapping: dict, events: dict[str, dict]) -> dict:
    frequencies = {name: Counter() for name in CHANNELS}
    tool_calls = Counter()
    transitions = Counter()
    previous_tool = None
    counts = Counter()
    core_start = mapping.get("core_start_event") or mapping["start_event"]
    core_end = mapping.get("core_end_event") or mapping["end_event"]
    for event_id in mapping["event_ids"]:
        event = events[event_id]
        if not core_start <= event["event_index"] <= core_end:
            continue
        counts["events"] += 1
        name = channel(event["category"])
        if name is None:
            continue
        counts[name] += 1
        if name == "tool":
            tool = event["tool_name"] or event["category"].removeprefix("tool_call:")
            tool_calls[tool] += 1
            if previous_tool is not None:
                transitions[(previous_tool, tool)] += 1
            previous_tool = tool
        # One vote per event; a pasted document cannot multiply its own weight.
        frequencies[name].update({token.casefold() for token in event["token_frequencies"]})
    return {
        "slice_id": mapping["slice_id"],
        "source_file": mapping["source_file"],
        "core_start_event": core_start,
        "core_end_event": core_end,
        "event_counts": dict(counts),
        "event_frequency": frequencies,
        "tool_calls": dict(tool_calls.most_common()),
        "tool_transitions": [
            {"from": first, "to": second, "count": count}
            for (first, second), count in transitions.most_common(12)
        ],
    }


def rank_signals(slices: list[dict]) -> tuple[list[dict], Counter]:
    slice_df = Counter()
    for row in slices:
        slice_df.update(set().union(*(set(row["event_frequency"][c]) for c in CHANNELS)))
    total_slices = len(slices)
    for row in slices:
        frequencies = row.pop("event_frequency")
        all_tokens = set().union(*(set(frequencies[c]) for c in CHANNELS))
        signals = []
        for token in all_tokens:
            evidence = {name: frequencies[name][token] for name in CHANNELS}
            event_count = sum(evidence.values())
            if not useful(token) or event_count < (3 if len(token) == 2 else 2):
                continue
            support = sum(
                CHANNEL_WEIGHTS[name] * min(evidence[name], CHANNEL_CAPS[name])
                for name in CHANNELS
            )
            channel_count = sum(bool(evidence[name]) for name in CHANNELS)
            idf = 1 + math.log((total_slices + 1) / (slice_df[token] + 1))
            score = math.log1p(support) * idf * (1 + 0.35 * (channel_count - 1))
            signals.append({
                "token": token,
                "score": round(score, 3),
                "slice_document_frequency": slice_df[token],
                "event_frequency": evidence,
            })
        signals.sort(key=lambda s: (-s["score"], -sum(s["event_frequency"].values()), s["token"]))
        row["task_signals"] = [s for s in signals if any(s["event_frequency"][c] for c in ("user", "assistant", "unknown"))][:20]
        row["tool_only_signals"] = [s for s in signals if not any(s["event_frequency"][c] for c in ("user", "assistant", "unknown"))][:10]
        row["action_terms"] = [s for s in signals if s["token"] in ACTION_WORDS and (s["event_frequency"]["user"] or s["event_frequency"]["assistant"])][:12]
    return slices, slice_df


def add_action_object_pairs(rows: list[dict], mappings: list[dict]) -> None:
    for row, mapping in zip(rows, mappings, strict=True):
        objects = {signal["token"] for signal in row["task_signals"][:20]} - ACTION_WORDS
        pair_events = defaultdict(Counter)
        source = json.loads(Path(mapping["source_file"]).read_text(encoding="utf-8"))
        for offset, event in enumerate(source["events"]):
            event_index = mapping["start_event"] + offset
            if not row["core_start_event"] <= event_index <= row["core_end_event"]:
                continue
            name = channel(event["category"])
            if name not in ("user", "assistant", "unknown"):
                continue
            words = [token.casefold() for token in tokenize(event.get("text", ""), include_symbols=False)]
            found = set()
            for index, action in enumerate(words):
                if action not in ACTION_WORDS:
                    continue
                for obj in words[max(0, index - 6):index + 7]:
                    if obj in objects:
                        found.add((action, obj))
            for pair in found:
                pair_events[pair][name] += 1
        pairs = []
        for (action, obj), evidence in pair_events.items():
            if evidence.total() < 2:
                continue
            score = sum(CHANNEL_WEIGHTS[name] * min(evidence[name], CHANNEL_CAPS[name]) for name in evidence)
            pairs.append({"action": action, "object": obj, "event_frequency": dict(evidence), "score": round(score, 2)})
        pairs.sort(key=lambda pair: (-pair["score"], -sum(pair["event_frequency"].values()), pair["action"], pair["object"]))
        row["action_object_pairs"] = pairs[:12]


def run(input_dir: Path, output_dir: Path) -> dict:
    events = load_events(input_dir / "events.jsonl")
    mappings = json.loads((input_dir / "slice-events.json").read_text(encoding="utf-8"))
    rows, slice_df = rank_signals([collect_slice(mapping, events) for mapping in mappings])
    add_action_object_pairs(rows, mappings)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "slice-signals.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "slice_count": len(rows),
        "input_event_count": len(events),
        "core_event_count": sum(row["event_counts"].get("events", 0) for row in rows),
        "slices_without_user_text": sum(not row["event_counts"].get("user", 0) for row in rows),
        "slices_with_unknown_text": sum(bool(row["event_counts"].get("unknown", 0)) for row in rows),
        "slices_with_task_signals": sum(bool(row["task_signals"]) for row in rows),
        "global_slice_document_frequency": dict(slice_df.most_common()),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 事件证据特征词", "", "核心区间内的事件参与统计；重叠事件不跨切片重复计分。", "", "| 切片 | 任务相关特征词（前 8） | 同事件动作+对象（前 4） | 工具调用（前 5） |", "|---|---|---|---|"]
    for row in rows:
        terms = ", ".join(s["token"] for s in row["task_signals"][:8]) or "—"
        actions = ", ".join(f"{s['action']}+{s['object']}" for s in row["action_object_pairs"][:4]) or "—"
        tools = ", ".join(f"{name}:{count}" for name, count in list(row["tool_calls"].items())[:5]) or "—"
        lines.append(f"| `{row['slice_id']}` | {terms} | {actions} | {tools} |")
    (output_dir / "slice-signals.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# 低成本事件证据信号\n\n"
        "读取 event-token-frequency/events.jsonl 与 slice-events.json；无需模型或 embedding。\n"
        "每个词在一个事件内最多计一次，大小写合并；仅用切片核心区间。"
        "按 user、assistant、unknown、tool 四通道计事件数，单通道计分封顶，再乘跨切片 IDF 与跨通道奖励。"
        "unknown_text 角色未明，单列通道，不能推断为用户输入。"
        "要求至少两个事件支持，双字词至少三个；常见英文虚词、纯数字、版本号、短十六进制串和过长词不参与排序。\n\n"
        "`task_signals` 至少出现于 user、assistant 或 unknown；`tool_only_signals` 单列工具参数词。"
        "`action_terms` 是固定英文动词列表的命中情况，不是行为标签。"
        "`action_object_pairs` 要求动作词与候选特征词在文本中相距至多 6 个词项，且至少有两个事件支持；"
        "仅表示邻近，不表示语法关系或实际执行。"
        "工具调用类型及相邻工具调用转移直接计数。"
        "词频仅给出候选证据，不能单独证明任务完成或动作成功。"
        "中文仍沿用原始连续汉字分词，尚未做词语切分。\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = run(args.input_dir, args.output_dir)
    print(json.dumps({key: summary[key] for key in ("slice_count", "core_event_count", "slices_with_task_signals")}))


if __name__ == "__main__":
    main()
