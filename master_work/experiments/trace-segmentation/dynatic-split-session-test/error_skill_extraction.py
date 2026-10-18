"""Extract candidate Skills from original error-code groups in three input arms.

Standard library only. No network is used in --prepare-only mode. The model can
only read its arm's snapshotted files; trace commands are never executed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import select_group_slices as selector

VERSION = "error-skill-extraction-v1"
DEFAULT_USER_AGENT = "skill-extraction/1.0"
HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ARMS = ("A-original", "B-selected", "C-context-collapsed")
MALFORMED_RETRIES = 3
STRING = {"type": "string", "minLength": 1}


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


SECTION_TOOLS = {"write_goal": "Goal", "write_scope": "Scope", "write_inputs": "Inputs",
                 "write_outputs": "Outputs", "write_preconditions": "Preconditions",
                 "write_procedure": "Procedure", "write_decision_rules": "Decision Rules",
                 "write_invariants": "Invariants", "write_common_failures": "Common Failures",
                 "write_verification": "Verification", "write_examples": "Examples",
                 "write_evidence": "Evidence"}
TOOL_MARKUP = re.compile(r"<tool_call>|</tool_call>|<function=|<parameter=")
TOOLS = [
    {"type": "function", "function": {"name": "read_trace", "description":
     "Read the entire allowed input file without truncation. No hidden content or other arms can be read.",
     "parameters": obj(file_id=STRING)}},
    {"type": "function", "function": {"name": "search_trace", "description":
     "Search visible string values in raw records or slice events. Return every matching string in full "
     "with all match positions and original source indices. Never restore hidden payloads.",
     "parameters": obj(file_id=STRING, pattern=STRING, regex={"type": "boolean"})}},
    {"type": "function", "function": {"name": "read_event", "description":
     "Read a visible event/part by original zero-based source_index and source_part_index. "
     "Return the complete event without truncation. Does not restore collapsed content.",
     "parameters": obj(file_id=STRING, source_index={"type": "integer", "minimum": 0},
                       source_part_index={"type": ["integer", "null"], "minimum": 0})}},
    {"type": "function", "function": {"name": "write_header", "description":
     "Start one candidate Skill: write its SKILL.md frontmatter and title. Call this first for each Skill. "
     "description is one line: 'Use when ... Helps the agent ... Requires ... Do not use when ....'",
     "parameters": obj(name=STRING, title=STRING, description=STRING)}},
    *[{"type": "function", "function": {"name": tool, "description":
       f"Write the '## {title}' section of SKILL.md for skill `name`. Call once per section; "
       f"calling again overwrites only this section.",
       "parameters": obj(name=STRING, content=STRING)}} for tool, title in SECTION_TOOLS.items()],
    {"type": "function", "function": {"name": "no_skill", "description":
     "Declare that no reusable Skill can be extracted from this input, with the reason. "
     "Use it instead of finishing without any SKILL.md.",
     "parameters": obj(reason=STRING)}},
]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_schema(value, schema, where="arguments"):
    """Validate the small JSON Schema subset used by these tools without dependencies."""
    typ = schema.get("type")
    types = typ if isinstance(typ, list) else [typ]
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list),
              "string": isinstance(value, str), "integer": type(value) is int,
              "boolean": type(value) is bool, "null": value is None}
    if not any(checks.get(t, False) for t in types):
        raise ValueError(f"{where}: expected {typ}")
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{where}: invalid choice")
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            raise ValueError(f"{where}: empty text")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValueError(f"{where}: invalid format")
    if type(value) is int:
        if value < schema.get("minimum", value):
            raise ValueError(f"{where}: outside range")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{where}: too few items")
        for index, item in enumerate(value):
            validate_schema(item, schema["items"], f"{where}[{index}]")
    if isinstance(value, dict):
        if set(schema["required"]) - value.keys():
            raise ValueError(f"{where}: missing fields {sorted(set(schema['required']) - value.keys())}")
        if set(value) - schema["properties"].keys():
            raise ValueError(f"{where}: unexpected fields")
        for key, item in value.items():
            validate_schema(item, schema["properties"][key], f"{where}.{key}")


def string_values(value):
    """Return actual payload strings, excluding collapsed-body location metadata."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from string_values(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in {"collapsed_content", "signature"}:
                yield from string_values(item)


def source_parts(path, kind):
    """Yield (original source index, part index, category, visible payload)."""
    if kind == "slice":
        for event in read_json(path)["events"]:
            yield (event["source_index"], event.get("source_part_index", 0),
                   event.get("category", "unknown"), event)
        return
    path = Path(path)
    if path.suffix == ".jsonl":
        rows = [(i, json.loads(line)) for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines())
                if line.strip()]
    else:
        rows = list(enumerate(read_json(path)["messages"]))
    for index, row in rows:
        message = row.get("message", row)
        role = row.get("info", {}).get("role", message.get("role", row.get("role", row.get("type", "unknown"))))
        content = message.get("content", row.get("parts"))
        if content is None:
            yield index, 0, "record:" + str(role), row
            continue
        parts = content if isinstance(content, list) else [{"type": "text", "text": content}]
        for part_index, part in enumerate(parts):
            if not isinstance(part, dict):
                continue
            typ = part.get("type", "text")
            category = ("tool_call:" + part.get("name", part.get("tool", "unknown"))
                        if typ in {"tool", "tool_use", "tool_call"} else
                        "tool_result" if typ in {"tool_result", "tool-result"} or role == "tool" else
                        str(role) + "_" + typ)
            # OpenCode input and result share one original part.
            if typ == "tool":
                state = part.get("state", {})
                yield index, part_index, category, {"arguments": state.get("input", {}), "tool": part.get("tool")}
                yield index, part_index, "tool_result", {k: state[k] for k in ("output", "error") if k in state}
            else:
                yield index, part_index, category, part


class ArmReader:
    def __init__(self, files):
        self.files = {f["file_id"]: f for f in files}
        self.texts = {}
        self.parts = {}
        self.touched = set()
        self.read_ranges = {fid: [] for fid in self.files}

    def file(self, fid):
        if fid not in self.files:
            raise ValueError("Unknown file_id; only this arm's files are available")
        return self.files[fid]

    def text(self, fid):
        if fid not in self.texts:
            self.texts[fid] = Path(self.file(fid)["path"]).read_text(encoding="utf-8-sig")
        return self.texts[fid]

    def events(self, fid):
        if fid not in self.parts:
            self.parts[fid] = list(source_parts(self.file(fid)["path"], self.file(fid)["kind"]))
        return self.parts[fid]

    def read(self, file_id):
        text = self.text(file_id)
        self.touched.add(file_id)
        self.read_ranges[file_id].append([0, len(text)])
        return {"file_id": file_id, "total_chars": len(text), "content": text}

    def search(self, file_id, pattern, regex):
        expression = re.compile(pattern if regex else re.escape(pattern), re.IGNORECASE)
        matches = []
        for index, part, category, payload in self.events(file_id):
            for text in string_values(payload):
                positions = [[match.start(), match.end()] for match in expression.finditer(text)]
                if positions:
                    matches.append({"source_index": index, "source_part_index": part, "category": category,
                                    "text": text, "match_spans": positions})
        self.touched.add(file_id)
        return {"file_id": file_id, "matches": matches}

    def read_event(self, file_id, source_index, source_part_index):
        selected = [{"source_index": i, "source_part_index": p, "category": c, "payload": v}
                    for i, p, c, v in self.events(file_id) if i == source_index and
                    (source_part_index is None or p == source_part_index)]
        if not selected:
            raise ValueError("Original source event is absent from this input file")
        text = json.dumps(selected, ensure_ascii=False)
        self.touched.add(file_id)
        return {"file_id": file_id, "source_index": source_index, "source_part_index": source_part_index,
                "total_chars": len(text), "content": text}

def file_entry(path, session_id, kind, content_mode):
    path = Path(path).resolve()
    return {"file_id": session_id + ("__" + path.stem if kind == "slice" else "__original"),
            "session_id": session_id, "kind": kind, "content_mode": content_mode,
            "path": str(path), "bytes": path.stat().st_size, "sha256": digest(path),
            "chars": len(path.read_text(encoding="utf-8-sig"))}


def raw_path(root, session_id):
    harness, sid = session_id.split("__", 1)
    if re.search(r"[\\/:]", harness + sid) or harness in {".", ".."} or sid in {".", ".."}:
        raise ValueError("Invalid original trace ID")
    matches = [p for p in (root / harness / (sid + ".jsonl"), root / harness / (sid + ".json")) if p.is_file()]
    if len(matches) != 1:
        raise ValueError(f"Expected one original trace for {session_id}")
    return matches[0]


def prepare(groups_path, slices_dir, sessions_dir, output, prompt_path, selection_strategy="group-context"):
    groups = read_json(groups_path)
    if not isinstance(groups, list) or not groups:
        raise ValueError("Expected nonempty original error-code groups.json")
    if output.exists():
        raise ValueError("Output already exists: use --resume or a new --output")
    group_ids = [g["group_id"] for g in groups]
    if len(set(group_ids)) != len(groups) or any(not re.fullmatch(r"native-code-[a-z0-9]+", gid) for gid in group_ids):
        raise ValueError("This runner accepts original native-code groups only")
    ids = sorted({sid for g in groups for sid in g["member_session_ids"]})
    originals = {sid: raw_path(sessions_dir, sid) for sid in ids}
    # Preflight all mappings before producing a partially prepared experiment.
    candidates = {sid: selector.load_candidates(slices_dir, sid) for sid in ids}
    if sys.platform == "win32":
        planned = [output / g["group_id"] / "selection-C" / "slices" / sid / Path(c["source_path"]).name
                   for g in groups for sid in g["member_session_ids"] for c in candidates[sid]]
        if any(len(str(p.resolve())) >= 260 for p in planned):
            raise ValueError("Output path is too long on Windows; choose a shorter --output such as C:/skill-runs/run1")
    restoration_path = slices_dir / "payload-restoration.json"
    if restoration_path.is_file():
        hashes = {s["harness"] + "__" + s["session_id"]: s["source_sha256"]
                  for s in read_json(restoration_path)["sessions"]}
        for sid, original in originals.items():
            if hashes.get(sid) != digest(original):
                raise ValueError(f"Original trace and restored slices have different source hashes: {sid}")
    for group in groups:
        if set(group.get("member_ids", group["member_session_ids"])) != set(group["member_session_ids"]):
            raise ValueError("Expected original groups, not slice groups")
        for sid in group["member_session_ids"]:
            selected = selector.select(group, sid, candidates[sid], selection_strategy)
            if not selected["selected_count"] or any(r["reason"] == "group_hit" for r in selected["unmapped_references"]):
                raise ValueError(f"Unmapped error evidence for {group['group_id']}/{sid}")
    if not prompt_path.is_file():
        raise ValueError("Missing extraction prompt")
    output.mkdir(parents=True)
    shutil.copyfile(prompt_path, output / "prompt.txt")
    save(output / "groups.json", groups)
    save(output / "tools.json", TOOLS)
    snapshots = {}
    for sid, source in originals.items():
        destination = output / "inputs" / "originals" / source.parent.name / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        snapshots[sid] = file_entry(destination, sid, "original", "full") | {"original_path": str(source.resolve())}
    experiments = []
    for group in sorted(groups, key=lambda g: g["group_id"]):
        gid = group["group_id"]
        selected = selector.run(output / "groups.json", gid, group["member_session_ids"], slices_dir,
                                output / gid / "selection-B", selection_strategy, "selected-only")
        collapsed = selector.run(output / "groups.json", gid, group["member_session_ids"], slices_dir,
                                 output / gid / "selection-C", selection_strategy, "selected-full-rest-collapsed")
        arm_files = {
            "A-original": [snapshots[sid] for sid in sorted(group["member_session_ids"])],
            "B-selected": [file_entry(s["output_path"], s["session_id"], "slice", s["content_mode"])
                           for s in selected["exported_slices"]],
            "C-context-collapsed": [file_entry(s["output_path"], s["session_id"], "slice", s["content_mode"])
                                    for s in collapsed["exported_slices"]],
        }
        for arm in ARMS:
            directory = output / gid / arm
            manifest = {"group_id": gid, "error_key": group.get("error_key", group.get("group_key")),
                        "arm": arm, "session_ids": sorted(group["member_session_ids"]), "files": arm_files[arm],
                        "error_source_indices": {sid: sorted({e["source_index"] for e in group["evidence"]
                            if e["session_id"] == sid}) for sid in group["member_session_ids"]},
                        "selected_slice_count": selected["selected_count"],
                        "unmapped_context_references": selected["unmapped_references"]}
            save(directory / "input-manifest.json", manifest)
            experiments.append({"group_id": gid, "arm": arm, "input_manifest": str((directory / "input-manifest.json").resolve()),
                                "input_manifest_sha256": digest(directory / "input-manifest.json")})
    manifest = {"version": VERSION, "created_at": now(), "status": "prepared", "group_count": len(groups),
                "experiment_count": len(experiments), "arms": list(ARMS), "experiments": experiments,
                "inputs": {"groups": str(groups_path.resolve()), "slices_dir": str(slices_dir.resolve()),
                           "sessions_dir": str(sessions_dir.resolve())}, "groups_sha256": digest(output / "groups.json"),
                "prompt_sha256": digest(output / "prompt.txt"), "tools_sha256": digest(output / "tools.json"),
                "selection_strategy": selection_strategy, "skill_status": "candidate_needs_review"}
    save(output / "manifest.json", manifest)
    save(output / "preflight.json", {"status": "prepared_no_api_calls", "group_count": len(groups),
        "experiment_count": len(experiments), "api_calls": 0,
        "groups": [{"group_id": g["group_id"], "error_key": g.get("error_key", g.get("group_key")),
            "session_count": len(g["member_session_ids"]),
            "arms": {arm: {"file_count": len(arm_input["files"]),
                "input_bytes": sum(f["bytes"] for f in arm_input["files"]),
                "full_file_count": sum(f["content_mode"] == "full" for f in arm_input["files"]),
                "collapsed_file_count": sum(f["content_mode"] == "collapsed" for f in arm_input["files"]),
                "unmapped_context_count": len(arm_input["unmapped_context_references"])}
                for arm in ARMS for arm_input in [read_json(output / g["group_id"] / arm / "input-manifest.json")]}}
            for g in sorted(groups, key=lambda g: g["group_id"])]})
    return manifest


def endpoint(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url must be an HTTP(S) API root without credentials, query or fragment")
    base = base_url.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def load_config(path, require_credentials=True):
    # Only identity/connection settings are accepted. Old generation controls,
    # token/round budgets, sampling controls and extra_body cannot reach the API.
    original = read_json(path)
    config = {k: v for k, v in original.items() if k in
              {"api_key", "base_url", "model", "sessionHeader", "userAgent"}}
    for field in ("api_key", "base_url", "model"):
        if require_credentials and (not isinstance(config.get(field), str) or not config[field].strip()):
            raise ValueError(f"Fill {field} in your configuration before running API experiments")
    if config.get("base_url"):
        endpoint(config["base_url"])
    session_header = config.get("sessionHeader", "")
    if not isinstance(session_header, str) or (session_header and (
            not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", session_header) or
            session_header.lower() in {"authorization", "content-type", "content-length", "host"})):
        raise ValueError("sessionHeader must be a valid custom HTTP header name, or an empty string")
    config.setdefault("userAgent", DEFAULT_USER_AGENT)
    if not isinstance(config["userAgent"], str) or not config["userAgent"].strip() or any(
            ord(c) < 32 or ord(c) > 126 for c in config["userAgent"]):
        raise ValueError("userAgent must be nonempty printable ASCII HTTP header text")
    return config


def public_config(config):
    return {"userAgent": DEFAULT_USER_AGENT, **{k: v for k, v in config.items()
            if k in {"base_url", "model", "sessionHeader", "userAgent"}}}


def request_headers(config):
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + config["api_key"],
               "User-Agent": config.get("userAgent", DEFAULT_USER_AGENT)}
    if config.get("sessionHeader"):
        if not config.get("_session_id"):
            raise ValueError("Missing per-experiment Session ID for sessionHeader")
        headers[config["sessionHeader"]] = config["_session_id"]
    return headers


def api_request(payload, config):
    request = urllib.request.Request(endpoint(config["base_url"]),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers=request_headers(config))
    try:
        with urllib.request.urlopen(request) as reply:
            return json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if config.get("api_key"):
            detail = detail.replace(config["api_key"], "[REDACTED]")
        detail = re.sub(r"(?i)(bearer\s+)[^\s\"'<>]+", r"\1[REDACTED]", detail)
        detail = " ".join(detail.split())
        raise RuntimeError(f"API HTTP {error.code}: {detail or 'empty error body'}; no automatic retry was made") from None
    except urllib.error.URLError:
        raise RuntimeError("API connection failed; provider may have processed the request; usage unknown") from None


def usage_record(response):
    usage = response.get("usage") or {}
    numeric = lambda x: x if type(x) is int and x >= 0 else None
    input_tokens = numeric(usage.get("prompt_tokens"))
    cached = numeric((usage.get("prompt_tokens_details") or {}).get("cached_tokens"))
    return {"input_tokens": input_tokens, "cached_input_tokens": cached,
            "noncached_input_tokens": input_tokens - cached if input_tokens is not None and cached is not None and cached <= input_tokens else None,
            "output_tokens": numeric(usage.get("completion_tokens")), "total_tokens": numeric(usage.get("total_tokens")),
            "reasoning_tokens": numeric((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")),
            "provider_usage": usage}


def aggregate_usage(records):
    fields = ("input_tokens", "cached_input_tokens", "noncached_input_tokens", "output_tokens", "total_tokens", "reasoning_tokens")
    return {field: {"known_sum": sum(r[field] for r in records if r.get(field) is not None),
                    "missing_request_count": sum(r.get(field) is None for r in records),
                    "complete": all(r.get(field) is not None for r in records)} for field in fields}


def log_round(directory, text):
    with (directory / "rounds.log").open("a", encoding="utf-8") as log:
        log.write(text + "\n")


SKILL_SECTIONS = ["Goal", "Scope", "Inputs", "Outputs", "Preconditions", "Procedure",
                  "Decision Rules", "Invariants", "Common Failures", "Verification", "Examples", "Evidence"]


def check_name(name):
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name):
        raise ValueError("name must be lowercase letters, digits and hyphens")


def skill_path(directory, name):
    return directory / "skills" / name / "SKILL.md"


def check_section(title, body):
    problems = []
    if len(re.sub(r"\s+", "", body)) < 20:
        problems.append(f"'## {title}' has no real content")
    if "TODO" in body or "待补充" in body:
        problems.append(f"'## {title}' still contains a placeholder")
    if title == "Procedure" and "### Step" not in body:
        problems.append("Procedure needs at least one '### Step N' subsection")
    if title == "Evidence":
        for kind in ("problem", "action", "verification"):
            if kind not in body.lower():
                problems.append(f"Evidence lacks a '{kind}' entry")
    return problems


def check_skill(name, text):
    frontmatter = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not frontmatter:
        return ["missing YAML frontmatter at the top"]
    fields = dict(line.split(":", 1) for line in frontmatter.group(1).splitlines() if ":" in line)
    problems = []
    if fields.get("name", "").strip() != name:
        problems.append(f"frontmatter name must be exactly '{name}'")
    if "Use when" not in fields.get("description", ""):
        problems.append("frontmatter description must contain 'Use when'")
    if not re.search(r"^# \S", text, re.M):
        problems.append("missing title line '# ...'")
    headings = list(re.finditer(r"^## (.+)$", text, re.M))
    for section in SKILL_SECTIONS:
        match = next((h for h in headings if h.group(1).strip() == section), None)
        if match is None:
            problems.append(f"missing section '## {section}'")
            continue
        index = headings.index(match)
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        problems += check_section(section, text[match.end():end])
    return problems


def valid_skills(directory):
    return [path for path in sorted((directory / "skills").glob("*/SKILL.md"))
            if not check_skill(path.parent.name, path.read_text(encoding="utf-8"))]


def has_skill(directory):
    return bool(valid_skills(directory))


def render_skill_md(name, part):
    lines = ["---", f"name: {name}", f"description: {part['description']}", "---", f"# {part['title']}", ""]
    for title in SKILL_SECTIONS:
        if title in part["sections"]:
            lines += [f"## {title}", part["sections"][title], ""]
    return "\n".join(lines)


def parse_text_tool_calls(content, tools):
    schemas = {tool["function"]["name"]: tool["function"]["parameters"]["properties"] for tool in tools}
    calls = []
    for block in re.findall(r"<tool_call>(.*?)</tool_call>", content, re.S):
        found = re.search(r"<function=([^>\s]+)>(.*?)</function>", block, re.S)
        if not found or found.group(1) not in schemas:
            return []
        arguments = {}
        for key, raw in re.findall(r"<parameter=([^>\s]+)>(.*?)</parameter>", found.group(2), re.S):
            kind = schemas[found.group(1)].get(key, {}).get("type")
            kinds = kind if isinstance(kind, list) else [kind]
            if "null" in kinds and raw.strip() == "null":
                arguments[key] = None
            elif "integer" in kinds and raw.strip().isdigit():
                arguments[key] = int(raw.strip())
            elif "boolean" in kinds and raw.strip().lower() in ("true", "false"):
                arguments[key] = raw.strip().lower() == "true"
            else:
                arguments[key] = raw.strip("\n")
        calls.append({"id": f"text-{len(calls) + 1}", "type": "function",
                      "function": {"name": found.group(1), "arguments": json.dumps(arguments, ensure_ascii=False)}})
    return calls


def describe_round(index, sent, request_chars, message_count, response, record):
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    lines = [f"=== request {index:04d} | sent {sent} | messages {message_count} | request_chars {request_chars} ===",
             f"finish_reason: {choice.get('finish_reason')}",
             f"usage: prompt={record['input_tokens']} cached={record['cached_input_tokens']} "
             f"completion={record['output_tokens']} reasoning={record['reasoning_tokens']}",
             "--- reasoning_content ---", str(message.get("reasoning_content") or ""),
             "--- content ---", str(message.get("content") or "")]
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        lines += [f"--- tool_call {call.get('id')}: {function.get('name')} ---", str(function.get("arguments"))]
    return "\n".join(lines) + "\n"


def initial_messages(prompt, inputs):
    catalog = copy.deepcopy(inputs)
    for entry in catalog["files"]:
        # Paths do not confer filesystem access: tool file_id is the sole authority.
        entry.pop("path", None)
    return [{"role": "system", "content": prompt}, {"role": "user", "content":
            "本次只分析以下输入文件。用 read_trace/search_trace/read_event 读取证据，再通过 write_header 和各章节工具逐节写出 SKILL.md；写完后直接回复总结结束。\n" +
            json.dumps(catalog, ensure_ascii=False)}]


def extract_arm(directory, prompt, config, transport=api_request):
    inputs = read_json(directory / "input-manifest.json")
    # One provider session per extraction attempt; tool rounds share that session.
    request_config = dict(config)
    session_id = str(uuid.uuid4()) if config.get("sessionHeader") else None
    if session_id:
        request_config["_session_id"] = session_id
        save(directory / "api-session.json", {"header_name": config["sessionHeader"], "session_id": session_id,
             "group_id": inputs["group_id"], "arm": inputs["arm"]})
    reader = ArmReader(inputs["files"])
    messages = initial_messages(prompt, inputs)
    records, accesses = [], []
    started, clock = now(), time.perf_counter()
    parts = {}
    declared = None
    malformed_retries = 0
    error = None
    try:
        request_index = 0
        while True:
            request_index += 1
            payload = {"model": config["model"], "messages": messages, "tools": TOOLS,
                       "tool_choice": "auto", "stream": False}
            request_dir = directory / "requests" / f"{request_index:04d}"
            # Exact request body, no Authorization header/API key.
            save(request_dir / "request.json", payload)
            sent, api_clock = now(), time.perf_counter()
            request_chars = len(json.dumps(payload, ensure_ascii=False))
            try:
                response = transport(payload, request_config)
            except Exception as failure:
                log_round(directory, f"=== request {request_index:04d} | sent {sent} | messages {len(messages)} | request_chars {request_chars} ===\n"
                          f"TRANSPORT FAILED: {type(failure).__name__}: {failure}\n{traceback.format_exc()}")
                records.append({"request_index": request_index, "sent_at": sent, "finished_at": now(),
                                "api_seconds": time.perf_counter() - api_clock, **usage_record({}),
                                "status": "transport_failed_usage_unknown"})
                raise
            records.append({"request_index": request_index, "sent_at": sent, "finished_at": now(),
                            "api_seconds": time.perf_counter() - api_clock, **usage_record(response),
                            "status": "received", "response_id": response.get("id"), "model": response.get("model")})
            save(request_dir / "response.json", response)
            # Persist usage as soon as an API response arrives, even on malformed output.
            save(directory / "request-costs.json", records)
            log_round(directory, describe_round(request_index, sent, request_chars, len(messages), response, records[-1]))
            choice = response["choices"][0]
            if choice.get("finish_reason") == "content_filter":
                raise ValueError("Provider filtered the response")
            message = choice["message"]
            calls = message.get("tool_calls") or []
            if not calls and TOOL_MARKUP.search(message.get("content") or ""):
                calls = parse_text_tool_calls(message["content"], TOOLS)
                if calls:
                    message["tool_calls"] = calls
                    log_round(directory, f"RECOVERED: {len(calls)} tool call(s) parsed from content text; structured tool_calls was null")
            malformed = None
            if choice.get("finish_reason") == "tool_calls" and not calls:
                malformed = "finish_reason is tool_calls but structured tool_calls is empty"
            elif not calls and TOOL_MARKUP.search(message.get("content") or ""):
                malformed = "Provider returned tool-call markup as text instead of structured tool_calls"
            if malformed:
                if malformed_retries < MALFORMED_RETRIES:
                    malformed_retries += 1
                    messages.append({"role": "user", "content": "上一条回复无效：" + malformed + "。需要调用工具时，请使用结构化的工具调用发出，不要把工具调用写成正文文本。请重新回复。"})
                    log_round(directory, f"RETRY {malformed_retries}/{MALFORMED_RETRIES}: {malformed}; feedback sent to model")
                    continue
                raise ValueError(f"{malformed} (after {MALFORMED_RETRIES} retries)")
            malformed_retries = 0
            assistant_message = {k: message[k] for k in ("role", "content", "tool_calls", "reasoning_content") if k in message}
            assistant_message.setdefault("role", "assistant")
            messages.append(assistant_message)
            if not calls:
                if declared is not None or has_skill(directory):
                    break
                pending = {name: [t for t in SKILL_SECTIONS if t not in part["sections"]] for name, part in parts.items()}
                status = json.dumps(pending, ensure_ascii=False) if pending else "尚未调用 write_header"
                messages.append({"role": "user", "content": "尚无完整的 SKILL.md。未完成的 Skill 及缺失章节：" + status +
                                 "。请用结构化工具调用继续写；若确认没有可提取的 Skill，调用 no_skill 并写明原因，不要直接结束。"})
                log_round(directory, f"BLOCKED: finish without a complete SKILL.md; pending={pending}")
                continue
            for call in calls:
                name = call.get("function", {}).get("name")
                tool = next((t for t in TOOLS if t["function"]["name"] == name), None)
                tool_result = None
                try:
                    if call.get("type") != "function" or tool is None:
                        raise ValueError(f"unknown or invalid tool call: type={call.get('type')!r}, name={name!r}")
                    try:
                        arguments = json.loads(call["function"]["arguments"])
                    except (KeyError, TypeError, ValueError):
                        raise ValueError("tool call arguments are not valid JSON") from None
                    if not isinstance(arguments, dict):
                        raise ValueError("tool call arguments must be a JSON object")
                    validate_schema(arguments, tool["function"]["parameters"])
                    if name == "read_trace":
                        tool_result = reader.read(**arguments)
                    elif name == "search_trace":
                        tool_result = reader.search(**arguments)
                    elif name == "read_event":
                        tool_result = reader.read_event(**arguments)
                    elif name == "no_skill":
                        declared = arguments["reason"]
                        tool_result = {"declared": True}
                    elif name == "write_header":
                        check_name(arguments["name"])
                        if "Use when" not in arguments["description"]:
                            raise ValueError("description must contain 'Use when'")
                        parts[arguments["name"]] = {"title": arguments["title"],
                                                    "description": arguments["description"], "sections": {}}
                        tool_result = {"accepted": True, "sections_to_write": SKILL_SECTIONS}
                    else:
                        title = SECTION_TOOLS[name]
                        check_name(arguments["name"])
                        part = parts.get(arguments["name"])
                        if part is None:
                            raise ValueError("call write_header for this name first")
                        problems = check_section(title, arguments["content"])
                        if problems:
                            raise ValueError("; ".join(problems))
                        part["sections"][title] = arguments["content"].strip()
                        path = skill_path(directory, arguments["name"])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(render_skill_md(arguments["name"], part), encoding="utf-8")
                        tool_result = {"written": str(path.resolve()),
                                       "missing_sections": [t for t in SKILL_SECTIONS if t not in part["sections"]]}
                except Exception as failure:
                    tool_result = {"error": f"{type(failure).__name__}: {failure}", "accepted": False}
                accesses.append({"request_index": request_index, "tool_call_id": call.get("id"),
                                 "name": name, "arguments": call.get("function", {}).get("arguments"),
                                 "result": tool_result})
                log_round(directory, f"--- tool result {name}: chars={len(json.dumps(tool_result, ensure_ascii=False))} "
                          f"accepted={tool_result.get('accepted')} error={tool_result.get('error')}")
                messages.append({"role": "tool", "tool_call_id": call.get("id"),
                                 "content": json.dumps(tool_result, ensure_ascii=False)})
            save(directory / "tool-log.json", accesses)
        exported = []
        for path in valid_skills(directory):
            item = {"status": "candidate_needs_review", "name": path.parent.name, "group_id": inputs["group_id"],
                    "error_key": inputs["error_key"], "arm": inputs["arm"], "model": config["model"],
                    "run_directory": str(directory.parents[1].resolve()), "markdown_path": str(path.resolve()),
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "source_files": inputs["files"]}
            exported.append(item)
        save(directory / "skills.json", exported)
    except (Exception, KeyboardInterrupt) as failure:
        # Preserve partial logs and known usage; never silently convert failure to zero Skills.
        error = ("interrupted" if isinstance(failure, KeyboardInterrupt) else str(failure))
        key = config.get("api_key", "")
        if key:
            error = error.replace(key, "[REDACTED]")
        log_round(directory, f"ERROR: {error}")
    finally:
        save(directory / "request-costs.json", records)
        save(directory / "tool-log.json", accesses)
        save(directory / "messages.json", messages)
        summary = {"status": "completed" if error is None else "failed", "error": error,
                   "group_id": inputs["group_id"], "error_key": inputs["error_key"], "arm": inputs["arm"],
                   "session_header": config.get("sessionHeader") or None, "api_session_id": session_id,
                   "started_at": started, "finished_at": now(), "wall_seconds": time.perf_counter() - clock,
                   "api_seconds": sum(r["api_seconds"] for r in records), "request_count": len(records),
                   "usage": aggregate_usage(records), "ttft_seconds": None,
                   "ttft_note": "Nonstreaming transport; time to first token is unavailable",
                   "skill_count": len(valid_skills(directory)) if error is None else None,
                   "input_file_count": len(inputs["files"]), "inspected_file_ids": sorted(reader.touched),
                   "read_ranges": reader.read_ranges,
                   "coverage_note": "Inspected means read or searched. It does not mean the entire file was read.",
                   "input_manifest_sha256": digest(directory / "input-manifest.json")}
        save(directory / "summary.json", summary)
    return summary


def verify_prepared(output, manifest):
    if manifest["version"] != VERSION or digest(output / "prompt.txt") != manifest["prompt_sha256"] or digest(output / "tools.json") != manifest["tools_sha256"]:
        raise ValueError("Prepared experiment version/prompt/tools mismatch")
    if read_json(output / "tools.json") != TOOLS or digest(output / "groups.json") != manifest["groups_sha256"]:
        raise ValueError("Prepared input/schema changed")
    for experiment in manifest["experiments"]:
        path = Path(experiment["input_manifest"])
        if digest(path) != experiment["input_manifest_sha256"]:
            raise ValueError("Input manifest changed")
        for entry in read_json(path)["files"]:
            if digest(entry["path"]) != entry["sha256"]:
                raise ValueError("Snapshotted input changed")


def summarize_run(output, manifest):
    results, skills, requests = [], [], []
    for experiment in manifest["experiments"]:
        directory = Path(experiment["input_manifest"]).parent
        # Failed attempts archived by --resume still count towards spent tokens/time.
        attempts = sorted((directory / "attempts").glob("attempt-*/summary.json")) + [directory / "summary.json"]
        for path in attempts:
            if path.exists():
                results.append(read_json(path))
                requests.extend(read_json(path.parent / "request-costs.json"))
        current = directory / "summary.json"
        if current.exists() and read_json(current)["status"] == "completed":
            skills.extend(read_json(directory / "skills.json"))
    index = output / "skill-index.jsonl"
    index.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in skills), encoding="utf-8")
    summaries = {arm: {"completed": 0, "failed": 0, "skill_count": 0, "api_seconds": 0, "wall_seconds": 0} for arm in ARMS}
    for experiment in manifest["experiments"]:
        path = Path(experiment["input_manifest"]).parent / "summary.json"
        if path.exists():
            current = read_json(path)
            summaries[current["arm"]][current["status"]] += 1
            summaries[current["arm"]]["skill_count"] += current["skill_count"] or 0
    for arm in ARMS:
        arm_results = [r for r in results if r["arm"] == arm]
        summaries[arm]["wall_seconds"] = sum(r["wall_seconds"] for r in arm_results if r["wall_seconds"] is not None)
        summaries[arm]["api_seconds"] = sum(r["api_seconds"] for r in arm_results if r["api_seconds"] is not None)
        summaries[arm]["unknown_time_attempt_count"] = sum(r["wall_seconds"] is None for r in arm_results)
        arm_requests = []
        for experiment in manifest["experiments"]:
            if experiment["arm"] != arm:
                continue
            directory = Path(experiment["input_manifest"]).parent
            for path in sorted((directory / "attempts").glob("attempt-*/request-costs.json")) + [directory / "request-costs.json"]:
                if path.exists():
                    arm_requests.extend(read_json(path))
        summaries[arm]["usage"] = aggregate_usage(arm_requests)
    summary = {"version": VERSION, "group_count": manifest["group_count"], "experiment_count": manifest["experiment_count"],
               "arms": summaries, "candidate_count": len(skills), "usage": aggregate_usage(requests),
               "total_known_attempt_wall_seconds": sum(r["wall_seconds"] for r in results if r["wall_seconds"] is not None),
               "unknown_time_attempt_count": sum(r["wall_seconds"] is None for r in results),
               "generated_at": now(), "attempts": results, "index_path": str(index.resolve()),
               "note": "Token totals sum every API request including resumed failed attempts; unknown usage is not zero. "
                       "Candidates are not independently audited or deduplicated across groups/arms."}
    save(output / "summary.json", summary)
    return summary


def archive_failed(directory):
    attempts = directory / "attempts"
    attempt = attempts / f"attempt-{len(list(attempts.glob('attempt-*'))) + 1:03d}"
    attempt.mkdir(parents=True)
    for path in list(directory.iterdir()):
        if path.name not in {"input-manifest.json", "attempts"}:
            shutil.move(str(path), str(attempt / path.name))


def reuse_completed(output, manifest, config):
    public = public_config(config)
    for experiment in manifest["experiments"]:
        gid, arm = experiment["group_id"], experiment["arm"]
        target = output / gid / arm
        if (target / "summary.json").exists():
            continue
        wanted = sorted(f["sha256"] for f in read_json(experiment["input_manifest"])["files"])
        for run in sorted(output.parent.iterdir(), reverse=True):
            source = run / gid / arm
            if run == output or not (source / "summary.json").exists() or not (run / "manifest.json").exists():
                continue
            old = read_json(run / "manifest.json")
            if read_json(source / "summary.json")["status"] != "completed":
                continue
            if old.get("prompt_sha256") != manifest["prompt_sha256"] or old.get("api_config") != public:
                continue
            if sorted(f["sha256"] for f in read_json(source / "input-manifest.json")["files"]) != wanted:
                continue
            shutil.copytree(source, target, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("input-manifest.json", "requests", "attempts", "api-session.json"))
            skills = read_json(target / "skills.json") if (target / "skills.json").exists() else []
            for item in skills:
                item["run_directory"] = str(output.resolve())
                item["markdown_path"] = str((target / "skills" / item["name"] / "SKILL.md").resolve())
            save(target / "skills.json", skills)
            print(f"{gid} / {arm}: reused completed result from {run.name}", flush=True)
            break


def run_prepared(output, config, transport=api_request):
    manifest = read_json(output / "manifest.json")
    verify_prepared(output, manifest)
    public = public_config(config)
    if manifest.get("api_config") is not None and manifest["api_config"] != public:
        raise ValueError("Model/API settings changed; choose a new output for a new experiment")
    manifest["api_config"] = public
    manifest["status"] = "running"
    save(output / "manifest.json", manifest)
    prompt = (output / "prompt.txt").read_text(encoding="utf-8-sig")
    reuse_completed(output, manifest, config)
    for experiment in manifest["experiments"]:
        directory = Path(experiment["input_manifest"]).parent
        previous = directory / "summary.json"
        if previous.exists():
            result = read_json(previous)
            if result["status"] == "completed":
                continue
        # A process killed before summary persisted has request logs; archive those too.
        if previous.exists() or (directory / "requests").exists():
            if not previous.exists():
                paths = sorted((directory / "requests").glob("*/response.json"))
                old_records = read_json(directory / "request-costs.json") if (directory / "request-costs.json").exists() else []
                by_index = {r["request_index"]: r for r in old_records}
                requests = sorted((directory / "requests").glob("*/request.json"))
                records = []
                for path in requests:
                    index = int(path.parent.name)
                    response_path = path.parent / "response.json"
                    records.append(by_index.get(index) or {"request_index": index, "api_seconds": None,
                        **usage_record(read_json(response_path) if response_path.exists() else {})})
                save(directory / "request-costs.json", records)
                save(previous, {"status": "failed", "error": "Process ended without summary; time unknown", "wall_seconds": None,
                    "api_seconds": sum(r["api_seconds"] for r in records if r["api_seconds"] is not None) if
                        all(r["api_seconds"] is not None for r in records) else None,
                    "group_id": experiment["group_id"], "arm": experiment["arm"], "skill_count": None})
            archive_failed(directory)
        print(f"{experiment['group_id']} / {experiment['arm']}: extracting", flush=True)
        result = extract_arm(directory, prompt, config, transport)
        summarize_run(output, manifest)
        print(f"  {result['status']}; skills={result['skill_count']}; requests={result['request_count']}; seconds={result['wall_seconds']:.2f}", flush=True)
        if result["error"]:
            print(f"  error: {result['error']}", flush=True)
        if result["error"] == "interrupted":
            break
    summary = summarize_run(output, manifest)
    completed = sum(a["completed"] for a in summary["arms"].values())
    manifest["status"] = "completed" if completed == manifest["experiment_count"] else "partial"
    manifest["last_finished_at"] = now()
    save(output / "manifest.json", manifest)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "error_skill_extraction.local.json")
    parser.add_argument("--groups", type=Path, default=HERE / "error-clustering-v1/sessions-30/native-code/groups.json")
    parser.add_argument("--slices-dir", type=Path, default=WORKSPACE / "vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-full-content-slices")
    parser.add_argument("--sessions-dir", type=Path, default=WORKSPACE / "sessions")
    parser.add_argument("--prompt", type=Path, default=HERE / "error-skill-extraction-prompt.txt")
    parser.add_argument("--selection-strategy", choices=tuple(selector.SELECTION_STRATEGIES), default="group-context")
    parser.add_argument("--output", type=Path, default=WORKSPACE / "skill-runs" / datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--prepare-only", action="store_true", help="Validate/snapshot every group; no API credentials or requests")
    parser.add_argument("--resume", action="store_true", help="Skip completed arms; retry failed arms, preserving their costs")
    args = parser.parse_args()
    try:
        config = None if args.prepare_only else load_config(args.config)
        output = args.output.resolve()
        if args.resume:
            manifest = read_json(output / "manifest.json")
            verify_prepared(output, manifest)
        else:
            manifest = prepare(args.groups, args.slices_dir, args.sessions_dir, output, args.prompt, args.selection_strategy)
        if args.prepare_only:
            print(json.dumps({"output": str(output), "groups": manifest["group_count"], "experiments": manifest["experiment_count"], "api_calls": 0}, ensure_ascii=False))
            return
        result = run_prepared(output, config)
        print(json.dumps({"output": str(output), "arms": result["arms"]}, ensure_ascii=False))
        if sum(a["completed"] for a in result["arms"].values()) != manifest["experiment_count"]:
            sys.exit(1)
    except (ValueError, OSError, KeyError, TypeError) as failure:
        parser.error(str(failure))


if __name__ == "__main__":
    main()
