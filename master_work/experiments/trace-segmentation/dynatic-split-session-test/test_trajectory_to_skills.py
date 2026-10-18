"""Offline tests for the canonical raw-trajectory pipeline wiring."""

import json
import tempfile
import unittest
from pathlib import Path

import trajectory_to_skills as pipeline


class TrajectoryPipelineTests(unittest.TestCase):
    def test_sampling_is_deterministic_and_never_empty(self):
        trajectories = [
            {"harness": "h", "session_id": f"s{i}", "events": [{"text": str(i)}]}
            for i in range(8)
        ]
        first = pipeline.select_trajectories(trajectories, 0.25, 42)
        second = pipeline.select_trajectories(trajectories, 0.25, 42)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertEqual(pipeline.select_trajectories(trajectories, 1.0, 42), trajectories)

    def test_normalized_stage_preserves_jsonl_source_for_original_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "claude_code" / "fixture.jsonl"
            source.parent.mkdir()
            original = '{"message":{"role":"user","content":"failure"}}\n'
            source.write_text(original, encoding="utf-8")
            trajectories = [{"harness": "claude_code", "session_id": "fixture",
                             "events": [{"category": "user_text", "text": "failure"}],
                             "source_file": str(source)}]
            expanded, raw_root = pipeline.write_expanded_and_raw(root / "stages", trajectories)
            self.assertEqual((raw_root / "claude_code" / "fixture.jsonl").read_text(encoding="utf-8"), original)
            self.assertTrue((expanded / "index.json").is_file())

    def test_discovery_supports_normalized_trajectory_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.json"
            path.write_text(json.dumps({"trajectories": [{
                "harness": "h", "session_id": "s", "events": [{"category": "user_text", "text": "x"}]
            }]}), encoding="utf-8")
            found = pipeline.discover_trajectories(path)
            self.assertEqual([(item["harness"], item["session_id"]) for item in found], [("h", "s")])


if __name__ == "__main__":
    unittest.main()
