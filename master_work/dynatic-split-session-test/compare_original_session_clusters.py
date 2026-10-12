#!/usr/bin/env python3
"""Cluster complete sessions and compare them with slice-domain membership.

The experiment deliberately keeps the existing slice clustering immutable. It
creates one token-frequency document per original session, runs the same
unsupervised domain-graph implementation, then expands session clusters back
to their associated slices for set-level comparison.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from token_frequency import load_segment, segment_key
from unsupervised_domain_graph import discover


SESSION_ID_RE = re.compile(r"(?:^|__)claude_code__(.+)$")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def text_event(role: str, text: str, source_index: int) -> dict[str, Any]:
    return {
        "category": f"{role}_text",
        "role": role,
        "part_type": "text",
        "source_index": source_index,
        "text": text,
    }


def parse_claude_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for source_index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message", {})
        role = message.get("role") or record.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "tool", "system"}:
            continue
        if isinstance(content, str) and content.strip():
            events.append(text_event(role, content, source_index))
            continue
        if not isinstance(content, list):
            continue
        for part_index, part in enumerate(content):
            if not isinstance(part, dict):
                continue
            part_type = part.get("type")
            if part_type == "text" and isinstance(part.get("text"), str) and part["text"].strip():
                event = text_event(role, part["text"], source_index)
                event["source_part_index"] = part_index
                events.append(event)
            elif role == "assistant" and part_type == "tool_use":
                # Keep the operation category for traceability, but do not add
                # tool names or arguments to text. This matches token_frequency
                # on the existing materialized slices, which counts text keys.
                events.append({
                    "category": f"tool_call:{part.get('name', 'unknown')}",
                    "role": role,
                    "part_type": part_type,
                    "source_index": source_index,
                    "source_part_index": part_index,
                })
    return events


def parse_opencode_json(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    events: list[dict[str, Any]] = []
    for message_index, message in enumerate(payload.get("messages", [])):
        info = message.get("info", {})
        role = info.get("role")
        for part_index, part in enumerate(message.get("parts", [])):
            part_type = part.get("type")
            if part_type in {"text", "reasoning"} and isinstance(part.get("text"), str) and part["text"].strip():
                event = text_event(role or "unknown", part["text"], message_index)
                event["part_type"] = part_type
                event["source_part_index"] = part_index
                events.append(event)
            elif role == "assistant" and part_type == "tool":
                events.append({
                    "category": f"tool_call:{part.get('tool', 'unknown')}",
                    "role": role,
                    "part_type": part_type,
                    "source_index": message_index,
                    "source_part_index": part_index,
                })
    return events


def session_key(path: Path) -> str:
    harness = path.parent.name
    return f"{harness}__{path.stem}"


def build_session_inputs(raw_root: Path, output: Path) -> dict[str, Any]:
    input_root = output / "raw-session-inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    sessions: list[dict[str, Any]] = []
    for path in sorted(raw_root.rglob("*.jsonl")) + sorted(raw_root.rglob("*.json")):
        if path.name == ".gitkeep":
            continue
        key = session_key(path)
        events = parse_claude_jsonl(path) if path.suffix == ".jsonl" else parse_opencode_json(path)
        if not events:
            continue
        session_dir = input_root / key
        session_dir.mkdir(parents=True, exist_ok=True)
        input_path = session_dir / "segment-01.json"
        input_path.write_text(json.dumps({
            "session_id": path.stem,
            "harness": path.parent.name,
            "segment_index": 1,
            "start_event": 1,
            "end_event": len(events),
            "events": events,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sessions.append({
            "session_key": key,
            "source_file": str(path),
            "input_file": str(input_path),
            "event_count": len(events),
            "text_event_count": sum("text" in event for event in events),
        })
    (output / "session-input-manifest.json").write_text(
        json.dumps({"session_count": len(sessions), "sessions": sessions}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {row["session_key"]: row for row in sessions}


def load_assignments(path: Path) -> dict[str, list[dict[str, Any]]]:
    return read_json(path)


def assignment_domains(
    assignments: dict[str, list[dict[str, Any]]],
    *,
    primary_only: bool = False,
    normalize_session_members: bool = False,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for member, rows in assignments.items():
        selected = rows[:1] if primary_only else rows
        normalized = member
        if normalize_session_members:
            parts = member.split("__")
            if parts[-1].startswith("segment-"):
                normalized = "__".join(parts[:-1])
                if normalized.startswith("segments__"):
                    normalized = normalized[len("segments__"):]
        for row in selected:
            result[str(row["domain_id"])].add(normalized)
    return dict(result)


def slice_session_key(member: str) -> str:
    parts = member.split("__")
    if len(parts) < 3 or not parts[-1].startswith("segment-"):
        raise ValueError(f"Unexpected slice member key: {member}")
    return "__".join(parts[1:-1])


def load_session_domains(path: Path) -> dict[str, set[str]]:
    domains = read_json(path)
    result: dict[str, set[str]] = {}
    for domain in domains:
        members = set()
        for member in domain.get("members", []):
            parts = member.split("__")
            if parts[-1].startswith("segment-"):
                session_member = "__".join(parts[:-1])
                if session_member.startswith("segments__"):
                    session_member = session_member[len("segments__"):]
                members.add(session_member)
            else:
                members.add(member)
        result[domain["domain_id"]] = members
    return result


def invert_membership(domain_members: dict[str, set[str]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for domain_id, members in domain_members.items():
        for member in members:
            result[member].add(domain_id)
    return dict(result)


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def compare_memberships(
    session_domains: dict[str, set[str]],
    slice_domains: dict[str, set[str]],
) -> dict[str, Any]:
    session_to_domains = invert_membership(session_domains)
    slice_to_domains = invert_membership(slice_domains)

    all_slices = set(slice_to_domains)
    session_to_slices: dict[str, set[str]] = defaultdict(set)
    for slice_id in all_slices:
        session_to_slices[slice_session_key(slice_id)].add(slice_id)

    pair_rows: list[dict[str, Any]] = []
    for session_domain_id, session_members in session_domains.items():
        expanded = set().union(*(session_to_slices.get(key, set()) for key in session_members))
        for slice_domain_id, slice_members in slice_domains.items():
            intersection = expanded & slice_members
            pair_rows.append({
                "session_domain_id": session_domain_id,
                "slice_domain_id": slice_domain_id,
                "session_count": len(session_members),
                "expanded_slice_count": len(expanded),
                "slice_domain_count": len(slice_members),
                "intersection_count": len(intersection),
                "session_to_slice_coverage": round(len(intersection) / len(expanded), 6) if expanded else 0.0,
                "slice_to_session_coverage": round(len(intersection) / len(slice_members), 6) if slice_members else 0.0,
                "jaccard": round(jaccard(expanded, slice_members), 6),
                "exact_member_set_match": expanded == slice_members,
                "expanded_slice_ids": sorted(expanded),
                "slice_domain_member_ids": sorted(slice_members),
            })

    best_for_session = {}
    for session_domain_id in session_domains:
        candidates = [row for row in pair_rows if row["session_domain_id"] == session_domain_id]
        best_for_session[session_domain_id] = max(candidates, key=lambda row: (row["jaccard"], row["intersection_count"]))
    best_for_slice = {}
    for slice_domain_id in slice_domains:
        candidates = [row for row in pair_rows if row["slice_domain_id"] == slice_domain_id]
        best_for_slice[slice_domain_id] = max(candidates, key=lambda row: (row["jaccard"], row["intersection_count"]))

    return {
        "session_domain_count": len(session_domains),
        "slice_domain_count": len(slice_domains),
        "slice_count": len(all_slices),
        "session_count_in_slice_mapping": len(session_to_slices),
        "session_domains": {key: sorted(value) for key, value in session_domains.items()},
        "slice_domains": {key: sorted(value) for key, value in slice_domains.items()},
        "session_to_domains": {key: sorted(value) for key, value in session_to_domains.items()},
        "slice_to_domains": {key: sorted(value) for key, value in slice_to_domains.items()},
        "pair_rows": pair_rows,
        "best_slice_domain_for_session_domain": best_for_session,
        "best_session_domain_for_slice_domain": best_for_slice,
    }


def compare(
    session_domains_path: Path,
    session_assignments_path: Path,
    slice_assignments_path: Path,
) -> dict[str, Any]:
    session_domain_members = load_session_domains(session_domains_path)
    session_assignments = load_assignments(session_assignments_path)
    slice_assignments = load_assignments(slice_assignments_path)
    modes = {
        "overlap_evidence": compare_memberships(
            session_domain_members,
            assignment_domains(slice_assignments),
        ),
        "primary_partition": compare_memberships(
            assignment_domains(session_assignments, primary_only=True, normalize_session_members=True),
            assignment_domains(slice_assignments, primary_only=True),
        ),
    }
    return modes


def write_report(comparison: dict[str, Any], output: Path) -> None:
    (output / "session-slice-consistency.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 原始 session 聚类与切片聚类一致性",
        "",
        "- `overlap_evidence`：保留原始候选簇的多归属关系；",
        "- `primary_partition`：每个成员只取 assignments 中的最高分簇。",
    ]
    for mode in ("overlap_evidence", "primary_partition"):
        data = comparison[mode]
        lines.extend([
            "",
            f"## {mode}",
            "",
            f"- 原始 session 簇数：{data['session_domain_count']}",
            f"- 切片簇数：{data['slice_domain_count']}",
            f"- 切片数：{data['slice_count']}",
            f"- 关联 session 数：{data['session_count_in_slice_mapping']}",
            "",
            "| 原始簇 | 最佳切片簇 | 展开切片数 | 切片簇大小 | 交集 | 原始→切片覆盖 | 切片→原始覆盖 | Jaccard | 完全相同 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ])
        for session_id, row in sorted(data["best_slice_domain_for_session_domain"].items()):
            lines.append(
                f"| {session_id} | {row['slice_domain_id']} | {row['expanded_slice_count']} | "
                f"{row['slice_domain_count']} | {row['intersection_count']} | "
                f"{row['session_to_slice_coverage']:.3f} | {row['slice_to_session_coverage']:.3f} | "
                f"{row['jaccard']:.3f} | {'是' if row['exact_member_set_match'] else '否'} |"
            )
    (output / "session-slice-consistency.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-sessions-root", type=Path, required=True)
    parser.add_argument("--slice-dir", type=Path, required=True)
    parser.add_argument("--slice-domains", type=Path, required=True)
    parser.add_argument("--slice-assignments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-terms", type=int, default=300)
    parser.add_argument("--edge-threshold", type=float, default=0.55)
    parser.add_argument("--min-support", type=int, default=3)
    parser.add_argument("--min-coverage", type=float, default=0.03)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    build_session_inputs(args.raw_sessions_root, args.output)
    session_token_output = args.output / "session-token-frequency"
    session_input_root = args.output / "raw-session-inputs"
    session_token_output.mkdir(parents=True, exist_ok=True)
    results = [
        load_segment(path, include_symbols=False)
        for path in sorted(session_input_root.rglob("segment-*.json"))
    ]
    segments_output = session_token_output / "segments"
    segments_output.mkdir(parents=True, exist_ok=True)
    for result in results:
        output_path = segments_output / f"{segment_key(result)}.json"
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (session_token_output / "summary.json").write_text(json.dumps({
        "session_count": len(results),
        "input_dir": str(session_input_root),
        "output_dir": str(segments_output),
        "include_symbols": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    session_cluster_output = args.output / "unsupervised-session-domain-v1"
    summary = discover(segments_output, session_cluster_output, args.max_terms, args.edge_threshold, args.min_support, args.min_coverage)
    comparison = compare(
        session_cluster_output / "domains.json",
        session_cluster_output / "assignments.json",
        args.slice_assignments,
    )
    comparison["session_cluster_summary"] = summary
    comparison["parameters"] = {
        "max_terms": args.max_terms,
        "edge_threshold": args.edge_threshold,
        "min_support": args.min_support,
        "min_coverage": args.min_coverage,
    }
    write_report(comparison, args.output)
    print(json.dumps({
        "session_count": len(results),
        "session_cluster_summary": summary,
        "comparison_json": str(args.output / "session-slice-consistency.json"),
        "comparison_report": str(args.output / "session-slice-consistency.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
