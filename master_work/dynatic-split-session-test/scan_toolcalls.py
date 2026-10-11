#!/usr/bin/env python3
"""Scan coding-agent sessions and index tool calls.

The input traces are not one common schema. This scanner supports the raw
formats currently present in Trace Commons:

* Claude Code / Cursor: one JSON object per JSONL line.
* OpenCode: one JSON document containing ``messages`` and ``parts``.

For every detected call the report keeps both the exact arguments and an
inferred JSON Schema for those arguments. A declared tool schema is included
when the trace actually contains one; most raw traces contain calls but do not
contain the provider's complete tool definitions.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


def json_path(parent: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{parent}[{key}]"
    return f"{parent}.{key}" if parent else f"$.{key}"


def walk(value: Any, path: str = "$") -> Iterator[tuple[Any, str]]:
    yield value, path
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, json_path(path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, json_path(path, index))


def infer_schema(value: Any) -> dict[str, Any]:
    """Infer a useful, lossless-enough JSON Schema from one actual argument."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, list):
        item_schemas = [json.dumps(infer_schema(item), sort_keys=True) for item in value]
        unique_json = sorted(set(item_schemas))
        unique = [json.loads(schema) for schema in unique_json]
        schema: dict[str, Any] = {"type": "array"}
        if len(unique) == 1:
            schema["items"] = unique[0]
        elif unique:
            schema["items"] = {"anyOf": unique}
        return schema
    if isinstance(value, dict):
        properties = {key: infer_schema(child) for key, child in value.items()}
        return {
            "type": "object",
            "properties": properties,
            "required": list(value.keys()),
            "additionalProperties": False,
        }
    return {}


def schema_locations(
    value: Any,
    actual_path: str = "$",
    schema_path: str = "#",
) -> dict[str, str]:
    """Return JSON-Schema locations for every field in an inferred schema."""
    locations: dict[str, str] = {actual_path: schema_path}
    if isinstance(value, dict):
        for key, child in value.items():
            escaped_key = key.replace("~", "~0").replace("/", "~1")
            locations.update(schema_locations(
                child,
                json_path(actual_path, key),
                f"{schema_path}/properties/{escaped_key}",
            ))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            locations.update(schema_locations(
                child,
                json_path(actual_path, index),
                f"{schema_path}/items",
            ))
    return locations


def declared_schemas(value: Any, path: str = "$") -> list[dict[str, Any]]:
    """Find formal tool schemas if a raw trace preserved them."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key in ("input_schema", "inputSchema"):
            schema = value.get(key)
            if isinstance(schema, dict):
                found.append({"path": json_path(path, key), "schema": schema})

        function = value.get("function")
        if isinstance(function, dict) and isinstance(function.get("parameters"), dict):
            found.append({
                "path": json_path(json_path(path, "function"), "parameters"),
                "schema": function["parameters"],
            })

        if value.get("type") in {"function", "tool"} and isinstance(value.get("parameters"), dict):
            found.append({
                "path": json_path(path, "parameters"),
                "schema": value["parameters"],
            })

        for key, child in value.items():
            found.extend(declared_schemas(child, json_path(path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(declared_schemas(child, json_path(path, index)))
    return found


def call_from_node(node: Any, path: str) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None

    call_type = node.get("type")
    name: Any = None
    arguments: Any = None
    argument_path: str | None = None

    if call_type == "tool_use" and isinstance(node.get("name"), str):
        name = node["name"]
        arguments = node.get("input", {})
        argument_path = json_path(path, "input")
    elif call_type in {"tool_call", "function_call"}:
        name = node.get("name")
        for key in ("arguments", "args", "input"):
            if key in node:
                arguments = node[key]
                argument_path = json_path(path, key)
                break
    elif call_type == "tool" and isinstance(node.get("tool"), str):
        name = node["tool"]
        state = node.get("state")
        if isinstance(state, dict) and "input" in state:
            arguments = state["input"]
            argument_path = json_path(json_path(path, "state"), "input")
        else:
            arguments = node.get("input", {})
            argument_path = json_path(path, "input") if "input" in node else None

    if not isinstance(name, str):
        return None
    if arguments is None:
        arguments = {}
    declared = declared_schemas(node)
    return {
        "tool_name": name,
        "actual_arguments": arguments,
        "actual_argument_schema": infer_schema(arguments),
        "actual_argument_schema_locations": schema_locations(arguments),
        "schema_source": "declared_in_trace" if declared else "inferred_from_actual_arguments",
        "schema_locations": [item["path"] for item in declared],
        "argument_json_path": argument_path,
        "call_json_path": path,
        "declared_schemas_in_event": declared,
    }


def scan_document(document: Any, *, source_file: str, event_index: int, byte_offset: int) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for node, path in walk(document):
        call = call_from_node(node, path)
        if call is not None:
            call.update({
                "source_file": source_file,
                "event_index": event_index,
                "byte_offset": byte_offset,
            })
            calls.append(call)
    return calls


def scan_file(path: Path, sessions_root: Path) -> dict[str, Any]:
    relative = path.relative_to(sessions_root).as_posix()
    events: list[dict[str, Any]] = []
    if path.suffix == ".jsonl":
        byte_offset = 0
        with path.open("rb") as handle:
            for event_index, raw_line in enumerate(handle, start=1):
                line_offset = byte_offset
                byte_offset += len(raw_line)
                if not raw_line.strip():
                    continue
                try:
                    document = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    events.append({
                        "event_index": event_index,
                        "byte_offset": line_offset,
                        "parse_error": str(exc),
                    })
                    continue
                events.extend(scan_document(
                    document,
                    source_file=relative,
                    event_index=event_index,
                    byte_offset=line_offset,
                ))
    else:
        raw = path.read_bytes()
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            events.append({"event_index": 1, "byte_offset": 0, "parse_error": str(exc)})
        else:
            events.extend(scan_document(
                document,
                source_file=relative,
                event_index=1,
                byte_offset=0,
            ))

    tool_counts = Counter(
        event["tool_name"] for event in events if "tool_name" in event
    )
    return {
        "harness": path.parent.name,
        "session_id": path.stem,
        "source_file": relative,
        "tool_call_count": sum(1 for event in events if "tool_name" in event),
        "tool_counts": dict(sorted(tool_counts.items())),
        "tool_calls": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "agent-traces" / "sessions",
        help="Trace Commons sessions directory (default: ../agent-traces/sessions)",
    )
    parser.add_argument("--output", type=Path, help="Write JSON report to this path instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON report")
    args = parser.parse_args()

    sessions_root = args.sessions_root.resolve()
    if not sessions_root.is_dir():
        parser.error(f"sessions root does not exist: {sessions_root}")

    session_files = sorted(
        path for path in sessions_root.rglob("*")
        if path.is_file() and path.suffix in {".jsonl", ".json"}
    )
    sessions = [scan_file(path, sessions_root) for path in session_files]
    report = {
        "sessions_root": str(sessions_root),
        "session_count": len(sessions),
        "tool_call_count": sum(session["tool_call_count"] for session in sessions),
        "declared_schema_note": "A null/empty declared schema means the raw session did not preserve a formal tool definition; actual_argument_schema is inferred from the recorded arguments.",
        "sessions": sessions,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
