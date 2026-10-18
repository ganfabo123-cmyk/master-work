"""Strategy grouping of Session/slice evidence, selected by --strategies.

Add a function accepting one projected unit and register it in STRATEGY_REGISTRY.
The shared pipeline supplies source context and groups its matches by group_key.
Existing error strategies and the historical filename remain compatible.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import posixpath
from pathlib import Path
import re
import tomllib
import xml.etree.ElementTree as ET
from typing import Any, Callable, Iterable

VERSION = "strategy-grouping-v2"
# Historical defaults remain fixed; newly registered strategies are opt-in.
STRATEGIES = ("native-code", "exception-type", "message-template")
STRATEGY_REGISTRY: dict[str, Callable[[dict], Iterable[dict]]] = {}
CODE = re.compile(r"\b(?:TS\d{3,5}|CS\d{3,5}|LNK\d{4}|NETSDK\d{4}|C\d{4}|E\d{4}|E[A-Z][A-Z0-9_]{3,})\b")
SQLSTATE = re.compile(r"\bSQLSTATE\s*(?:\[|[:=])?\s*['\"]?([0-9A-Z]{5})\b", re.I)
EXCEPTION = re.compile(r"\b((?:[A-Za-z_]\w*\.)*[A-Z]\w*(?:Error|Exception))\b")
ERROR_LINE = re.compile(
    r"(?:^\s*(?:(?:fatal\s+)?error|exception|panic|failure|failed)\s*[:\[]"
    r"|\b(?:fatal\s+)?error\s+(?:[A-Z]+\d+\s*)?:"
    r"|\b[A-Za-z_]\w*(?:Error|Exception)\s*:"
    r"|\bundefined reference\s+to\b|\bsegmentation fault\b|\bstack overflow\b"
    r"|\b(?:command|test|build|compilation|linking)\s+failed\b"
    r"|^\s*(?:错误|异常|失败)\s*[:：])", re.I)
SUCCESS = re.compile(r"\b(?:0|zero|no)\s+(?:errors?|failures?)\b", re.I)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
FENCE = re.compile(r"```([^\n]*)\n(.*?)```", re.S)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values), encoding="utf-8")


def payload_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (payload_text(v) for v in value)))
    if isinstance(value, dict):
        return "\n".join(payload_text(value[k]) for k in ("text", "stdout", "stderr", "output", "content") if k in value)
    return ""


def prose(text: str) -> str:
    # Keep diagnostic fences, remove embedded source examples.
    return FENCE.sub(lambda m: m[2] if m[1].strip().lower() in {
        "", "text", "plaintext", "console", "output", "log", "stderr", "traceback"
    } else "\n", text)


def normalize_message(line: str) -> str:
    value = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line)
    value = re.sub(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b", "<uuid>", value)
    # Only remove locations and volatile values; preserve type names and status codes.
    value = re.sub(r"(?:[A-Za-z]:[\\/]|/)(?:[^\s:'\"<>]+[\\/])*[^\s:'\"<>]+", "<path>", value)
    value = re.sub(r"<path>(?::\d+){1,2}", "<location>", value)
    value = re.sub(r"\b[^\s:'\"<>]+\.(?:[A-Za-z0-9]{1,8})(?::\d+){1,2}(?=:|\s)", "<location>", value)
    value = re.sub(r"\b(line|column|position)\s+\d+\b", r"\1 <n>", value, flags=re.I)
    value = re.sub(r"\bat 0x[0-9a-f]+\b", "at <address>", value, flags=re.I)
    value = re.sub(r"(['\"`])[^'\"`\n]{1,200}\1", "<arg>", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def code_namespace(code: str) -> str:
    for prefix, namespace in (("NETSDK", "dotnet-sdk"), ("LNK", "ms-linker"), ("TS", "typescript"), ("CS", "csharp")):
        if code.startswith(prefix) and code[len(prefix):].isdigit():
            return namespace
    # Bare E/C codes are not enough to prove a language or compiler identity.
    return "numeric-diagnostic" if re.fullmatch(r"[EC]\d+", code) else "symbolic-code"


def detect(text: str, channel: str, strategy: str | None = None) -> list[dict[str, Any]]:
    """Backward-compatible text detector for the built-in error strategies."""
    text = text if channel == "tool_result" else prose(text)
    found: dict[tuple[str, str, str], dict] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = ANSI.sub("", raw).strip()
        if not line or SUCCESS.search(line):
            continue
        if re.match(r"(?:\d+\s*[\t|→]|PASS\b|\[PASS\b)", line):
            continue
        # Source definitions inside retrieved code are not exception reports.
        if re.match(r"(?:class|def|function|import|from|raise|throw)\s", line):
            continue
        if ':: proc' in line or re.match(r'\s*(?:if\s*\(|#define\b|#include\b)', line):
            continue
        entries: list[tuple[str, str, str]] = []
        if strategy in (None, "native-code"):
            for match in SQLSTATE.finditer(line):
                entries.append(("native-code", "sqlstate:" + match[1].upper(), match[1].upper()))
            for match in CODE.finditer(line):
                code = match[0]
                if code in {"ERROR", "ERRORS", "EXCEPTION", "EXCEPTIONS", "EXIT", "EXPECTED", "ENV", "END"}:
                    continue
                diagnostic = ERROR_LINE.search(line) or re.search(r"\b(?:code|errno|FullyQualifiedErrorId)\s*[:=]", line, re.I)
                if not diagnostic and (channel == "tool_result" or code_namespace(code) == "symbolic-code"):
                    continue
                entries.append(("native-code", code_namespace(code) + ":" + code, code))
            for match in re.finditer(r"\bexit\s+(?:code|status)\s*[:=]?\s*[`'\"]?(-?\d+|0x[0-9a-f]+)\b", line, re.I):
                status = int(match[1], 16 if match[1].lower().startswith('0x') else 10)
                if status < 0 or status > 255:
                    code = f"0x{status & 0xFFFFFFFF:08X}"
                    entries.append(("native-code", "exit-status:" + code, code))
        if strategy in (None, "exception-type"):
            for match in EXCEPTION.finditer(line):
                name = match[1]
                if not (
                    re.match(r"[`'\"]?\s*(?::|at\b)", line[match.end():])
                    or re.search(r"\b(?:CategoryInfo|FullyQualifiedErrorId)\s*:", line)
                    or re.search(r"<(?:tool_use_error|error)>", line)
                ):
                    continue
                entries.append(("exception-type", "exception:" + name, name))
        if strategy in (None, "message-template") and ERROR_LINE.search(line):
            template = normalize_message(line[:2000])
            if template:
                entries.append(("message-template", "template:" + template, template))
        for strategy_name, key, label in entries:
            signature = (strategy_name, key, line)
            found.setdefault(signature, {
                "strategy": strategy_name, "error_key": key, "label": label,
                "evidence_line": raw[:2000], "text_line": number, "evidence_line_truncated": len(raw) > 2000,
                "evidence_kind": "tool_output" if channel == "tool_result" else "reported_in_text",
            })
    return list(found.values())


def select_strategies(names: Iterable[str] | None = None) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(STRATEGIES if names is None else names))
    if not selected:
        raise ValueError("Select at least one strategy")
    unknown = [name for name in selected if name not in STRATEGY_REGISTRY]
    if unknown:
        raise ValueError(f"Unknown strategies: {', '.join(unknown)}")
    return selected


def error_event_allowed(event: dict) -> bool:
    """Error-specific filtering; it never gates other strategy functions."""
    if event["channel"] == "tool_result":
        if event["tool_name"].casefold() in {"read", "grep", "glob", "webfetch", "websearch", "semanticsearch"}:
            return bool(re.match(r"\s*(?:<tool_use_error>|Error:|error:)", event["text"]))
        return True
    return event["channel"] in {"user_text", "assistant_text", "assistant_thinking", "assistant_reasoning"}


def _error_matches(unit: dict, name: str) -> Iterable[dict]:
    for position, event in enumerate(unit["events"]):
        if error_event_allowed(event) and event["text"]:
            for match in detect(event["text"], event["channel"], name):
                yield {**match, "group_key": match["error_key"], "event_position": position}


def strategy_native_code(unit: dict) -> Iterable[dict]:
    """Source/code-family + native code or nontrivial exit status."""
    return _error_matches(unit, "native-code")


def strategy_exception_type(unit: dict) -> Iterable[dict]:
    """Qualified exception names in diagnostic report syntax."""
    return _error_matches(unit, "exception-type")


def strategy_message_template(unit: dict) -> Iterable[dict]:
    """Diagnostic messages normalized for locations and quoted arguments."""
    return _error_matches(unit, "message-template")


def _path(value: str) -> str:
    result = str(value).replace("\\", "/").rstrip("/")
    result = re.sub(r"/+", "/", result)
    return result.casefold() if re.match(r"^[A-Za-z]:/", result) else result


def _scope(unit: dict, position: int) -> str:
    for event in reversed(unit["events"][:position + 1]):
        if event.get("cwd"):
            return _path(event["cwd"])
    return "session:" + unit["session_id"]


def _file_identity(unit: dict, position: int, filename: str) -> str:
    filename = _path(filename)
    scope = _scope(unit, position)
    if filename.startswith("/") or re.match(r"^[a-z]:/", filename):
        return posixpath.normpath(filename)
    if ("/" in filename or re.search(r"\.(?:py|cpp|c|java|js|ts|groovy|json|toml)(?:::|$)", filename)) and not scope.startswith("session:"):
        return posixpath.normpath(scope + "/" + filename)
    return scope + "::" + filename


def _runtime_output(event: dict) -> bool:
    return (event["channel"] == "tool_result" and event["text"] and
            event["tool_name"].casefold() not in {"read", "grep", "glob", "webfetch", "websearch", "semanticsearch"})


def _hit(position: int, key: str, evidence: str, **details: Any) -> dict:
    return {"event_position": position, "group_key": key, "evidence_line": evidence[:2000],
            "evidence_line_truncated": len(evidence) > 2000, **details}


def _written_test_names(text: str, filename: str) -> list[str]:
    name = _path(filename)
    if not ("/tests/" in name or "/test/" in name or re.search(r"(?:^|/)(?:test[_-]|.*(?:_test|\.test|\.spec|_spec|spec)\.)", name, re.I)):
        return []
    names = []
    for pattern in (r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(",
                    r"^\s*TEST\s*\(\s*[\"']([^\"']+)[\"']",
                    r"^\s*(?:test|it)\s*\(\s*[\"']([^\"']+)[\"']",
                    r"^\s*def\s+[\"']([^\"']+)[\"']\s*\("):
        names.extend(re.findall(pattern, text, re.M))
    return sorted(set(names))


def strategy_test_case(unit: dict) -> Iterable[dict]:
    """Project + suite/file + failed or newly written/edited test identity."""
    for position, event in enumerate(unit["events"]):
        if event["channel"].startswith("tool_call"):
            args = event.get("arguments", {})
            if not isinstance(args, dict):
                continue
            filename = str(args.get("file_path", args.get("path", "")))
            # Only names present in the actual changed text; untouched suite PASS
            # and unnamed assertion failures never create test memberships.
            changed = str(args.get("new_string", args.get("content", "")))
            for name in _written_test_names(changed, filename):
                identity = _file_identity(unit, position, filename)
                definition = next((line for line in changed.splitlines() if name in _written_test_names(line, filename)), name)
                yield _hit(position, f"test:{identity}::{name}", definition, test_name=name,
                           test_owner=identity, trigger="test_definition_change", evidence_kind="tool_call")
        if not _runtime_output(event):
            continue
        text = ANSI.sub("", event["text"])
        # JUnit XML fragments are accepted only with explicit failed/error cases.
        for fragment in re.findall(r"<testcase\b.*?</testcase>", text, re.S):
            try:
                case = ET.fromstring(fragment)
            except ET.ParseError:
                continue
            if case.find("failure") is None and case.find("error") is None:
                continue
            name, owner = case.get("name"), case.get("classname")
            if name and owner:
                identity = _scope(unit, position) + "::" + owner
                yield _hit(position, f"test:{identity}::{name}", fragment, test_name=name,
                           test_owner=identity, trigger="failed_test", evidence_kind="tool_output")
        for line in text.splitlines():
            match = re.match(r"\s*FAILED\s+(\S+::\S+)(?:\s|$)", line)
            if match:
                owner, name = match[1].rsplit("::", 1)
            else:
                match = re.match(r"\s*FAIL:\s+(\w+)\s+\(([^)]+)\)", line)
                if match:
                    name, owner = match[1], match[2]
                else:
                    match = re.match(r"\s*([\w.$]+)\s*>\s*(.+?)\s+FAILED\s*$", line)
                    if match:
                        owner, name = match[1], match[2]
                    else:
                        match = re.match(r"\s*FAIL\s+([A-Za-z_][\w./-]+)(?:\s*:\s*|\s*$)", line)
                        if not match:
                            continue
                        name = match[1]
                        if re.search(r"\.(?:cpp|c|py|java|js|ts)$", name):
                            continue  # A source location is not a test-case name.
                        owner = name.rsplit("/", 1)[0] if "/" in name else "reported-suite"
            identity = _file_identity(unit, position, owner)
            yield _hit(position, f"test:{identity}::{name}", line, test_name=name,
                       test_owner=identity, trigger="failed_test", evidence_kind="tool_output")


def strategy_stack_site(unit: dict) -> Iterable[dict]:
    """Exception type + owned throw-site frame parsed from failed runtime output."""
    for position, event in enumerate(unit["events"]):
        if not _runtime_output(event):
            continue
        text = ANSI.sub("", event["text"])
        if re.search(r"(?:Results:\s*\d+ passed,\s*0 failed|failures=0\s+errors=0|All .*tests PASSED)", text, re.I):
            continue  # Expected exceptions in a successful test report.
        frames = []
        exception = ""
        style = ""
        for line in text.splitlines():
            if re.match(r"\s*(?:PASS\b|\d+\s*[\t|→])", line):
                continue
            python = re.match(r'\s*File "([^"]+)", line (\d+), in (.+)', line)
            other = re.match(r"\s*at\s+([\w.$<>]+)\s*\((.+?):(\d+)(?::\d+)?\)", line)
            error = re.search(r"\b((?:[\w]+\.)*(?:[A-Z]\w*(?:Error|Exception)|Error|Exception))\s*:", line)
            if python:
                style = "python"
                frames.append({"file": python[1], "line": int(python[2]), "function": python[3].strip()})
            elif other:
                style = "java-or-js"
                frames.append({"file": other[2], "line": int(other[3]), "function": other[1]})
            elif error:
                # Java/JS chained causes begin a fresh frame block; Python's
                # exception type follows its frames.
                if style == "java-or-js":
                    frames = []
                exception = error[1]
        if not frames or not exception:
            continue
        site = frames[-1] if style == "python" else frames[0]
        symbol = site["function"]
        if style == "python" or "." not in symbol:
            symbol = _file_identity(unit, position, site["file"]) + "::" + symbol
        yield _hit(position, f"stack:{exception}::{symbol}", text, exception_type=exception,
                   throw_site=site, frames=frames, stack_format=style, evidence_kind="tool_output")


def _clean_file_text(text: str) -> str:
    return "\n".join(re.sub(r"^\s*\d+[\t→]", "", line) for line in text.splitlines())


def _file_changes(unit: dict) -> Iterable[dict]:
    """Recover writes/edits using only snapshots observed inside this unit."""
    snapshots = {}
    calls = {}
    last_read = None
    for position, event in enumerate(unit["events"]):
        args = event.get("arguments", {})
        if event["channel"].startswith("tool_call") and isinstance(args, dict):
            filename = str(args.get("file_path", args.get("path", "")))
            if not filename:
                continue
            key = _path(filename)
            if event["tool_name"].casefold() == "read":
                last_read = (key, position)
                if event.get("tool_use_id"):
                    calls[event["tool_use_id"]] = last_read
            elif "content" in args or "new_string" in args:
                before = snapshots.get(key)
                old = args.get("old_string")
                new = args.get("new_string", args.get("content"))
                if not isinstance(new, str):
                    continue
                if "content" in args:
                    after = new
                    mode = "write"
                elif before is not None and isinstance(old, str) and old in before:
                    count = -1 if args.get("replace_all") else 1
                    after = before.replace(old, new, count)
                    mode = "snapshot-edit"
                else:
                    before, after, mode = old, new, "fragment-edit"
                if mode != "fragment-edit":
                    snapshots[key] = after
                else:
                    snapshots.pop(key, None)
                yield {"position": position, "filename": filename, "before": before,
                       "after": after, "mode": mode, "evidence": json.dumps(args, ensure_ascii=False)}
        elif event["channel"] == "tool_result" and event["tool_name"].casefold() == "read":
            reference = calls.get(event.get("tool_use_id")) or last_read
            if reference and event["text"]:
                snapshots[reference[0]] = _clean_file_text(event["text"])
            last_read = None


def _structured(text: str | None, filename: str, fragment: bool = False) -> dict | None:
    if text is None:
        return None
    try:
        if filename.casefold().endswith(".toml"):
            value = tomllib.loads(text)
        else:
            # JSONC comments are stripped only outside quoted strings.
            cleaned = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/',
                             lambda m: m[1] or "", text, flags=re.S)
            cleaned = re.sub(r'("(?:\\.|[^"\\])*")|,\s*([}\]])',
                             lambda m: m[1] or m[2], cleaned)
            if fragment:
                cleaned = "{" + cleaned.strip().strip(",") + "}"
            value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except (ValueError, tomllib.TOMLDecodeError):
        return None


def _flatten(value: dict, prefix: tuple = ()) -> dict[tuple, Any]:
    result = {}
    for key, item in value.items():
        path = prefix + (str(key),)
        if isinstance(item, dict):
            result.update(_flatten(item, path))
        else:
            result[path] = item  # Arrays stay intact; index changes are ambiguous.
    return result


def strategy_config_change(unit: dict) -> Iterable[dict]:
    """Confirmed config filename + parsed complete key path + before/after change."""
    for change in _file_changes(unit):
        filename = change["filename"]
        basename = _path(filename).rsplit("/", 1)[-1]
        if not basename.endswith((".json", ".jsonc", ".toml")):
            continue
        # Generic filename conventions, not a catalog of domain configuration keys.
        if not ("config" in basename or "settings" in basename or re.search(r"rc\.jsonc?$", basename)):
            continue
        if change["mode"] == "fragment-edit":
            continue  # Cannot claim a complete key path from an isolated fragment.
        before = _structured(change["before"], filename)
        after = _structured(change["after"], filename)
        if before is None or after is None:
            continue
        left, right = _flatten(before), _flatten(after)
        for path in sorted(left.keys() | right.keys()):
            if path in left and path in right and left[path] == right[path]:
                continue
            key_path = "/".join(path)
            schema = after.get("$schema", before.get("$schema"))
            identity = "schema:" + schema if isinstance(schema, str) else _file_identity(unit, change["position"], filename)
            yield _hit(change["position"], f"config:{identity}::{key_path}", change["evidence"],
                       config_file=filename, key_path=list(path), old_value=left.get(path), new_value=right.get(path),
                       old_present=path in left, new_present=path in right, reconstruction=change["mode"],
                       evidence_kind="tool_call")


def _dependencies(text: str | None, filename: str) -> dict[tuple[str, str], str] | None:
    if text is None:
        return None
    base = _path(filename).rsplit("/", 1)[-1]
    result = {}
    if base == "package.json":
        value = _structured(text, filename)
        if value is None:
            return None
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            entries = value.get(section, {})
            if not isinstance(entries, dict):
                continue
            for name, version in entries.items():
                result[("npm", name)] = str(version)
        return result
    if base == "cargo.toml":
        value = _structured(text, filename)
        if value is None:
            return None
        for section in ("dependencies", "dev-dependencies", "build-dependencies"):
            for name, version in value.get(section, {}).items():
                result[("cargo", name)] = json.dumps(version, sort_keys=True) if isinstance(version, dict) else str(version)
        return result
    if base == "pyproject.toml":
        value = _structured(text, filename)
        if value is None:
            return None
        entries = value.get("project", {}).get("dependencies", [])
        entries += [item for group in value.get("project", {}).get("optional-dependencies", {}).values() for item in group]
        for item in entries:
            match = re.match(r"([\w.-]+)(.*)", item)
            if match:
                result[("pypi", re.sub(r"[-_.]+", "-", match[1]).lower())] = match[2].strip()
        return result
    if re.match(r"requirements.*\.txt$", base):
        for line in text.splitlines():
            match = re.match(r"\s*([\w.-]+)\s*([<>=!~].*)?$", line)
            if match:
                result[("pypi", re.sub(r"[-_.]+", "-", match[1]).lower())] = (match[2] or "").strip()
        return result
    if base in {"build.gradle", "build.gradle.kts"}:
        for match in re.finditer(r"\b(?:implementation|api|compileOnly|runtimeOnly|testImplementation|testRuntimeOnly|errorprone)\s*\(?\s*['\"]([^:'\"]+):([^:'\"]+):([^'\"]+)['\"]", text):
            result[("maven", match[1] + ":" + match[2])] = match[3]
        for match in re.finditer(r"\bid\s*\(?\s*['\"]([^'\"]+)['\"]\s*\)?\s*version\s*['\"]([^'\"]+)['\"]", text):
            result[("gradle-plugin", match[1])] = match[2]
        return result
    return None


def strategy_dependency_change(unit: dict) -> Iterable[dict]:
    """Package ecosystem + package name from manifest writes/edits; old versions stay unknown when absent."""
    for change in _file_changes(unit):
        before = _dependencies(change["before"], change["filename"])
        after = _dependencies(change["after"], change["filename"])
        if after is None:
            continue
        if change["mode"] == "fragment-edit" and before is None:
            continue
        left = before or {}
        for identity in sorted(left.keys() | after.keys()):
            if before is not None and identity in left and identity in after and left[identity] == after[identity]:
                continue
            ecosystem, name = identity
            operation = ("declaration_old_unknown" if before is None else "removed" if identity not in after
                         else "added" if identity not in left else "version_changed")
            if change["mode"] == "fragment-edit" and operation in {"added", "removed"}:
                operation = "fragment_declaration_" + operation
            yield _hit(change["position"], f"dependency:{ecosystem}::{name}", change["evidence"],
                       ecosystem=ecosystem, package_name=name, old_version=left.get(identity),
                       new_version=after.get(identity), old_version_known=before is not None,
                       operation=operation, manifest_file=change["filename"], reconstruction=change["mode"],
                       evidence_kind="tool_call")


# Add future test/stack/config/dependency functions here, then select their names
# with --strategies. No change to loading, scan(), group(), or run() is needed.
STRATEGY_REGISTRY.update({
    "native-code": strategy_native_code,
    "exception-type": strategy_exception_type,
    "message-template": strategy_message_template,
    "test-case": strategy_test_case,
    "stack-site": strategy_stack_site,
    "config-change": strategy_config_change,
    "dependency-change": strategy_dependency_change,
})


def project(event: dict, path: Path, offset: int, event_index: int) -> dict:
    category = str(event.get("category") or event.get("kind") or "unknown")
    if category == "text":
        channel = str(event.get("role", "unknown")) + "_" + str(event.get("text_type", "text"))
    else:
        channel = category
    call = event.get("tool_call", {})
    arguments = event.get("arguments", call.get("actual_arguments", {}))
    tool_name = event.get("tool_name", call.get("tool_name", ""))
    command = ""
    if isinstance(arguments, dict):
        command = str(arguments.get("command", arguments.get("cmd", "")))
    text = payload_text(event.get("text", ""))
    if channel == "tool_result":
        text = payload_text(event.get("content", event.get("output", event.get("text", ""))))
    return {
        "event_index": event_index, "source_index": event.get("source_index", event.get("source_event_index", event_index)),
        "source_part_index": event.get("source_part_index", 0), "channel": channel,
        "text": text, "tool_name": tool_name, "command": command,
        "arguments": arguments, "cwd": event.get("cwd", ""),
        "tool_use_id": event.get("tool_use_id", event.get("id", "")),
        "source_path": str(path.resolve()), "json_pointer": f"/events/{offset}",
    }


def load_expanded(root: Path) -> tuple[list[dict], dict[str, str]]:
    manifest = read(root / "index.json")
    collected: dict[str, dict[tuple, dict]] = defaultdict(dict)
    paths: dict[str, set[str]] = defaultdict(set)
    sources: dict[str, str] = {}
    for path in sorted(root.glob("*__segment-*.json")):
        source = read(path)
        sid = source["harness"] + "__" + source["session_id"]
        collected[sid]  # Preserve empty projections as residual members.
        sources[sid] = source["source_file"]
        paths[sid].add(str(path.resolve()))
        for offset, event in enumerate(source["events"]):
            row = project(event, path, offset, int(event.get("source_event_index", offset)))
            key = (row["source_index"], row["source_part_index"], row["channel"])
            collected[sid].setdefault(key, row)
    if len(collected) != manifest["session_count"]:
        raise ValueError("Expanded session count differs from its manifest")
    return [{"unit_id": sid, "session_id": sid, "source_paths": sorted(paths[sid]),
             "events": sorted(events.values(), key=lambda e: (e["source_index"], e["source_part_index"], e["channel"])),
             "input_kind": "expanded_text_and_call_projection"}
            for sid, events in sorted(collected.items())], sources


def raw_events(path: Path) -> list[dict]:
    output: list[dict] = []
    if path.suffix == '.json':
        root = read(path)
        records = list(enumerate(root['messages']))
    else:
        with path.open(encoding='utf-8-sig') as handle:
            records = [(index, json.loads(line)) for index, line in enumerate(handle) if line.strip()]
    for index, source in records:
            message = source.get("message", source)
            role = source.get('info', {}).get('role', message.get("role", source.get("role", source.get("type", "unknown"))))
            content = message.get("content", source.get("parts", ""))
            parts = content if isinstance(content, list) else [{"type": "text", "text": payload_text(content)}]
            for part_index, part in enumerate(parts):
                if not isinstance(part, dict):
                    continue
                kind = part.get("type", "text")
                if kind == 'tool':
                    state = part.get('state', {})
                    # OpenCode stores call and output on one part. Emit separately.
                    call = project({'category': 'tool_call:' + part.get('tool', 'unknown'),
                        'arguments': state.get('input', {}), 'tool_name': part.get('tool', ''),
                        'source_index': index, 'source_part_index': part_index}, path, index, index)
                    call['json_pointer'] = f'/messages/{index}/parts/{part_index}/state/input'
                    output.append(call)
                    result = project({'category': 'tool_result', 'content': state.get('output', state.get('error', '')),
                        'tool_name': part.get('tool', ''), 'source_index': index, 'source_part_index': part_index}, path, index, index)
                    result['json_pointer'] = f'/messages/{index}/parts/{part_index}/state'
                    output.append(result)
                    continue
                if kind not in {'text', 'thinking', 'reasoning', 'tool_use', 'tool_call', 'tool_result', 'tool-result'}:
                    continue
                category = "tool_result" if kind in {"tool_result", "tool-result"} or role == "tool" else (
                    "tool_call:" + part.get("name", "unknown") if kind in {"tool_use", "tool_call"} else
                    role + "_" + ("thinking" if kind in {"thinking", "reasoning"} else "text"))
                row = project({"category": category, "text": part.get("text", part.get("thinking", "")),
                    "content": part.get("content", part.get("output", "")), "arguments": part.get("input", part.get("arguments", {})),
                    "tool_name": part.get("name", ""), "tool_use_id": part.get("tool_use_id", part.get("id", "")),
                    "source_index": index, "source_part_index": part_index,
                    "cwd": source.get("cwd", source.get("info", {}).get("path", {}).get("cwd", ""))}, path, index, index)
                row["json_pointer"] = f"jsonl:{index + 1}/content/{part_index}"
                if path.suffix == '.json':
                    row['json_pointer'] = f'/messages/{index}/parts/{part_index}'
                output.append(row)
    call_names = {e['tool_use_id']: e['tool_name'] for e in output if e['tool_name'] and e['tool_use_id']}
    for e in output:
        if e['channel'] == 'tool_result' and not e['tool_name']:
            e['tool_name'] = call_names.get(e['tool_use_id'], '')
    return output


def load_slices(root: Path, raw_by_session: dict[str, dict[tuple, dict]]) -> list[dict]:
    units = []
    for path in sorted(root.rglob("segment-*.json")):
        source = read(path)
        sid = path.parent.name
        events = []
        for offset, event in enumerate(source["events"]):
            index = source["start_event"] + offset
            if not source.get("core_start_event", source["start_event"]) <= index <= source.get("core_end_event", source["end_event"]):
                continue
            row = project(event, path, offset, index)
            raw = raw_by_session.get(sid, {}).get((row["source_index"], row["source_part_index"]))
            if raw:
                row["cwd"] = raw.get("cwd", "")
            if raw and row["channel"] == "tool_result" and not row["text"]:
                row["text"] = raw["text"]
                row['tool_name'] = raw['tool_name']
                row["hydrated_from"] = {"source_path": raw["source_path"], "json_pointer": raw["json_pointer"]}
            events.append(row)
        units.append({"unit_id": sid + "__" + path.stem, "session_id": sid,
                      "source_paths": [str(path.resolve())], "events": events, "input_kind": "banded_v3_slice_core"})
    return units


def scan(units: list[dict], strategies: Iterable[str] | None = None) -> tuple[list[dict], dict]:
    selected = select_strategies(strategies)
    uses_error_filters = any(name in STRATEGIES for name in selected)
    occurrences = []
    diagnostics = Counter()
    for unit in units:
        last_command = ""
        commands = []
        for event in unit["events"]:
            diagnostics["events"] += 1
            if event["command"]:
                last_command = event["command"]
            commands.append(last_command)
            if event["channel"] == "tool_result":
                diagnostics["tool_result_events"] += 1
                if not event["text"]:
                    diagnostics["tool_result_without_payload"] += 1
                if uses_error_filters and not error_event_allowed(event):
                    diagnostics["source_or_search_outputs_excluded"] += 1
        unit_matches = []
        for strategy_order, name in enumerate(selected):
            seen = set()
            for match in STRATEGY_REGISTRY[name](unit):
                position = match.get("event_position")
                key = match.get("group_key")
                if type(position) is not int or not 0 <= position < len(unit["events"]):
                    raise ValueError(f"{name}: invalid event_position {position!r}")
                if not isinstance(key, str) or not key:
                    raise ValueError(f"{name}: group_key must be a nonempty string")
                if not isinstance(match.get("evidence_line"), str):
                    raise ValueError(f"{name}: evidence_line must be a string")
                signature = (position, key, match["evidence_line"])
                if signature in seen:
                    continue
                seen.add(signature)
                unit_matches.append((position, match.get("text_line", 0), strategy_order, name, match))
        # Retain chronological output, including the historical error ordering.
        for position, _, _, name, match in sorted(unit_matches, key=lambda item: item[:3]):
            event = unit["events"][position]
            channel = event["channel"]
            context = unit["events"][max(0, position - 2):position + 5]
            fields = {k: v for k, v in match.items() if k != "event_position"}
            fields.setdefault("label", match["group_key"])
            fields.setdefault("evidence_kind", "tool_output" if channel == "tool_result" else
                              "tool_call" if channel.startswith("tool_call") else "reported_in_text")
            occurrences.append({**fields, "strategy": name,
                "unit_id": unit["unit_id"], "session_id": unit["session_id"],
                "source_paths": unit["source_paths"], "event_index": event["event_index"],
                "source_index": event["source_index"], "source_part_index": event["source_part_index"],
                "source_path": event["source_path"], "json_pointer": event["json_pointer"], "channel": channel,
                "preceding_command": commands[position][:2000], "hydrated_from": event.get("hydrated_from"),
                "context": [{k: e[k] for k in ("event_index", "channel", "source_path", "json_pointer")} |
                            {"text_preview": e["text"][:600], "command": e["command"][:500]} for e in context]})
    return occurrences, dict(sorted(diagnostics.items()))


def group(units: list[dict], occurrences: list[dict], strategy: str) -> tuple[list[dict], list[str], dict]:
    by_key: dict[str, list[dict]] = defaultdict(list)
    for occurrence in occurrences:
        if occurrence["strategy"] == strategy:
            key = occurrence.get("group_key", occurrence.get("error_key"))
            if not isinstance(key, str) or not key:
                raise ValueError(f"{strategy}: missing group_key")
            by_key[key].append(occurrence)
    groups = []
    for key, matches in sorted(by_key.items()):
        member_ids = sorted({m["unit_id"] for m in matches})
        session_ids = sorted({m["session_id"] for m in matches})
        groups.append({"group_id": strategy + "-" + hashlib.sha256(key.encode()).hexdigest()[:12],
            "group_key": key, "label": matches[0]["label"], "member_ids": member_ids,
            "member_session_ids": session_ids, "member_count": len(member_ids), "distinct_session_count": len(session_ids),
            "occurrence_count": len(matches), "observed_output_count": sum(m["evidence_kind"] == "tool_output" for m in matches),
            "observed_member_ids": sorted({m['unit_id'] for m in matches if m['evidence_kind'] == 'tool_output'}),
            "reported_text_count": sum(m["evidence_kind"] == "reported_in_text" for m in matches),
            "members": [{"unit_id": uid, "source_paths": next(m["source_paths"] for m in matches if m["unit_id"] == uid)} for uid in member_ids],
            "evidence": matches})
        if "error_key" in matches[0]:
            groups[-1]["error_key"] = key  # Old error consumers remain compatible.
    covered = {uid for g in groups for uid in g["member_ids"]}
    residual = sorted(u["unit_id"] for u in units if u["unit_id"] not in covered)
    summary = {"input_count": len(units), "group_count": len(groups), "covered_count": len(covered),
        "residual_count": len(residual), "multi_member_group_count": sum(g["member_count"] >= 2 for g in groups),
        "cross_session_group_count": sum(g["distinct_session_count"] >= 2 for g in groups),
        "max_group_size": max((g["member_count"] for g in groups), default=0),
        "occurrence_count": sum(g["occurrence_count"] for g in groups),
        "observed_output_count": sum(g["observed_output_count"] for g in groups),
        "observed_output_group_count": sum(bool(g['observed_member_ids']) for g in groups),
        "observed_output_covered_count": len({uid for g in groups for uid in g['observed_member_ids']})}
    return groups, residual, summary


def run(expanded_dir: Path, slices_dir: Path, output: Path, raw_root: Path | None = None,
        strategies: Iterable[str] | None = None) -> dict:
    selected = select_strategies(strategies)
    sessions, sources = load_expanded(expanded_dir)
    raw_by_session = {}
    missing_raw = []
    for unit in sessions:
        path = raw_root / sources[unit["session_id"]] if raw_root else None
        if path and path.is_file():
            unit["events"] = raw_events(path)
            unit["source_paths"] = [str(path.resolve())]
            unit["input_kind"] = "original_json" if path.suffix == '.json' else "original_jsonl"
            raw_by_session[unit["session_id"]] = {(e["source_index"], e["source_part_index"]): e for e in unit["events"]}
        else:
            missing_raw.append(sources[unit["session_id"]])
    slices = load_slices(slices_dir, raw_by_session)
    if not sessions or not slices:
        raise ValueError("Both input corpora must contain at least one unit")
    if {u["session_id"] for u in slices} != {u["session_id"] for u in sessions}:
        raise ValueError("Session and slice corpora do not refer to the same sessions")
    all_summary = {}
    inventories = {}
    session_corpus, slice_corpus = f"sessions-{len(sessions)}", f"slices-{len(slices)}"
    corpora = ((session_corpus, sessions), (slice_corpus, slices))
    for corpus, units in corpora:
        occurrences, diagnostics = scan(units, selected)
        jsonl(output / corpus / "occurrences.jsonl", occurrences)
        all_summary[corpus] = {"diagnostics": diagnostics, "strategies": {}}
        inventories[corpus] = {}
        for strategy in selected:
            groups, residual, summary = group(units, occurrences, strategy)
            inventories[corpus][strategy] = {g["group_key"] for g in groups}
            directory = output / corpus / strategy
            save(directory / "groups.json", groups)
            save(directory / "residual.json", residual)
            save(directory / "summary.json", summary)
            lines = [f"# {corpus} / {strategy}", "", STRATEGY_REGISTRY[strategy].__doc__ or strategy,
                     "", "按策略键直接分组，允许重叠；来源类型及原文保留供核验。", ""]
            for g in sorted(groups, key=lambda g: (-g["distinct_session_count"], -g["member_count"], g["group_key"])):
                lines += [f"## {g['group_id']}", "", f"分组键：`{g['group_key']}`", "",
                    f"成员 {g['member_count']}；独立 Session {g['distinct_session_count']}；输出证据 {g['observed_output_count']}；文本提及 {g['reported_text_count']}。", "",
                    *[f"- `{m['unit_id']}`：[输入文件]({Path(m['source_paths'][0]).as_posix()})" for m in g["members"]], ""]
                for e in g["evidence"][:3]:
                    lines += [f"> {e['evidence_line'].replace(chr(10), ' ')[:1200]}", "",
                        f"来源：`{e['unit_id']}`，事件 {e['source_index']}，`{e['channel']}`，`{e['json_pointer']}`。", ""]
            (directory / "report.md").write_text("\n".join(lines), encoding="utf-8")
            all_summary[corpus]["strategies"][strategy] = summary
        save(output / corpus / "input-units.json", [{k: v for k, v in u.items() if k != "events"} for u in units])
    comparison = {}
    error_comparison = {}
    for strategy in selected:
        left, right = inventories[session_corpus][strategy], inventories[slice_corpus][strategy]
        comparison[strategy] = {"shared_group_keys": len(left & right), "session_only_group_keys": sorted(left - right), "slice_only_group_keys": sorted(right - left)}
        if strategy in STRATEGIES:
            error_comparison[strategy] = {"shared_error_keys": len(left & right), "session_only_error_keys": sorted(left - right), "slice_only_error_keys": sorted(right - left)}
    all_summary["group_key_comparison"] = comparison
    if error_comparison:
        all_summary["error_key_comparison"] = error_comparison
    save(output / "summary.json", all_summary)
    save(output / "manifest.json", {"version": VERSION, "expanded_sessions_dir": str(expanded_dir.resolve()),
        "slices_dir": str(slices_dir.resolve()), "raw_sessions_root": str(raw_root.resolve()) if raw_root else None,
        "missing_original_jsonl": missing_raw, "session_input_kind": dict(Counter(u["input_kind"] for u in sessions)),
        "strategies": {name: STRATEGY_REGISTRY[name].__doc__ or name for name in selected},
        "selected_strategies": list(selected), "group_key_field": "group_key",
        "strategy_interface": "function(unit) -> matches with group_key, event_position, evidence_line",
        "event_filtering": "strategy-owned; each function receives all projected events including tool arguments",
        "slice_overlap": "only core event ranges counted", "session_overlap": "deduplicate expanded segments by original event index/part/channel",
        "error_strategy_excluded": ["record metadata", "tool call arguments as error evidence", "source code fences", "numbered source excerpts", "passing negative tests", "Read/Grep/Glob/WebSearch/WebFetch returned source/docs"],
        "output_missing_policy": "report missing payload; never infer a tool error from its metadata",
        "semantic_limits": ["same group key does not prove same Skill", "nearby events do not prove a causal chain", "text mention is not an observed outcome"],
        "llm_calls": 0, "embedding_calls": 0})
    lines = ["# 通用策略分组", "", f"{len(sessions)} 个 Session 与 {len(slices)} 个切片；运行策略：{', '.join(selected)}。", ""]
    if missing_raw:
        lines += [f"**输入限制：{len(missing_raw)} 个原始 JSONL 不可用，Session 组使用已有展开文本/调用投影；不等同于完整原始输出扫描。**", "",
                  "缺失原始文件时，部分工具结果无法恢复；不能把缺失正文的事件推断为成功或失败。", ""]
    lines += ["| 输入 | 策略 | 组数 | 有命中成员 | 多成员组 | 跨 Session 组 | 最大组 | 工具输出证据 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for corpus, _ in corpora:
        for strategy, s in all_summary[corpus]["strategies"].items():
            lines.append(f"| {corpus} | {strategy} | {s['group_count']} | {s['covered_count']}/{s['input_count']} | {s['multi_member_group_count']} | {s['cross_session_group_count']} | {s['max_group_size']} | {s['observed_output_count']} |")
    lines += ["", "分组允许重叠，不合并三种策略，也不强迫无错误命中的成员入组。JSON 保留全部命中的来源与上下文引用；单条证据展示最多 2000 字符，完整原文可回溯。Markdown 每组展示最多三个例子。", "",
              "策略命中率不是准确率或 Skill 可用率。旧错误策略保留 error_key 别名，其他策略统一使用 group_key。", "",
              "复现命令：", "", "```powershell", f'python error_clustering_experiment.py --expanded-sessions-dir "{expanded_dir.resolve()}" --slices-dir "{slices_dir.resolve()}" --output "{output.resolve()}" --strategies {" ".join(selected)}' + (f' --raw-sessions-root "{raw_root.resolve()}"' if raw_root else ''),
              "```", "", "`--list-strategies` 列出注册函数；`--strategies` 选择策略，省略时运行历史三种错误策略。"]
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return all_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded-sessions-dir", type=Path)
    parser.add_argument("--slices-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--raw-sessions-root", type=Path)
    parser.add_argument("--strategies", nargs="+", choices=tuple(STRATEGY_REGISTRY),
                        help="Run only the selected strategy functions; defaults to the historical error strategies")
    parser.add_argument("--list-strategies", action="store_true", help="List registered strategies without reading input")
    args = parser.parse_args()
    if args.list_strategies:
        for name, function in STRATEGY_REGISTRY.items():
            print(f"{name}: {function.__doc__ or function.__name__}")
        return
    missing = [name for name in ("expanded_sessions_dir", "slices_dir", "output") if getattr(args, name) is None]
    if missing:
        parser.error("required arguments: " + ", ".join("--" + name.replace("_", "-") for name in missing))
    summary = run(args.expanded_sessions_dir, args.slices_dir, args.output, args.raw_sessions_root, args.strategies)
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith('key_comparison')}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
