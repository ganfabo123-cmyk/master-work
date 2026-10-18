"""Select intact slices for a batch of Sessions in one original-trace group.

Add selection functions to SELECTION_STRATEGIES; grouping itself is not rerun.
Only slice cores are used for matching. Exported files retain their overlap.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Callable, Iterable

VERSION = "group-slice-selection-v3-content-strategies"
SELECTION_STRATEGIES: dict[str, Callable[[dict, str, list[dict]], Iterable[dict]]] = {}


def content_selected_only(data: dict, selected: bool, source_path: str) -> dict | None:
    """Export only the selected intact slices (historical default)."""
    return data if selected else None


def content_selected_full_rest_collapsed(data: dict, selected: bool, source_path: str) -> dict:
    """Keep selected events intact; hide thinking/results in other slices."""
    if selected:
        return data
    output = copy.deepcopy(data)
    for event in output["events"]:
        category = event.get("category", "")
        fields = []
        if category == "tool_result":
            fields = [field for field in ("content", "output", "text", "raw_part") if field in event]
        elif category.endswith(("_thinking", "_reasoning")):
            fields = [field for field in ("text", "thinking", "reasoning", "content", "signature", "raw_part")
                      if field in event]
        hidden = {}
        for field in fields:
            hidden[field] = event.pop(field)
        # OpenCode result state is attached to the call; keep its input and status.
        if isinstance(event.get("tool_result"), dict):
            for field in ("output", "error"):
                if field in event["tool_result"]:
                    hidden["tool_result/" + field] = event["tool_result"].pop(field)
        if hidden:
            event["collapsed_content"] = {
                "hidden_fields": sorted(hidden),
                "original_payload_chars": sum(len(json.dumps(v, ensure_ascii=False)) for v in hidden.values()),
                "source_slice_path": source_path, "source_index": event.get("source_index"),
                "source_part_index": event.get("source_part_index", 0),
            }
    return output


CONTENT_STRATEGIES = {"selected-only": content_selected_only,
                      "selected-full-rest-collapsed": content_selected_full_rest_collapsed}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_candidates(root: Path, session_id: str) -> list[dict]:
    directory = root / session_id
    if not directory.is_dir():
        raise ValueError(f"No slice directory for Session: {session_id}")
    candidates = []
    for path in sorted(directory.glob("segment-*.json")):
        data = read_json(path)
        start, end = data["start_event"], data["end_event"]
        core_start = data.get("core_start_event", start)
        core_end = data.get("core_end_event", end)
        if not start <= core_start <= core_end <= end:
            raise ValueError(f"Invalid core range: {path}")
        if len(data["events"]) != end - start + 1:
            raise ValueError(f"Event count does not match range: {path}")
        refs = set()
        for offset, event in enumerate(data["events"]):
            if core_start <= start + offset <= core_end:
                index = event.get("source_index")
                part = event.get("source_part_index")
                if type(index) is not int or index < 0:
                    raise ValueError(f"Missing/invalid original source_index: {path}")
                if part is not None and (type(part) is not int or part < 0):
                    raise ValueError(f"Invalid source_part_index: {path}")
                refs.add((index, part))
        candidates.append({"slice_id": session_id + "__" + path.stem,
                           "source_path": str(path.resolve()), "core_start_event": core_start,
                           "core_end_event": core_end, "core_refs": refs})
    if not candidates:
        raise ValueError(f"No segment JSON files: {directory}")
    return candidates


def source_reference(event: dict) -> tuple[int, int | None]:
    """Context pointers refer to raw JSONL lines or OpenCode message parts.

    Never substitute slice event_index: it is a different coordinate system.
    """
    index, part = event.get("source_index"), event.get("source_part_index")
    if index is None:
        pointer = event.get("json_pointer", "")
        match = re.fullmatch(r"jsonl:(\d+)/content/(\d+)", pointer)
        if match:
            index, part = int(match[1]) - 1, int(match[2])
        else:
            match = re.match(r"^/messages/(\d+)/parts/(\d+)(?:/|$)", pointer)
            if match:
                index, part = int(match[1]), int(match[2])
    if type(index) is not int or index < 0:
        raise ValueError(f"Missing/invalid raw source reference: {event.get('json_pointer')}")
    if part is not None and (type(part) is not int or part < 0):
        raise ValueError("Invalid original part index")
    return index, part


def requested_references(group: dict, session_id: str, include_context: bool) -> list[dict]:
    refs = {}
    for occurrence in group.get("evidence", []):
        if occurrence.get("session_id", occurrence.get("unit_id")) != session_id:
            continue
        # A slice group carries pointers into slice JSON, not original messages.
        if occurrence.get("unit_id", session_id) != session_id:
            raise ValueError("Expected an original-trace group, not a slice group")
        for reason, event in [("group_hit", occurrence)] + (
                [("stored_context", e) for e in occurrence.get("context", [])]
                if include_context else []):
            index, part = source_reference(event)
            key = (index, part, reason)
            refs[key] = {"source_index": index, "source_part_index": part,
                         "reason": reason, "json_pointer": event.get("json_pointer"),
                         "channel": event.get("channel")}
    if not any(r["reason"] == "group_hit" for r in refs.values()):
        raise ValueError(f"No source evidence for Session: {session_id}")
    return sorted(refs.values(), key=lambda r: (r["source_index"],
                  -1 if r["source_part_index"] is None else r["source_part_index"], r["reason"]))


def reference_matches(reference: dict, candidate: dict) -> bool:
    index, part = reference["source_index"], reference["source_part_index"]
    return any(index == i and (part is None or p is None or part == p)
               for i, p in candidate["core_refs"])


def match_references(refs: list[dict], candidates: list[dict]) -> list[dict]:
    return [{**ref, "slice_ids": [s["slice_id"] for s in candidates if reference_matches(ref, s)]}
            for ref in refs]


def strategy_group_evidence(group: dict, session_id: str, candidates: list[dict]) -> list[dict]:
    """Select cores containing this group's original evidence events."""
    return match_references(requested_references(group, session_id, False), candidates)


def strategy_group_context(group: dict, session_id: str, candidates: list[dict]) -> list[dict]:
    """Select evidence cores plus the nearby context already stored by grouping."""
    return match_references(requested_references(group, session_id, True), candidates)


SELECTION_STRATEGIES.update({"group-evidence": strategy_group_evidence,
                             "group-context": strategy_group_context})


def select(group: dict, session_id: str, candidates: list[dict], strategy: str) -> dict:
    if session_id not in group.get("member_session_ids", group.get("member_ids", [])):
        raise ValueError(f"Session is not a member of group: {session_id}")
    if strategy not in SELECTION_STRATEGIES:
        raise ValueError(f"Unknown selection strategy: {strategy}")
    refs = list(SELECTION_STRATEGIES[strategy](group, session_id, candidates))
    known_ids = {s["slice_id"] for s in candidates}
    reasons = {sid: [] for sid in known_ids}
    for ref in refs:
        if not isinstance(ref.get("slice_ids"), list) or not isinstance(ref.get("reason"), str):
            raise ValueError("Selection functions must return reason and slice_ids")
        for sid in dict.fromkeys(ref["slice_ids"]):
            if sid not in known_ids:
                raise ValueError(f"Strategy selected an unknown slice: {sid}")
            reasons[sid].append({k: v for k, v in ref.items() if k != "slice_ids"})
    selected, excluded = [], []
    for candidate in candidates:
        public = {k: v for k, v in candidate.items() if k != "core_refs"}
        if reasons[candidate["slice_id"]]:
            selected.append({**public, "selection_evidence": reasons[candidate["slice_id"]]})
        else:
            excluded.append({**public, "reason": "not_selected_by_strategy"})
    return {"algorithm_version": VERSION, "group_id": group["group_id"],
            "group_key": group.get("group_key", group.get("error_key")),
            "session_id": session_id, "selection_strategy": strategy,
            "candidate_count": len(candidates), "selected_count": len(selected),
            "excluded_count": len(excluded), "selected_slices": selected,
            "excluded_slices": excluded, "unmapped_references": [r for r in refs if not r["slice_ids"]],
            "original_trace_paths": sorted({e["source_path"] for e in group.get("evidence", [])
                if e.get("session_id", e.get("unit_id")) == session_id and e.get("source_path")}),
            "content_policy": "Copy original slice files unchanged; no hydration or event compression"}


def run(groups_file: Path, group_id: str, session_ids: Iterable[str] | str, slices_dir: Path,
        output: Path, strategy: str = "group-context", content_strategy: str = "selected-only") -> dict:
    # Accept the historical single-string API, but always produce a batch result.
    ids = [session_ids] if isinstance(session_ids, str) else list(session_ids)
    if not ids:
        raise ValueError("session_ids must contain at least one original trace ID")
    for sid in ids:
        if not isinstance(sid, str) or not sid or sid in {".", ".."} or re.search(r"[\\/:]", sid):
            raise ValueError("Each session_id must be a directory name")
    ids = sorted(set(ids))
    if content_strategy not in CONTENT_STRATEGIES:
        raise ValueError(f"Unknown content strategy: {content_strategy}")
    groups = read_json(groups_file)
    if not isinstance(groups, list):
        raise ValueError("Expected groups.json containing a list of groups")
    matches = [g for g in groups if g.get("group_id") == group_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one matching group: {group_id}")
    group = matches[0]
    members = group.get("member_session_ids", group.get("member_ids", []))
    for sid in ids:
        if sid not in members:
            raise ValueError(f"Session is not a member of group: {sid}")
    # Validate and select every Session before creating any output files.
    sessions = [select(group, sid, load_candidates(slices_dir, sid), strategy) for sid in ids]
    selected = [{**slice_result, "session_id": session["session_id"]}
                for session in sessions for slice_result in session["selected_slices"]]
    excluded = [{**slice_result, "session_id": session["session_id"]}
                for session in sessions for slice_result in session["excluded_slices"]]
    result = {"algorithm_version": VERSION, "group_id": group_id,
              "group_key": group.get("group_key", group.get("error_key")),
              "session_ids": ids, "session_count": len(ids), "selection_strategy": strategy,
              "candidate_count": sum(session["candidate_count"] for session in sessions),
              "selected_count": len(selected), "excluded_count": len(excluded),
              "selected_slice_ids": [s["slice_id"] for s in selected],
              "selected_slices": selected, "excluded_slices": excluded,
              "unmapped_references": [{**ref, "session_id": session["session_id"]}
                  for session in sessions for ref in session["unmapped_references"]],
              "sessions": sessions,
              "original_trace_paths": sorted({p for session in sessions
                                               for p in session["original_trace_paths"]}),
              "content_policy": "Copy original slice files unchanged; no hydration or event compression"}
    # A fresh directory prevents accidental overwrite and stale selected slices.
    if output.exists():
        raise ValueError(f"Output already exists; choose a new directory: {output}")
    resolved_output, resolved_input = output.resolve(), slices_dir.resolve()
    if resolved_output == resolved_input or resolved_input in resolved_output.parents:
        raise ValueError("Output must be outside the input slice directory")
    result["inputs"] = {"groups_file": str(groups_file.resolve()),
                        "slices_dir": str(resolved_input)}
    result["content_strategy"] = content_strategy
    if content_strategy != "selected-only":
        result["content_policy"] = "Selected slices unchanged; unselected thinking/tool-result payloads hidden"
    output.mkdir(parents=True)
    exported_slices = []
    selected_ids = set(result["selected_slice_ids"])
    for item in sorted(result["selected_slices"] + result["excluded_slices"], key=lambda s: s["slice_id"]):
        selected = item["slice_id"] in selected_ids
        if not selected and content_strategy == "selected-only":
            continue
        source = Path(item["source_path"])
        data = read_json(source)
        # Selected slices are protected even when additional content policies are registered.
        transformed = data if selected else CONTENT_STRATEGIES[content_strategy](data, False, str(source))
        if transformed is None:
            continue
        destination = output / "slices" / item["session_id"] / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if selected:
            shutil.copyfile(source, destination)
        else:
            destination.write_text(json.dumps(transformed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        item["output_path"] = str(destination.resolve())
        item["sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
        item["content_mode"] = "full" if selected else "collapsed"
        item["collapsed_event_count"] = sum("collapsed_content" in e for e in transformed["events"])
        exported_slices.append(item)
    result["exported_slices"] = exported_slices
    result["exported_count"] = len(exported_slices)
    result["collapsed_slice_count"] = sum(s["content_mode"] == "collapsed" for s in exported_slices)
    result["collapsed_event_count"] = sum(s["collapsed_event_count"] for s in exported_slices
                                          if s["content_mode"] == "collapsed")
    exported = {s["slice_id"]: s for s in result["selected_slices"]}
    for session in sessions:
        session["selected_slices"] = [exported[s["slice_id"]] for s in session["selected_slices"]]
        session["content_strategy"] = content_strategy
        session["content_policy"] = result["content_policy"]
        session["exported_slices"] = [s for s in exported_slices if s["session_id"] == session["session_id"]]
    (output / "selection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-strategies", action="store_true")
    parser.add_argument("--groups", type=Path)
    parser.add_argument("--group-id")
    parser.add_argument("--session-ids", "--session-id", dest="session_ids", nargs="+",
                        help="Original trace IDs belonging to the selected group; duplicates are removed")
    parser.add_argument("--slices-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strategy", choices=tuple(SELECTION_STRATEGIES), default="group-context")
    parser.add_argument("--content-strategy", choices=tuple(CONTENT_STRATEGIES), default="selected-only")
    args = parser.parse_args()
    if args.list_strategies:
        for name, function in SELECTION_STRATEGIES.items():
            print(f"{name}: {function.__doc__}")
        return
    for field in ("groups", "group_id", "session_ids", "slices_dir", "output"):
        if getattr(args, field) is None:
            parser.error("Required: --" + field.replace("_", "-"))
    try:
        result = run(args.groups, args.group_id, args.session_ids, args.slices_dir,
                     args.output, args.strategy, args.content_strategy)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps({k: result[k] for k in ("group_id", "session_ids", "session_count", "selection_strategy",
                                           "candidate_count", "selected_count", "excluded_count")},
                     ensure_ascii=False))
    print(f"unmapped_references: {len(result['unmapped_references'])}")
    print(f"exported_count: {result['exported_count']}; collapsed_slice_count: {result['collapsed_slice_count']}")


if __name__ == "__main__":
    main()
