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
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import select_group_slices as selector

VERSION = "error-skill-extraction-v1"
HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ARMS = ("A-original", "B-selected", "C-context-collapsed")
STRING = {"type": "string", "minLength": 1}
STRINGS = {"type": "array", "items": STRING}


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def arr(schema, minimum=0):
    return {"type": "array", "items": schema, "minItems": minimum}


EVIDENCE_SCHEMA = obj(kind={"type": "string", "enum": ["problem", "action", "verification"]},
    file_id=STRING, source_index={"type": "integer", "minimum": 0},
    source_part_index={"type": ["integer", "null"], "minimum": 0}, quote=STRING, supports=STRING)
SKILL_SCHEMA = obj(
    title=STRING, name={"type": "string", "pattern": r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"},
    description=obj(use_when=STRING, helps=STRING, requires=STRING, do_not_use_when=STRING),
    goal=STRING, scope=obj(in_scope=arr(STRING, 1), out_of_scope=STRINGS),
    inputs=arr(obj(name=STRING, type=STRING, source=STRING, required={"type": "boolean"},
                  constraints=STRING, default_value=STRING)),
    outputs=obj(artifacts=arr(obj(name=STRING, location=STRING, format=STRING)),
                success_criteria=arr(STRING, 1), failure_criteria=arr(STRING, 1)),
    preconditions=arr(STRING, 1),
    procedure=arr(obj(title=STRING, actions=arr(STRING, 1), inputs=STRINGS, outputs=STRINGS,
                      cautions=STRINGS, preserve=STRINGS, next_condition=STRING), 1),
    decision_rules=arr(obj(when=STRING, actions=arr(STRING, 1)), 1), invariants=arr(STRING, 1),
    common_failures=arr(obj(title=STRING, symptoms=STRINGS, causes=STRINGS, recovery=STRINGS)),
    verification=arr(STRING, 1),
    examples=arr(obj(title=STRING, input=STRING, procedure=STRING, expected_result=STRING,
                     parameterized_values=STRINGS), 1),
    evidence=arr(EVIDENCE_SCHEMA, 3))
RESPONSE_SCHEMA = obj(skills=arr(SKILL_SCHEMA),
    excluded_candidates=arr(obj(topic=STRING, reason=STRING, file_ids=STRINGS)))
TOOLS = [
    {"type": "function", "function": {"name": "read_trace", "description":
     "Read an exact character page of an allowed input file. Follow next_offset for long content. "
     "No hidden content or other arms can be read. Offsets are Unicode characters, not bytes.",
     "parameters": obj(file_id=STRING, offset={"type": "integer", "minimum": 0},
                       max_chars={"type": "integer", "minimum": 1, "maximum": 48000})}},
    {"type": "function", "function": {"name": "search_trace", "description":
     "Search visible string values in raw records or slice events. Returns source indices and "
     "short matching snippets, never hidden result/thinking payloads. start_match paginates results.",
     "parameters": obj(file_id=STRING, pattern=STRING, regex={"type": "boolean"},
                       start_match={"type": "integer", "minimum": 0},
                       limit={"type": "integer", "minimum": 1, "maximum": 20})}},
    {"type": "function", "function": {"name": "read_event", "description":
     "Read a visible event/part by original zero-based source_index and source_part_index. "
     "Use offset/next_offset to read long payloads. Does not restore collapsed content.",
     "parameters": obj(file_id=STRING, source_index={"type": "integer", "minimum": 0},
                       source_part_index={"type": ["integer", "null"], "minimum": 0},
                       offset={"type": "integer", "minimum": 0},
                       max_chars={"type": "integer", "minimum": 1, "maximum": 48000})}},
    {"type": "function", "function": {"name": "response", "description":
     "Submit the final complete Skill list using every section of the Agent Skill template. "
     "Zero Skills is valid. Evidence needs exact visible quotes for problem, action and verification. "
     "Successful submission ends this experiment; do not submit a draft.",
     "parameters": RESPONSE_SCHEMA}},
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
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
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

    def read(self, file_id, offset, max_chars):
        text = self.text(file_id)
        if offset >= len(text) and text:
            raise ValueError("offset is past end of file")
        end = min(len(text), offset + max_chars)
        self.touched.add(file_id)
        self.read_ranges[file_id].append([offset, end])
        return {"file_id": file_id, "offset": offset, "end_offset": end, "total_chars": len(text),
                "next_offset": end if end < len(text) else None, "content": text[offset:end]}

    def search(self, file_id, pattern, regex, start_match, limit):
        expression = re.compile(pattern if regex else re.escape(pattern), re.IGNORECASE)
        matches = []
        for index, part, category, payload in self.events(file_id):
            for text in string_values(payload):
                for match in expression.finditer(text):
                    matches.append({"source_index": index, "source_part_index": part, "category": category,
                                    "snippet": text[max(0, match.start() - 160):match.end() + 240]})
                    if len(matches) >= start_match + limit + 1:
                        break
                if len(matches) >= start_match + limit + 1:
                    break
            if len(matches) >= start_match + limit + 1:
                break
        self.touched.add(file_id)
        return {"file_id": file_id, "matches": matches[start_match:start_match + limit],
                "next_match": start_match + limit if len(matches) > start_match + limit else None}

    def read_event(self, file_id, source_index, source_part_index, offset, max_chars):
        selected = [{"source_index": i, "source_part_index": p, "category": c, "payload": v}
                    for i, p, c, v in self.events(file_id) if i == source_index and
                    (source_part_index is None or p == source_part_index)]
        if not selected:
            raise ValueError("Original source event is absent from this input file")
        text = json.dumps(selected, ensure_ascii=False)
        if offset >= len(text):
            raise ValueError("offset is past end of event")
        end = min(len(text), offset + max_chars)
        self.touched.add(file_id)
        return {"file_id": file_id, "source_index": source_index, "source_part_index": source_part_index,
                "offset": offset, "end_offset": end, "total_chars": len(text),
                "next_offset": end if end < len(text) else None, "content": text[offset:end]}

    def validate_response(self, result):
        validate_schema(result, RESPONSE_SCHEMA)
        if set(self.files) - self.touched:
            raise ValueError("Inspect every input file before response: " + ", ".join(sorted(set(self.files) - self.touched)))
        names = set()
        for number, skill in enumerate(result["skills"]):
            if skill["name"] in names:
                raise ValueError("Duplicate Skill name within one experiment")
            names.add(skill["name"])
            kinds = set()
            for ev in skill["evidence"]:
                fid = ev["file_id"]
                self.file(fid)
                candidates = [(cat, payload) for index, part, cat, payload in self.events(fid)
                    if index == ev["source_index"] and
                    (ev["source_part_index"] is None or ev["source_part_index"] == part)]
                matching = [(cat, payload) for cat, payload in candidates
                            if any(ev["quote"] in text for text in string_values(payload))]
                if not matching:
                    raise ValueError(f"skills[{number}]: quote is absent from visible source event in {fid}")
                if ev["kind"] == "verification":
                    verified = False
                    for cat, payload in matching:
                        output = ({k: payload[k] for k in ("content", "output", "text", "error") if k in payload}
                                  if cat == "tool_result" and not payload.get("collapsed_content") else {})
                        if isinstance(payload.get("tool_result"), dict):
                            output.update({k: payload["tool_result"][k] for k in ("output", "error")
                                           if k in payload["tool_result"]})
                        if any(ev["quote"] in text for text in string_values(output)):
                            verified = True
                    if not verified:
                        raise ValueError("Verification needs a visible tool-result quote, not prose or collapsed metadata")
                kinds.add(ev["kind"])
            if kinds != {"problem", "action", "verification"}:
                raise ValueError("Every Skill needs problem/action/verification source evidence")
        for item in result["excluded_candidates"]:
            for fid in item["file_ids"]:
                self.file(fid)


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
    config = read_json(path)
    for field in ("api_key", "base_url", "model"):
        if require_credentials and (not isinstance(config.get(field), str) or not config[field].strip()):
            raise ValueError(f"Fill {field} in your configuration before running API experiments")
    if config.get("base_url"):
        endpoint(config["base_url"])
    for field in ("timeout_seconds", "max_requests", "max_output_tokens"):
        if type(config.get(field)) is not int or config[field] < 1:
            raise ValueError(f"{field} must be a positive integer")
    if config.get("output_token_parameter", "max_tokens") not in {"max_tokens", "max_completion_tokens"}:
        raise ValueError("output_token_parameter must be max_tokens or max_completion_tokens")
    extra = config.get("extra_body", {})
    if not isinstance(extra, dict) or set(extra) & {"api_key", "messages", "tools", "tool_choice", "model", "stream", "n", "max_tokens", "max_completion_tokens"}:
        raise ValueError("extra_body cannot override transport, inputs, tools or output limits")
    return config


def public_config(config):
    return {k: v for k, v in config.items() if k != "api_key"}


def api_request(payload, config):
    request = urllib.request.Request(endpoint(config["base_url"]),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + config["api_key"]})
    try:
        with urllib.request.urlopen(request, timeout=config["timeout_seconds"]) as reply:
            return json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # Do not archive provider bodies that could echo secrets or trigger enormous logs.
        raise RuntimeError(f"API HTTP {error.code}; no automatic retry was made") from None
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


def render_skill(skill, files):
    bullets = lambda values: "\n".join("- " + v for v in values) if values else "- 轨迹未提供。"
    desc = skill["description"]
    description = "Use when " + desc["use_when"] + ". Helps the agent " + desc["helps"] + ". Requires " + desc["requires"] + ". Do not use when " + desc["do_not_use_when"] + "."
    text = ["# " + skill["title"], "```yaml\n---\nname: " + skill["name"] + "\ndescription: >\n  " +
            description.replace("\n", "\n  ") + "\n---\n```", "## Goal", skill["goal"], "## Scope", "### In scope",
            bullets(skill["scope"]["in_scope"]), "### Out of scope", bullets(skill["scope"]["out_of_scope"]), "## Inputs",
            bullets([f"`{v['name']}`：{v['type']}；来源：{v['source']}；必需：{v['required']}；约束：{v['constraints']}；默认值：{v['default_value']}" for v in skill["inputs"]]),
            "## Outputs", bullets([f"`{v['name']}`：{v['location']}；{v['format']}" for v in skill["outputs"]["artifacts"]]),
            "成功标准：\n" + bullets(skill["outputs"]["success_criteria"]), "失败标准：\n" + bullets(skill["outputs"]["failure_criteria"]),
            "## Preconditions", bullets(skill["preconditions"]), "前置条件不满足时，停止并报告具体原因。", "## Procedure"]
    for i, step in enumerate(skill["procedure"], 1):
        text += [f"### Step {i}: {step['title']}", bullets(step["actions"]), "输入：\n" + bullets(step["inputs"]),
                 "产物：\n" + bullets(step["outputs"]), "注意：\n" + bullets(step["cautions"]),
                 "保留：\n" + bullets(step["preserve"]), "下一步条件：" + step["next_condition"]]
    text += ["## Decision Rules"]
    for rule in skill["decision_rules"]:
        text += ["### When " + rule["when"], bullets(rule["actions"])]
    text += ["### When 条件不满足或信息缺失", "- 不猜测、不伪造数据；报告缺失信息，等待补充或安全退出。",
             "## Invariants", bullets(skill["invariants"]), "## Common Failures"]
    for failure in skill["common_failures"]:
        text += ["### Failure: " + failure["title"], "症状：\n" + bullets(failure["symptoms"]),
                 "原因：\n" + bullets(failure["causes"]), "恢复：\n" + bullets(failure["recovery"])]
    if not skill["common_failures"]:
        text.append("轨迹未提供。")
    text += ["## Verification", "\n".join("- [ ] " + v for v in skill["verification"]),
             "只有全部关键检查通过，才能报告成功。", "## Examples"]
    for i, example in enumerate(skill["examples"], 1):
        text += [f"### Example {i}: {example['title']}", "输入：\n\n```text\n" + example["input"] + "\n```",
                 "处理：\n\n" + example["procedure"], "预期结果：\n\n" + example["expected_result"],
                 "参数化值：\n" + bullets(example["parameterized_values"])]
    text += ["## 来源证据", "状态：待审核候选；结构和原文引用校验不代表方法或因果关系已获独立验证。"]
    for evidence in skill["evidence"]:
        source = files[evidence["file_id"]]
        text += [f"- {evidence['kind']} / {evidence['supports']}：Session `{source['session_id']}`，"
                 f"文件 `{evidence['file_id']}`，source_index={evidence['source_index']}，"
                 f"source_part_index={evidence['source_part_index']}。\n  原文：{evidence['quote']}"]
    return "\n\n".join(text) + "\n"


def initial_messages(prompt, inputs):
    catalog = copy.deepcopy(inputs)
    for entry in catalog["files"]:
        # Paths do not confer filesystem access: tool file_id is the sole authority.
        entry.pop("path", None)
    return [{"role": "system", "content": prompt}, {"role": "user", "content":
            "本次只分析以下输入文件。用 read_trace/search_trace 读取证据，再通过 response 提交结果。\n" +
            json.dumps(catalog, ensure_ascii=False)}]


def extract_arm(directory, prompt, config, transport=api_request):
    inputs = read_json(directory / "input-manifest.json")
    reader = ArmReader(inputs["files"])
    messages = initial_messages(prompt, inputs)
    records, accesses = [], []
    started, clock = now(), time.perf_counter()
    accepted = None
    error = None
    try:
        for request_index in range(1, config["max_requests"] + 1):
            payload = {"model": config["model"], "messages": messages, "tools": TOOLS,
                       "tool_choice": "auto", "stream": False,
                       config.get("output_token_parameter", "max_tokens"): config["max_output_tokens"]}
            payload.update(config.get("extra_body", {}))
            if config.get("temperature") is not None:
                payload["temperature"] = config["temperature"]
            request_dir = directory / "requests" / f"{request_index:04d}"
            # Exact request body, no Authorization header/API key.
            save(request_dir / "request.json", payload)
            sent, api_clock = now(), time.perf_counter()
            try:
                response = transport(payload, config)
            except Exception:
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
            choice = response["choices"][0]
            if choice.get("finish_reason") in {"length", "content_filter"}:
                raise ValueError("Response was truncated or filtered; no Skills accepted")
            message = choice["message"]
            calls = message.get("tool_calls") or []
            assistant_message = {k: message[k] for k in ("role", "content", "tool_calls", "reasoning_content") if k in message}
            assistant_message.setdefault("role", "assistant")
            messages.append(assistant_message)
            if not calls:
                messages.append({"role": "user", "content": "请使用工具读取输入并通过 response 提交完整结果；不要用正文代替工具。允许零个 Skill。"})
                continue
            pending_result = None
            for call in calls:
                name = call.get("function", {}).get("name")
                tool_result = None
                try:
                    arguments = json.loads(call["function"]["arguments"])
                    tool = next((t for t in TOOLS if t["function"]["name"] == name), None)
                    if tool is None:
                        raise ValueError("Unknown tool")
                    validate_schema(arguments, tool["function"]["parameters"])
                    if name == "read_trace":
                        tool_result = reader.read(**arguments)
                    elif name == "search_trace":
                        tool_result = reader.search(**arguments)
                    elif name == "read_event":
                        tool_result = reader.read_event(**arguments)
                    else:
                        if len(calls) != 1:
                            raise ValueError("response must be the only tool call in its final turn")
                        reader.validate_response(arguments)
                        pending_result = arguments
                        tool_result = {"accepted": True, "skill_count": len(arguments["skills"])}
                except (ValueError, TypeError, KeyError, re.error) as failure:
                    tool_result = {"error": str(failure), "accepted": False}
                accesses.append({"request_index": request_index, "tool_call_id": call.get("id"),
                                 "name": name, "arguments": call.get("function", {}).get("arguments"),
                                 "result": tool_result})
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(tool_result, ensure_ascii=False)})
            save(directory / "tool-log.json", accesses)
            if pending_result is not None:
                accepted = pending_result
                break
        if accepted is None:
            raise ValueError("max_requests reached without an accepted response")
        save(directory / "response-arguments.json", accepted)
        exported = []
        for skill in accepted["skills"]:
            stable = hashlib.sha256((inputs["group_id"] + "/" + inputs["arm"] + "/" + skill["name"]).encode()).hexdigest()[:20]
            sid = "skill-" + stable
            markdown = directory / "skills" / sid / "SKILL.md"
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(render_skill(skill, reader.files), encoding="utf-8")
            item = {"skill_id": sid, "status": "candidate_needs_review", "group_id": inputs["group_id"],
                    "error_key": inputs["error_key"], "arm": inputs["arm"], "skill": skill,
                    "run_directory": str(directory.parents[1].resolve()), "model": config["model"],
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "prompt_hash_convention": "UTF-8 text, CRLF normalized to LF",
                    "source_session_ids": sorted({reader.file(e["file_id"])["session_id"] for e in skill["evidence"]}),
                    "markdown_path": str(markdown.resolve()), "source_files": inputs["files"]}
            save(markdown.parent / "skill.json", item)
            exported.append(item)
        save(directory / "skills.json", exported)
    except (Exception, KeyboardInterrupt) as failure:
        # Preserve partial logs and known usage; never silently convert failure to zero Skills.
        error = ("interrupted" if isinstance(failure, KeyboardInterrupt) else str(failure))
        key = config.get("api_key", "")
        if key:
            error = error.replace(key, "[REDACTED]")
    finally:
        save(directory / "request-costs.json", records)
        save(directory / "tool-log.json", accesses)
        save(directory / "messages.json", messages)
        summary = {"status": "completed" if accepted is not None and error is None else "failed", "error": error,
                   "group_id": inputs["group_id"], "error_key": inputs["error_key"], "arm": inputs["arm"],
                   "started_at": started, "finished_at": now(), "wall_seconds": time.perf_counter() - clock,
                   "api_seconds": sum(r["api_seconds"] for r in records), "request_count": len(records),
                   "usage": aggregate_usage(records), "ttft_seconds": None,
                   "ttft_note": "Nonstreaming transport; time to first token is unavailable",
                   "skill_count": len(accepted["skills"]) if accepted is not None and error is None else None,
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
