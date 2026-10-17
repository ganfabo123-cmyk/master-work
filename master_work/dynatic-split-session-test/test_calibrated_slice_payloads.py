import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import calibrated_confidence_segmentation as cutter


class PayloadTests(unittest.TestCase):
    def test_restores_structured_result_and_thinking_without_mutating_input(self):
        result = {"category": "tool_result", "part_type": "tool_result", "source_index": 2,
                  "source_part_index": 1, "tool_use_id": "call"}
        thinking = {"category": "assistant_thinking", "part_type": "thinking", "source_index": 1,
                    "source_part_index": 0}
        parts = {(2, 1): {"type": "tool_result", "content": [{"type": "text", "text": "error"}],
                         "is_error": True, "tool_use_id": "call"},
                 (1, 0): {"type": "thinking", "thinking": "真实思考", "signature": "signature"}}
        before = copy.deepcopy((result, thinking, parts))
        self.assertEqual(cutter.restore_event_payload(result, parts)["content"], parts[2, 1]["content"])
        self.assertTrue(cutter.restore_event_payload(result, parts)["is_error"])
        restored = cutter.restore_event_payload(thinking, parts)
        self.assertEqual(restored["text"], "真实思考")
        self.assertEqual(restored["signature"], "signature")
        self.assertEqual((result, thinking, parts), before)
        with self.assertRaises(ValueError):
            cutter.restore_event_payload(result, {})
        with self.assertRaises(ValueError):
            cutter.restore_event_payload(result, {(2, 1): {"type": "text"}})

    def test_opencode_result_stays_on_same_event(self):
        event = {"category": "tool_call:websearch", "part_type": "tool", "source_index": 0,
                 "source_part_index": 0, "arguments": {"query": "question"}}
        state = {"input": event["arguments"], "output": "actual output", "status": "completed"}
        restored = cutter.restore_event_payload(event, {(0, 0): {"type": "tool", "state": state}})
        self.assertEqual(restored["tool_result"], state)
        self.assertEqual(restored["category"], event["category"])
        self.assertEqual(restored["arguments"], event["arguments"])

    def test_jsonl_line_indices_include_blank_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.jsonl"
            path.write_text('\n' + json.dumps({"message": {"content": [
                {"type": "thinking", "thinking": "text"}]}}), encoding="utf-8")
            self.assertEqual(cutter.load_raw_parts(path)[1, 0]["thinking"], "text")

    def test_reuse_keeps_boundaries_and_never_loads_embeddings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw"
            raw.mkdir()
            part = {"type": "tool_result", "content": "verified", "tool_use_id": "call"}
            (raw / "session.jsonl").write_text(json.dumps({"message": {"content": [part]}}),
                                              encoding="utf-8")
            report = root / "report.json"
            report.write_text(json.dumps({"sessions": [{"harness": "claude_code", "session_id": "sid",
                              "source_file": "session.jsonl"}]}), encoding="utf-8")
            event = {"category": "tool_result", "part_type": "tool_result", "source_index": 0,
                     "source_part_index": 0, "tool_use_id": "call"}
            segments = cutter.materialize_segments([event, {"category": "user_text", "text": "keep"}],
                                                   [1], 1)
            session = {"harness": "claude_code", "session_id": "sid", "event_count": 2,
                       "boundaries_after_event": [1], "segments": segments}
            original = {"formula": {"version": "calibrated-confidence-length-banded-v3"},
                        "sessions": [session], "session_count": 1, "total_segments": 2}
            saved = root / "segments.json"
            saved.write_text(json.dumps(original), encoding="utf-8")
            original_bytes = saved.read_bytes()
            with patch.object(cutter, "load_embeddings", side_effect=AssertionError("No embeddings")):
                full = cutter.reuse_and_restore(saved, report, raw, root / "full.json", root / "slices")
            self.assertEqual(saved.read_bytes(), original_bytes)
            self.assertEqual(full["sessions"][0]["boundaries_after_event"], [1])
            self.assertEqual(full["payload_restoration"]["restored_unique_parts"], 1)
            for old, new in zip(segments, full["sessions"][0]["segments"]):
                self.assertEqual({k:v for k,v in old.items() if k != "events"},
                                 {k:v for k,v in new.items() if k != "events"})
                self.assertEqual([(e.get("category"),e.get("source_index")) for e in old["events"]],
                                 [(e.get("category"),e.get("source_index")) for e in new["events"]])
                self.assertEqual(new["events"][0]["content"], "verified")
            with self.assertRaises(ValueError):
                cutter.reuse_and_restore(saved, report, raw, root / "full.json", root / "slices")


if __name__ == "__main__":
    unittest.main()
