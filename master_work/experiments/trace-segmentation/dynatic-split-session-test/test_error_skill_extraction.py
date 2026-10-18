"""Offline tests: no provider, API key or live model is used."""
import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import error_skill_extraction as runner


SID = "claude_code__fixture"
GID = "native-code-abc"


def skill(fid):
    return {
        "title": "修复示例错误", "name": "fix-fixture-error",
        "description": {"use_when": "fixture error occurs", "helps": "recover execution",
                        "requires": "fixture environment", "do_not_use_when": "failure is unrelated"},
        "goal": "恢复示例执行并验证。", "scope": {"in_scope": ["示例恢复"], "out_of_scope": ["部署"]},
        "inputs": [{"name": "fixture", "type": "file", "source": "caller", "required": True,
                    "constraints": "存在", "default_value": "无"}],
        "outputs": {"artifacts": [{"name": "result", "location": "调用者指定", "format": "text"}],
                    "success_criteria": ["passed"], "failure_criteria": ["错误仍存在"]},
        "preconditions": ["fixture 存在"],
        "procedure": [{"title": "恢复", "actions": ["执行 fix"], "inputs": ["fixture"],
                       "outputs": ["result"], "cautions": ["不改无关文件"], "preserve": ["源文件"],
                       "next_condition": "观察结果"}],
        "decision_rules": [{"when": "failure", "actions": ["fix"]}],
        "invariants": ["不报告未验证成功"],
        "common_failures": [{"title": "failure", "symptoms": ["failure"], "causes": ["轨迹未提供"],
                             "recovery": ["fix"]}],
        "verification": ["检查 passed"],
        "examples": [{"title": "Valid use case", "input": "failure", "procedure": "fix",
                      "expected_result": "passed", "parameterized_values": ["fixture"]}],
        "evidence": [{"kind": kind, "file_id": fid, "source_index": i, "source_part_index": 0,
                      "quote": quote, "supports": kind}
                     for i, (kind, quote) in enumerate([("problem", "failure"), ("action", "fix"), ("verification", "passed")])],
    }


def config():
    return {"api_key": "test-secret-not-a-real-key", "base_url": "https://fixture.invalid/v1", "model": "fixture-model",
            "userAgent": "skill-extraction/1.0"}


def completion(calls, usage=True):
    result = {"id": "fixture-response", "model": "fixture-model", "choices": [{"finish_reason": "tool_calls",
              "message": {"role": "assistant", "content": None,
                          "tool_calls": [{"id": f"call-{i}", "type": "function",
                              "function": {"name": name, "arguments": json.dumps(args)}}
                              for i, (name, args) in enumerate(calls)]}}]}
    if usage:
        result["usage"] = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                           "prompt_tokens_details": {"cached_tokens": 40},
                           "completion_tokens_details": {"reasoning_tokens": 3}}
    return result


def make_inputs(root):
    raw = root / "sessions" / "claude_code" / "fixture.jsonl"
    raw.parent.mkdir(parents=True)
    messages = [
        {"message": {"role": "user", "content": [{"type": "text", "text": "failure"}]}},
        {"message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Edit", "input": {"description": "fix"}}]}},
        {"message": {"role": "user", "content": [{"type": "tool_result", "content": "passed"}]}},
        {"message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "HIDDEN SECRET BODY"}]}},
    ]
    raw.write_text("\n".join(json.dumps(m) for m in messages) + "\n", encoding="utf-8")
    slices = root / "slices" / SID
    slices.mkdir(parents=True)
    events = [
        {"source_index": 0, "source_part_index": 0, "category": "user_text", "text": "failure"},
        {"source_index": 1, "source_part_index": 0, "category": "tool_call:Edit", "arguments": {"description": "fix"}},
        {"source_index": 2, "source_part_index": 0, "category": "tool_result", "content": "passed"},
    ]
    runner.save(slices / "segment-01.json", {"start_event": 0, "end_event": 2, "events": events})
    runner.save(slices / "segment-02.json", {"start_event": 3, "end_event": 3, "events": [
        {"source_index": 3, "source_part_index": 0, "category": "assistant_thinking", "text": "HIDDEN SECRET BODY"}]})
    groups = root / "groups.json"
    runner.save(groups, [{"group_id": GID, "error_key": "fixture:ERROR", "member_ids": [SID],
        "member_session_ids": [SID], "evidence": [{"source_index": 0, "source_part_index": 0,
            "unit_id": SID, "session_id": SID, "source_path": str(raw), "context": []}]}])
    prompt = root / "prompt.txt"
    prompt.write_text("fixture prompt", encoding="utf-8")
    output = root / "out"
    manifest = runner.prepare(groups, root / "slices", root / "sessions", output, prompt)
    return output, manifest


def stub(payload, api_config):
    catalog = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])
    files = catalog["files"]
    if len(payload["messages"]) == 2:
        return completion([("read_trace", {"file_id": f["file_id"]}) for f in files])
    return completion([("response", {"skills": [skill(files[0]["file_id"])], "excluded_candidates": []})])


class ExtractionTests(unittest.TestCase):
    def test_http_transport_uses_chat_endpoint_and_tool_payload(self):
        class Reply:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps(completion([])).encode()
        with patch.object(runner.urllib.request, "urlopen", return_value=Reply()) as opened:
            result = runner.api_request({"model": "fixture-model", "tools": runner.TOOLS, "messages": []},
                config() | {"sessionHeader": "x-opencode-session", "_session_id": "fixture-api-session"})
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "https://fixture.invalid/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + config()["api_key"])
        self.assertEqual(request.get_header("X-opencode-session"), "fixture-api-session")
        self.assertEqual(request.get_header("User-agent"), "skill-extraction/1.0")
        self.assertEqual(opened.call_args.kwargs, {})
        self.assertEqual(json.loads(request.data)["tools"][-1]["function"]["name"], "response")
        self.assertEqual(result["usage"]["total_tokens"], 120)

    def test_custom_user_agent_and_redacted_http_error_detail(self):
        settings = config() | {"userAgent": "fixture-agent/2.0"}
        headers = runner.request_headers(settings)
        self.assertEqual(headers["User-Agent"], "fixture-agent/2.0")
        error = runner.urllib.error.HTTPError("https://fixture.invalid", 403, "Forbidden", {},
            io.BytesIO(("denied " + settings["api_key"] + " Bearer another-secret").encode()))
        with patch.object(runner.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as raised:
                runner.api_request({"messages": []}, settings)
        message = str(raised.exception)
        self.assertIn("API HTTP 403: denied", message)
        self.assertNotIn(settings["api_key"], message)
        self.assertNotIn("another-secret", message)

    def test_user_agent_defaults_without_editing_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            original = {k: v for k, v in config().items() if k != "userAgent"}
            runner.save(path, original)
            loaded = runner.load_config(path)
            self.assertEqual(loaded["userAgent"], "skill-extraction/1.0")
            self.assertEqual(runner.read_json(path), original)
            runner.save(path, original | {"userAgent": "bad\r\nheader"})
            with self.assertRaises(ValueError):
                runner.load_config(path)

    def test_provider_session_shared_within_arm_and_isolated_between_arms(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            seen = []
            def capture(payload, settings):
                seen.append(settings["_session_id"])
                return stub(payload, settings)
            settings = config() | {"sessionHeader": "x-opencode-session"}
            result = runner.run_prepared(output, settings, capture)
            self.assertEqual(result["candidate_count"], 3)
            self.assertEqual(len(seen), 6)
            self.assertEqual(len(set(seen)), 3)
            for index, arm in enumerate(runner.ARMS):
                self.assertEqual(seen[2 * index], seen[2 * index + 1])
                recorded = runner.read_json(output / GID / arm / "api-session.json")
                self.assertEqual(recorded["session_id"], seen[2 * index])
                self.assertEqual(recorded["header_name"], "x-opencode-session")
            self.assertNotIn("_session_id", settings)

    def test_invalid_session_header_rejected_and_missing_id_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            for header in ("bad\nheader", "Authorization", "content-type", 123):
                runner.save(path, config() | {"sessionHeader": header})
                with self.assertRaises(ValueError):
                    runner.load_config(path)
        with self.assertRaisesRegex(ValueError, "Missing per-experiment Session"):
            runner.api_request({}, config() | {"sessionHeader": "x-opencode-session"})

    def test_config_blank_and_endpoint_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            runner.save(path, config() | {"api_key": ""})
            with self.assertRaises(ValueError):
                runner.load_config(path)
            runner.save(path, config() | {"extra_body": {"messages": []}})
            self.assertNotIn("extra_body", runner.load_config(path))
        self.assertEqual(runner.endpoint("https://example.com/v1/"), "https://example.com/v1/chat/completions")
        self.assertEqual(runner.endpoint("https://example.com/v1/chat/completions"), "https://example.com/v1/chat/completions")
        with self.assertRaises(ValueError):
            runner.endpoint("https://user:secret@example.com/v1")

    def test_prepare_three_arms_and_selected_files_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, manifest = make_inputs(Path(tmp))
            self.assertEqual(manifest["experiment_count"], 3)
            a, b, c = [runner.read_json(output / GID / arm / "input-manifest.json") for arm in runner.ARMS]
            self.assertEqual([len(x["files"]) for x in [a, b, c]], [1, 1, 2])
            self.assertEqual(b["files"][0]["sha256"], c["files"][0]["sha256"])
            self.assertNotIn("HIDDEN SECRET BODY", Path(c["files"][1]["path"]).read_text())
            runner.verify_prepared(output, manifest)

    def test_mock_end_to_end_export_template_costs_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            result = runner.run_prepared(output, config(), stub)
            self.assertEqual(result["candidate_count"], 3)
            self.assertEqual(result["usage"]["total_tokens"]["known_sum"], 720)
            self.assertEqual(result["usage"]["reasoning_tokens"]["known_sum"], 18)
            self.assertEqual(result["arms"]["A-original"]["usage"]["noncached_input_tokens"]["known_sum"], 120)
            index = [json.loads(line) for line in (output / "skill-index.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len({item["skill_id"] for item in index}), 3)
            markdown = Path(index[0]["markdown_path"]).read_text(encoding="utf-8")
            for heading in ("Goal", "Scope", "Inputs", "Outputs", "Preconditions", "Procedure", "Decision Rules", "Invariants", "Common Failures", "Verification", "Examples"):
                self.assertIn("## " + heading, markdown)
            self.assertNotIn("[x]", markdown)
            self.assertNotIn(config()["api_key"], (output / "manifest.json").read_text())
            def should_not_call(*args):
                self.fail("Completed arms should never be called again on resume")
            repeated = runner.run_prepared(output, config(), should_not_call)
            self.assertEqual(repeated["usage"], result["usage"])
            self.assertEqual(len((output / "skill-index.jsonl").read_text().splitlines()), 3)

    def test_no_skills_is_success_not_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            def no_skill(payload, settings):
                if len(payload["messages"]) == 2:
                    return stub(payload, settings)
                return completion([("response", {"skills": [], "excluded_candidates": []})], usage=False)
            result = runner.run_prepared(output, config(), no_skill)
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["arms"]["A-original"]["completed"], 1)
            self.assertFalse(result["usage"]["total_tokens"]["complete"])
            self.assertEqual(result["usage"]["total_tokens"]["missing_request_count"], 3)

    def test_wrong_citation_and_prose_verification_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            inputs = runner.read_json(output / GID / "B-selected" / "input-manifest.json")
            reader = runner.ArmReader(inputs["files"])
            fid = inputs["files"][0]["file_id"]
            reader.read(fid)
            valid = {"skills": [skill(fid)], "excluded_candidates": []}
            reader.validate_response(valid)
            invalid = copy.deepcopy(valid)
            invalid["skills"][0]["evidence"][2]["source_index"] = 0
            invalid["skills"][0]["evidence"][2]["quote"] = "failure"
            with self.assertRaisesRegex(ValueError, "Verification needs"):
                reader.validate_response(invalid)
            invalid["skills"][0]["evidence"][2]["quote"] = "made-up-result"
            with self.assertRaisesRegex(ValueError, "quote is absent"):
                reader.validate_response(invalid)

    def test_tools_cannot_access_other_arm_or_hidden_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            inputs = runner.read_json(output / GID / "C-context-collapsed" / "input-manifest.json")
            reader = runner.ArmReader(inputs["files"])
            fid = inputs["files"][1]["file_id"]
            self.assertEqual(reader.search(fid, "HIDDEN SECRET BODY", False)["matches"], [])
            self.assertNotIn("HIDDEN SECRET BODY", reader.read_event(fid, 3, 0)["content"])
            with self.assertRaises(ValueError):
                reader.read("C:/arbitrary-path.json")
            with self.assertRaises(ValueError):
                reader.read_event(fid, 2, 0)

    def test_failed_attempts_resume_keep_spent_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            def filtered(*args):
                response = completion([])
                response["choices"][0]["finish_reason"] = "content_filter"
                return response
            first = runner.run_prepared(output, config(), filtered)
            self.assertEqual(first["usage"]["total_tokens"]["known_sum"], 360)
            self.assertEqual(first["arms"]["A-original"]["failed"], 1)
            repeated = runner.run_prepared(output, config(), stub)
            self.assertEqual(repeated["usage"]["total_tokens"]["known_sum"], 1080)
            self.assertEqual(repeated["candidate_count"], 3)
            self.assertTrue((output / GID / "A-original" / "attempts/attempt-001/summary.json").exists())

    def test_killed_process_keeps_response_usage_without_inventing_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            directory = output / GID / "A-original"
            runner.save(directory / "requests/0001/request.json", {"model": "fixture"})
            runner.save(directory / "requests/0001/response.json", completion([]))
            runner.save(directory / "requests/0002/request.json", {"model": "fixture"})
            result = runner.run_prepared(output, config(), stub)
            self.assertEqual(result["usage"]["total_tokens"]["known_sum"], 840)
            self.assertEqual(result["usage"]["total_tokens"]["missing_request_count"], 1)
            self.assertEqual(result["unknown_time_attempt_count"], 1)
            self.assertIsNone(runner.read_json(directory / "attempts/attempt-001/summary.json")["wall_seconds"])

    def test_missing_usage_transport_error_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            def fails(payload, settings):
                raise RuntimeError("error " + settings["api_key"])
            result = runner.run_prepared(output, config(), fails)
            self.assertEqual(result["usage"]["total_tokens"]["missing_request_count"], 3)
            self.assertEqual(result["arms"]["A-original"]["failed"], 1)
            self.assertNotIn(config()["api_key"], (output / GID / "A-original" / "summary.json").read_text())
            self.assertNotIn(config()["api_key"], (output / GID / "A-original" / "requests/0001/request.json").read_text())

    def test_resume_rejects_changed_inputs_or_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, manifest = make_inputs(Path(tmp))
            runner.run_prepared(output, config(), stub)
            with self.assertRaisesRegex(ValueError, "settings changed"):
                runner.run_prepared(output, config() | {"model": "other-model"}, stub)
            original = runner.read_json(output / GID / "A-original/input-manifest.json")["files"][0]["path"]
            Path(original).write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input changed"):
                runner.verify_prepared(output, manifest)

    def test_raw_blank_lines_keep_original_source_indices_and_opencode_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.jsonl"
            path.write_text('\n{"message":{"role":"user","content":[{"type":"text","text":"failure"}]}}\n', encoding="utf-8")
            self.assertEqual(list(runner.source_parts(path, "original"))[0][0], 1)
            path = Path(tmp) / "raw.json"
            runner.save(path, {"messages": [{"info": {"role": "assistant"}, "parts": [{"type": "tool", "tool": "shell",
                "state": {"input": {"command": "test"}, "output": "passed"}}]}]})
            categories = [part[2] for part in runner.source_parts(path, "original")]
            self.assertEqual(categories, ["tool_call:shell", "tool_result"])

    def test_response_schema_every_section_and_bad_names(self):
        value = {"skills": [skill("fixture")], "excluded_candidates": []}
        runner.validate_schema(value, runner.RESPONSE_SCHEMA)
        del value["skills"][0]["verification"]
        with self.assertRaises(ValueError):
            runner.validate_schema(value, runner.RESPONSE_SCHEMA)
        value = {"skills": [skill("fixture") | {"name": "../escape"}], "excluded_candidates": []}
        with self.assertRaises(ValueError):
            runner.validate_schema(value, runner.RESPONSE_SCHEMA)

    def test_submission_requires_all_files_inspected_and_has_no_round_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            inputs = runner.read_json(output / GID / "C-context-collapsed/input-manifest.json")
            reader = runner.ArmReader(inputs["files"])
            with self.assertRaisesRegex(ValueError, "Inspect every"):
                reader.validate_response({"skills": [], "excluded_candidates": []})
            count = 0
            def prose_only(*args):
                nonlocal count
                count += 1
                if count == 102:
                    raise KeyboardInterrupt()
                return completion([])
            result = runner.extract_arm(output / GID / "A-original", "fixture", config(), prose_only)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "interrupted")
            self.assertEqual(result["request_count"], 102)
            self.assertIsNone(result["skill_count"])

    def test_no_generation_controls_sent_even_with_legacy_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, _ = make_inputs(Path(tmp))
            legacy = config() | {"timeout_seconds": 1, "max_requests": 1, "max_output_tokens": 1,
                "max_tokens": 1, "max_input_tokens": 1, "temperature": 0,
                "output_token_parameter": "max_tokens", "extra_body": {"stop": ["x"], "max_completion_tokens": 1}}
            path = Path(tmp) / "config.json"
            runner.save(path, legacy)
            loaded = runner.load_config(path)
            self.assertEqual(loaded, config())
            def capture(payload, settings):
                self.assertEqual(set(payload), {"model", "messages", "tools", "tool_choice", "stream"})
                response = stub(payload, settings)
                if len(payload["messages"]) > 2:
                    response["choices"][0]["finish_reason"] = "length"
                return response
            result = runner.extract_arm(output / GID / "A-original", "fixture", legacy, capture)
            self.assertEqual(result["status"], "completed")

    def test_full_file_event_and_all_search_matches_without_size_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.json"
            text = "needle" + "x" * 60000
            runner.save(path, {"events": [{"source_index": i, "source_part_index": 0,
                "category": "tool_result", "content": text} for i in range(25)]})
            entry = runner.file_entry(path, SID, "slice", "full")
            reader = runner.ArmReader([entry])
            fid = entry["file_id"]
            self.assertEqual(reader.read(fid)["content"], path.read_text(encoding="utf-8"))
            self.assertIn(text, reader.read_event(fid, 24, 0)["content"])
            matches = reader.search(fid, "needle", False)["matches"]
            self.assertEqual(len(matches), 25)
            self.assertTrue(all(m["text"] == text for m in matches))


if __name__ == "__main__":
    unittest.main()
