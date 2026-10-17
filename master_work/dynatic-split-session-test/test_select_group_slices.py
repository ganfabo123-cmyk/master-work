import json
import tempfile
import unittest
from pathlib import Path

import select_group_slices as selector


SID = "claude_code__test"


def group(index=20, part=0, context=None):
    return {"group_id": "example-group", "group_key": "example-key",
            "member_session_ids": [SID], "evidence": [{"unit_id": SID, "session_id": SID,
                "source_index": index, "source_part_index": part,
                "event_index": 999, "json_pointer": f"jsonl:{index + 1}/content/{part}",
                "source_path": "original.jsonl", "context": context or []}]}


def candidate(name, *refs):
    return {"slice_id": name, "source_path": name + ".json", "core_refs": set(refs)}


class SelectionTests(unittest.TestCase):
    def test_uses_raw_indices_not_projected_event_indices(self):
        result = selector.select(group(), SID, [candidate("right", (20, 0)),
                                candidate("wrong", (999, 0))], "group-evidence")
        self.assertEqual([s["slice_id"] for s in result["selected_slices"]], ["right"])

    def test_context_can_select_slice_without_target_hit(self):
        context = [{"event_index": 777, "json_pointer": "jsonl:31/content/0"}]
        candidates = [candidate("error", (20, 0)), candidate("context", (30, 0))]
        self.assertEqual(selector.select(group(context=context), SID, candidates,
                                         "group-evidence")["selected_count"], 1)
        result = selector.select(group(context=context), SID, candidates, "group-context")
        self.assertEqual(result["selected_count"], 2)
        self.assertEqual(result["selected_slices"][1]["selection_evidence"][0]["reason"],
                         "stored_context")

    def test_parts_do_not_match_other_parts(self):
        result = selector.select(group(part=1), SID, [candidate("wrong", (20, 0)),
                                  candidate("right", (20, 1))], "group-evidence")
        self.assertEqual([s["slice_id"] for s in result["selected_slices"]], ["right"])

    def test_no_part_information_retains_whole_raw_record(self):
        self.assertTrue(selector.reference_matches({"source_index": 20, "source_part_index": 1},
                                                  candidate("coarse", (20, None))))

    def test_session_isolation_and_nonmember_rejected(self):
        data = group()
        data["evidence"].append({"unit_id": "other", "session_id": "other", "source_index": 30})
        result = selector.select(data, SID, [candidate("mine", (20, 0)),
                                 candidate("other", (30, 0))], "group-evidence")
        self.assertEqual(result["selected_count"], 1)
        with self.assertRaises(ValueError):
            selector.select(data, "outsider", [], "group-evidence")

    def test_missing_mapping_is_reported_not_forced_to_nearest_slice(self):
        result = selector.select(group(), SID, [candidate("unrelated", (10, 0))], "group-evidence")
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["unmapped_references"][0]["source_index"], 20)

    def test_open_code_reference_and_invalid_projection_pointer(self):
        self.assertEqual(selector.source_reference({"json_pointer": "/messages/10/parts/2/state"}),
                         (10, 2))
        with self.assertRaises(ValueError):
            selector.source_reference({"event_index": 20, "json_pointer": "/events/10"})
        data = group()
        data["evidence"][0]["unit_id"] = SID + "__segment-01"
        with self.assertRaises(ValueError):
            selector.select(data, SID, [], "group-evidence")

    def test_registry_extension_without_modifying_pipeline(self):
        def custom(data, session_id, candidates):
            return [{"reason": "custom_evidence", "slice_ids": [candidates[-1]["slice_id"]]}]
        selector.SELECTION_STRATEGIES["test-custom"] = custom
        try:
            result = selector.select(group(), SID, [candidate("a"), candidate("b")], "test-custom")
            self.assertEqual(result["selected_slices"][0]["slice_id"], "b")
        finally:
            del selector.SELECTION_STRATEGIES["test-custom"]

    def test_export_is_intact_core_matching_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "input" / SID
            directory.mkdir(parents=True)
            data = {"start_event": 1, "end_event": 2, "core_start_event": 1,
                    "core_end_event": 1, "events": [{"source_index": 20, "source_part_index": 0,
                        "text": "KEEP 全文"}, {"source_index": 30, "source_part_index": 0}]}
            first = directory / "segment-01.json"
            first.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            data.update({"start_event": 2, "end_event": 2, "core_start_event": 2,
                         "core_end_event": 2, "events": [{"source_index": 30, "source_part_index": 0}]})
            (directory / "segment-02.json").write_text(json.dumps(data), encoding="utf-8")
            candidates = selector.load_candidates(root / "input", SID)
            # Event 30 is an overlap in slice 1, but owned by slice 2.
            self.assertEqual(selector.select(group(index=30), SID, candidates,
                                             "group-evidence")["selected_count"], 1)
            groups = root / "groups.json"
            groups.write_text(json.dumps([group()]), encoding="utf-8")
            result = selector.run(groups, "example-group", SID, root / "input", root / "output")
            exported = Path(result["selected_slices"][0]["output_path"])
            self.assertEqual(exported.read_bytes(), first.read_bytes())
            self.assertTrue((root / "output" / "selection.json").exists())
            with self.assertRaises(ValueError):
                selector.run(groups, "example-group", SID, root / "input", root / "output")
            with self.assertRaises(ValueError):
                selector.run(groups, "example-group", SID, root / "input", root / "input" / "new")

    def test_batch_union_deduplication_isolation_and_stable_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            second_sid = "claude_code__second"
            data = group()
            data["member_session_ids"].append(second_sid)
            data["evidence"].append({**data["evidence"][0], "session_id": second_sid,
                                     "unit_id": second_sid, "source_index": 30})
            expected = {}
            for sid, hit in [(SID, 20), (second_sid, 30)]:
                directory = root / "input" / sid
                directory.mkdir(parents=True)
                for number, index in [(1, hit), (2, 99)]:
                    contents = {"start_event": 1, "end_event": 1,
                        "events": [{"source_index": index, "source_part_index": 0,
                                    "text": sid}]}
                    path = directory / f"segment-{number:02d}.json"
                    path.write_text(json.dumps(contents), encoding="utf-8")
                    if number == 1:
                        expected[sid] = path.read_bytes()
            groups = root / "groups.json"
            groups.write_text(json.dumps([data]), encoding="utf-8")
            result = selector.run(groups, "example-group", [SID, second_sid, SID],
                                  root / "input", root / "out")
            repeated = selector.run(groups, "example-group", [second_sid, SID],
                                    root / "input", root / "repeat")
            self.assertEqual(result["session_count"], 2)
            self.assertEqual(result["candidate_count"], 4)
            self.assertEqual(result["selected_count"], 2)
            self.assertEqual(result["excluded_count"], 2)
            self.assertEqual(result["selected_slice_ids"], repeated["selected_slice_ids"])
            for selected in result["selected_slices"]:
                self.assertEqual(Path(selected["output_path"]).read_bytes(),
                                 expected[selected["session_id"]])
            self.assertEqual(sum(s["selected_count"] for s in result["sessions"]), 2)
            self.assertEqual({s["session_id"] for s in result["sessions"]}, {SID, second_sid})
            self.assertTrue(all(s["selected_slices"][0]["output_path"]
                                for s in result["sessions"]))
            with self.assertRaises(ValueError):
                selector.run(groups, "example-group", [SID, "not_a_member"],
                             root / "input", root / "invalid")
            self.assertFalse((root / "invalid").exists())
            missing = "missing_directory"
            data["member_session_ids"].append(missing)
            groups.write_text(json.dumps([data]), encoding="utf-8")
            with self.assertRaises(ValueError):
                selector.run(groups, "example-group", [SID, missing], root / "input", root / "missing")
            self.assertFalse((root / "missing").exists())

    def test_empty_batch_is_rejected(self):
        with self.assertRaises(ValueError):
            selector.run(Path("not_read.json"), "example-group", [], Path("input"), Path("output"))

    def test_collapsed_content_hides_only_target_payloads_and_keeps_references(self):
        original = {"events": [
            {"category": "assistant_thinking", "source_index": 1, "text": "hidden thought",
             "signature": "hidden signature"},
            {"category": "tool_result", "source_index": 2, "content": [{"text": "hidden result"}],
             "tool_use_id": "keep-id", "is_error": True},
            {"category": "assistant_text", "source_index": 3, "text": "keep explanation"},
            {"category": "user_text", "source_index": 4, "text": "keep goal"},
            {"category": "tool_call:Edit", "source_index": 5, "arguments": {"content": "keep code"}},
            {"category": "tool_call:websearch", "source_index": 6,
             "tool_result": {"input": {"q": "keep query"}, "output": "hidden output",
                             "error": "hidden error", "status": "completed"}}]}
        transformed = selector.content_selected_full_rest_collapsed(original, False, "source.json")
        self.assertEqual(len(transformed["events"]), len(original["events"]))
        self.assertEqual([e["source_index"] for e in transformed["events"]], list(range(1,7)))
        self.assertNotIn("text", transformed["events"][0])
        self.assertNotIn("signature", transformed["events"][0])
        self.assertNotIn("content", transformed["events"][1])
        self.assertEqual(transformed["events"][1]["tool_use_id"], "keep-id")
        self.assertTrue(transformed["events"][1]["is_error"])
        self.assertEqual(transformed["events"][2:5], original["events"][2:5])
        self.assertEqual(transformed["events"][5]["tool_result"],
                         {"input": {"q": "keep query"}, "status": "completed"})
        self.assertEqual(transformed["events"][0]["collapsed_content"]["source_slice_path"], "source.json")
        self.assertEqual(original["events"][0]["text"], "hidden thought")
        self.assertEqual(selector.content_selected_full_rest_collapsed(original, True, "source.json"), original)

    def test_context_content_strategy_exports_selected_intact_and_all_others_collapsed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=root/"input"/SID
            directory.mkdir(parents=True)
            for number, index in [(1,20),(2,30)]:
                data={"start_event":1,"end_event":1,"events":[{"category":"tool_result",
                    "source_index":index,"source_part_index":0,"content":"actual evidence"}]}
                (directory/f"segment-{number:02d}.json").write_text(json.dumps(data),encoding="utf-8")
            groups=root/"groups.json"
            groups.write_text(json.dumps([group()]),encoding="utf-8")
            result=selector.run(groups,"example-group",[SID],root/"input",root/"output",
                                content_strategy="selected-full-rest-collapsed")
            self.assertEqual(result["selected_count"],1)
            self.assertEqual(result["excluded_count"],1)
            self.assertEqual(result["exported_count"],2)
            self.assertEqual(result["collapsed_event_count"],1)
            first,second=result["exported_slices"]
            self.assertEqual(Path(first["output_path"]).read_bytes(),Path(first["source_path"]).read_bytes())
            collapsed=json.loads(Path(second["output_path"]).read_text(encoding="utf-8"))
            self.assertNotIn("content",collapsed["events"][0])
            self.assertIn("collapsed_content",collapsed["events"][0])
            self.assertEqual(len(result["sessions"][0]["exported_slices"]),2)


if __name__ == "__main__":
    unittest.main()
