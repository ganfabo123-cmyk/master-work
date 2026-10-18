"""Build cheap, ordered behavior graphs from materialized trajectory events."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


BASE = Path("master_work/experiments/trace-segmentation/dynatic-split-session-test")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def event_label(event: dict) -> str:
    category = str(event.get("category", "unknown"))
    if category in {"user_text", "user"}:
        return "user"
    if category in {"assistant_text", "assistant"}:
        return "assistant"
    if category.startswith("record"):
        return "record"
    if category in {"tool_call", "tool"}:
        return f"tool:{event.get('tool_name') or event.get('name') or 'unknown'}"
    return category


def compact_sequence(events: list[dict]) -> list[str]:
    """Collapse adjacent repeats while preserving the observed event order."""
    result: list[str] = []
    for event in events:
        label = event_label(event)
        if not result or result[-1] != label:
            result.append(label)
    return result


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def mermaid(domain: dict) -> str:
    lines = [f"# {domain['domain_id']} trajectory behavior graph", "", "```mermaid", "flowchart LR"]
    nodes = domain["nodes"]
    edges = domain["edges"]
    for label, count in nodes[:30]:
        nid = "n_" + safe_id(label)
        lines.append(f'    {nid}["{label} ({count})"]')
    for left, right, count in edges[:50]:
        lines.append(f"    n_{safe_id(left)} -->|{count}| n_{safe_id(right)}")
    lines.extend(["```", "", f"Slices: {domain['slice_count']}", f"Unique signatures: {domain['signature_count']}", ""])
    return "\n".join(lines)


def main() -> None:
    domains = read(BASE / "unsupervised-domain-complete-v6/domains.json")
    signal_path = BASE / "tool-operation-signals/slice-tool-signals.jsonl"
    tool_rows = {row["slice_id"]: row for row in (json.loads(line) for line in signal_path.read_text(encoding="utf-8").splitlines())}

    all_profiles: dict[str, dict] = {}
    for sid, row in tool_rows.items():
        source = Path(row.get("source_file", ""))
        if not source.exists():
            continue
        data = read(source)
        events = data.get("events", [])
        sequence = compact_sequence(events)
        raw_labels = [event_label(event) for event in events]
        profile = {
            "slice_id": sid,
            "event_count": len(events),
            "user_events": raw_labels.count("user"),
            "assistant_events": raw_labels.count("assistant"),
            "tool_events": sum(label.startswith("tool:") for label in raw_labels),
            "sequence": sequence[:80],
            "signature": " > ".join(sequence[:24]),
            "operations": row.get("operation_events", {}),
            "file_types": row.get("file_type_events", {}),
        }
        all_profiles[sid] = profile

    out = BASE / "trajectory-behavior-graphs-v1"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "slice-profiles.jsonl").open("w", encoding="utf-8") as stream:
        for profile in all_profiles.values():
            stream.write(json.dumps(profile, ensure_ascii=False) + "\n")
    cards = []
    for domain in domains:
        did = domain["domain_id"]
        members = [sid.removeprefix("segments__") for sid in domain.get("members", [])]
        profiles = [all_profiles[sid] for sid in members if sid in all_profiles]
        node_counts = Counter()
        edge_counts = Counter()
        signatures = Counter()
        for profile in profiles:
            node_counts.update(profile["sequence"])
            signatures[profile["signature"]] += 1
            edge_counts.update(zip(profile["sequence"], profile["sequence"][1:]))
        top_signatures = []
        for signature, count in signatures.most_common(8):
            example = next(p for p in profiles if p["signature"] == signature)
            top_signatures.append({"count": count, "signature": signature, "example_slice_id": example["slice_id"]})
        representatives = sorted(profiles, key=lambda p: (p["event_count"], len(p["operations"])), reverse=True)[:5]
        graph = {
            "domain_id": did,
            "source_terms": domain.get("terms", []),
            "slice_count": len(profiles),
            "signature_count": len(signatures),
            "nodes": [[label, count] for label, count in node_counts.most_common(30)],
            "edges": [[left, right, count] for (left, right), count in edge_counts.most_common(50)],
            "common_signatures": top_signatures,
            "representative_profiles": representatives,
        }
        (out / f"{did}.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / f"{did}.md").write_text(mermaid(graph), encoding="utf-8")
        cards.append({"domain_id": did, "slice_count": len(profiles), "signature_count": len(signatures), "graph_file": f"{did}.json", "mermaid_file": f"{did}.md"})
    summary = {"algorithm_version": "trajectory-behavior-graphs-v1", "domain_count": len(cards), "profile_count": len(all_profiles), "domains": cards, "label_policy": "ordered event categories and tool names; adjacent repeats collapsed; no semantic behavior labels"}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text("# 廉价轨迹行为图\n\n每个领域输出一张由事件类别和工具调用组成的有向加权图。它只描述可观察的操作顺序，不预设或命名语义行为。\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "domain_count": len(cards), "profile_count": len(all_profiles)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
