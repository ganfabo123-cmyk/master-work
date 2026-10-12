"""Extract cheap operation and file-object signals from materialized tool calls."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import shlex


PATH_KEYS = ("file_path", "path")
FILE_WITH_EXTENSION = re.compile(r"^[^/\\\s]+\.[A-Za-z0-9]{1,10}$")
SPECIAL_FILES = {"makefile", "dockerfile", "procfile", "license", "readme", ".gitignore", ".env", "gradlew"}
QUIET_COMMANDS = {"cd", "set-location", "pwd", "get-location", "echo", "write-host", "sleep", "start-sleep", "true"}
QUIET_COMMANDS.update({"do", "done", "for", "until", "while", "if", "then", "fi", "export", "out-null", "select-object", "where-object", "sort-object"})
RUN_COMMANDS = {"adb", "gh", "glab", "wsl", "wsl.exe", "npx", "node", "java", "docker", "kubectl", "bash", "sh", "pwsh", "powershell", "powershell.exe", "cmd", "cmd.exe"}
GIT_COMMANDS = {"add", "commit", "push", "pull", "fetch", "checkout", "switch", "branch", "merge", "status", "diff", "log", "restore", "reset"}
SIMPLE_OPERATIONS = {
    "ls": "list", "dir": "list", "get-childitem": "list", "find": "list",
    "cat": "read", "get-content": "read", "head": "read", "tail": "read", "sed": "read",
    "rg": "search", "grep": "search", "select-string": "search", "findstr": "search",
    "mkdir": "create", "new-item": "create", "touch": "create",
    "rm": "remove", "remove-item": "remove", "rmdir": "remove",
    "cp": "copy", "copy-item": "copy", "mv": "move", "move-item": "move",
    "curl": "fetch", "wget": "fetch", "invoke-webrequest": "fetch",
    "pytest": "test", "cargo": "build", "go": "build", "make": "build",
}


def normalized_file(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().strip("'\"`(),;[]{}")
    if not token or "://" in token or token.startswith(("$", "<", "-")):
        return None
    token = re.sub(r":\d+(?::\d+)?$", "", token).replace("\\", "/").rstrip("/")
    name = token.rsplit("/", 1)[-1].casefold()
    if re.fullmatch(r"\d+(?:\.\d+)+", name):
        return None
    if not name or "*" in name or "?" in name or len(name) > 100:
        return None
    if name not in SPECIAL_FILES and not FILE_WITH_EXTENSION.fullmatch(name):
        return None
    if name in {".", ".."} or name.startswith(".") and name not in SPECIAL_FILES:
        return None
    return name


def file_type(name: str) -> str:
    return Path(name).suffix or name


def split_segments(command: str) -> list[str]:
    # Split at shell separators outside simple quotes; never execute the command.
    command = command.split("<<", 1)[0]
    parts, current, quote = [], [], None
    for char in command[:12000]:
        if char in "\"'":
            quote = None if quote == char else char if quote is None else quote
            current.append(char)
        elif quote is None and char in ";|&\r\n":
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts[:40]


def shell_words(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=False)
    except ValueError:
        return segment.split()


def operation_for(words: list[str]) -> str | None:
    if not words:
        return None
    command = words[0].strip("'\"").replace("\\", "/").rsplit("/", 1)[-1].casefold()
    if not command or command.startswith(("#", "$")) or command in QUIET_COMMANDS:
        return None
    args = [word.strip("'\"").casefold() for word in words[1:]]
    positional = [word for word in args if not word.startswith("-")]
    subcommand = positional[0] if positional else ""
    if command == "git":
        action = next((word for word in positional if word in GIT_COMMANDS), None)
        return f"git:{action}" if action else "git:other"
    if command in {"npm", "pnpm", "yarn", "bun"}:
        action = positional[1] if subcommand == "run" and len(positional) > 1 else subcommand
        if action in {"build", "test", "lint", "install", "dev", "start", "typecheck"}:
            return f"{action}:{command}"
        return f"run:{command}"
    if command in {"gradle", "gradlew", "gradlew.bat"}:
        action = "test" if "test" in subcommand else "build" if any(word in subcommand for word in ("build", "assemble")) else "run"
        return f"{action}:gradle"
    if command in {"python", "python3", "py", "pytest"}:
        if command == "pytest" or "pytest" in args:
            return "test:pytest"
        if "pip" in args and "install" in args:
            return "install:pip"
        return "run:python"
    if command in {"make", "cargo", "go", "odin"}:
        action = "test" if subcommand == "test" else "build" if subcommand in {"build", "compile", "release"} or command == "make" else "run"
        return f"{action}:{command}"
    if command in {"clang", "clang++", "gcc", "g++", "cc", "c++", "javac"}:
        return "compile"
    if command in SIMPLE_OPERATIONS:
        return SIMPLE_OPERATIONS[command]
    return f"run:{command}" if command in RUN_COMMANDS or command.endswith((".exe", ".sh")) else None


def extract_tool(event: dict) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    category = event.get("category", "")
    if not category.startswith("tool_call:"):
        return [], [], []
    tool = event.get("tool_name") or category.removeprefix("tool_call:")
    args = event.get("arguments")
    if not isinstance(args, dict):
        return [], [], []
    operations = []
    targets = []
    pairs = []
    direct = {"Edit": "edit", "Write": "write", "Read": "read", "Grep": "search", "Glob": "list"}
    if tool in direct:
        operations.append(direct[tool])
        for key in PATH_KEYS:
            target = normalized_file(args.get(key))
            if target:
                targets.append(target)
                pairs.append((direct[tool], target))
    elif tool in {"Bash", "PowerShell"} and isinstance(args.get("command"), str):
        for segment in split_segments(args["command"]):
            words = shell_words(segment)
            operation = operation_for(words)
            if not operation:
                continue
            operations.append(operation)
            if len(segment) <= 600:
                segment_targets = [target for word in words[1:40] if (target := normalized_file(word))]
                targets.extend(segment_targets)
                pairs.extend((operation, target) for target in segment_targets)
    return list(dict.fromkeys(operations)), list(dict.fromkeys(targets)), list(dict.fromkeys(pairs))


def run(input_dir: Path, output_dir: Path) -> dict:
    mappings = json.loads((input_dir / "slice-events.json").read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = Counter()
    rows = []
    with (output_dir / "tool-events.jsonl").open("w", encoding="utf-8") as stream:
        for mapping in mappings:
            source = json.loads(Path(mapping["source_file"]).read_text(encoding="utf-8"))
            start = mapping.get("core_start_event") or mapping["start_event"]
            end = mapping.get("core_end_event") or mapping["end_event"]
            operations = Counter()
            targets = Counter()
            types = Counter()
            pairs = Counter()
            type_pairs = Counter()
            examples = defaultdict(list)
            for offset, event in enumerate(source["events"]):
                index = mapping["start_event"] + offset
                if not start <= index <= end or not event.get("category", "").startswith("tool_call:"):
                    continue
                summary["tool_calls"] += 1
                op, obj, op_obj = extract_tool(event)
                summary["tool_calls_with_operation"] += bool(op)
                summary["tool_calls_with_target"] += bool(obj)
                event_id = mapping["event_ids"][offset]
                item = {"event_id": event_id, "slice_id": mapping["slice_id"], "tool_name": event.get("tool_name"), "operations": op, "targets": obj, "target_types": list(dict.fromkeys(file_type(target) for target in obj)), "operation_targets": [{"operation": action, "target": target} for action, target in op_obj]}
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
                operations.update(op)
                targets.update(obj)
                types.update({file_type(target) for target in obj})
                type_pairs.update({(action, file_type(target)) for action, target in op_obj})
                for pair in op_obj:
                    pairs[pair] += 1
                    if len(examples[pair]) < 3:
                        examples[pair].append(event_id)
            rows.append({
                "slice_id": mapping["slice_id"],
                "source_file": mapping["source_file"],
                "operation_events": dict(operations.most_common()),
                "target_events": dict(targets.most_common()),
                "file_type_events": dict(types.most_common()),
                "operation_file_type_events": [
                    {"operation": action, "file_type": kind, "event_count": count}
                    for (action, kind), count in type_pairs.most_common()
                ],
                "operation_target_events": [
                    {"operation": action, "target": target, "event_count": count, "example_event_ids": examples[(action, target)]}
                    for (action, target), count in pairs.most_common()
                ],
            })
    with (output_dir / "slice-tool-signals.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    result = {"slice_count": len(rows), **summary, "slices_with_operation_target": sum(bool(row["operation_target_events"]) for row in rows)}
    (output_dir / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 工具调用的操作与对象", "", "仅切片核心事件；每个工具调用对同一操作或对象最多计一次。", "", "| 切片 | 操作（前 6） | 操作＋目标文件（前 6） |", "|---|---|---|"]
    for row in rows:
        op = ", ".join(f"{key}:{count}" for key, count in list(row["operation_events"].items())[:6]) or "—"
        pair = ", ".join(f"{p['operation']}+{p['target']}:{p['event_count']}" for p in row["operation_target_events"][:6]) or "—"
        lines.append(f"| `{row['slice_id']}` | {op} | {pair} |")
    (output_dir / "slice-tool-signals.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# 工具操作与对象信号\n\n"
        "读取事件级统计中的切片映射，再只看原始切片核心区间的工具调用。"
        "Edit/Write/Read/Grep/Glob 使用已知参数字段；Bash/PowerShell 按命令分隔符解析常见命令。"
        "路径统一取小写文件名，保留扩展名，舍弃父目录与不确定的目录参数。"
        "另列文件类型与操作+文件类型计数，便于跨项目比较。"
        "每个事件对同一操作、目标或组合最多计一次。"
        "`tool-events.jsonl` 提供可追溯事件；`slice-tool-signals.jsonl` 汇总切片；Markdown 便于查看。"
        "命令解析是保守的文本规则，不执行命令，也不从工具返回推断成功。"
        "操作与文件目标来自同一命令段；复杂脚本仍可能产生误配。\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.input_dir, args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
