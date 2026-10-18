import tempfile
import unittest
from pathlib import Path

from behavior_logic_clustering import build_event_rows
from behavior_logic_clustering_v5 import build_global_features, learn_latent_space, build_similarity_matrix, cannot_link_edges
from behavior_logic_clustering_v6 import _split_pressure, build_quality_skill_candidates, run_domain


def synthetic_slice(slice_id, session_text="repair parser boundary"):
    return {
        "slice_id": slice_id,
        "source_path": f"C:/synthetic/{slice_id}.json",
        "first_user_text": session_text,
        "events": build_event_rows(
            {
                "start_event": 1,
                "core_start_event": 1,
                "core_end_event": 4,
                "events": [
                    {"category": "user_text", "text": session_text},
                    {"category": "assistant_text", "text": "separate boundary and verify with regression tests"},
                    {"category": "tool_call:Read", "tool_name": "Read", "arguments": {"file_path": "parser.cpp"}},
                    {"category": "tool_call:Test", "tool_name": "Test", "arguments": {"command": "make test"}},
                ],
            },
            None,
        ),
    }


class V6DomainLocalTests(unittest.TestCase):
    def _rows(self, count=6):
        slices = {
            f"session-{index}__segment-01": synthetic_slice(
                f"session-{index}__segment-01",
                "repair parser boundary and verify tests",
            )
            for index in range(count)
        }
        rows, config = build_global_features(
            slices,
            [{"domain_id": "D001", "members": list(slices)}],
            {},
        )
        learn_latent_space(rows, config)
        return rows

    def test_split_pressure_is_continuous_and_increases_with_domain_size(self):
        small = _split_pressure(8, 8)
        large = _split_pressure(80, 8)
        self.assertGreater(large["pressure"], small["pressure"])
        self.assertGreater(large["pair_quantile"], small["pair_quantile"])

    def test_candidates_use_original_domain_slices_not_session_pooling(self):
        rows = self._rows()
        matrix = build_similarity_matrix(rows)
        cannot_edges, _ = cannot_link_edges(rows, matrix)
        candidates, residual, metadata = build_quality_skill_candidates(rows, matrix, cannot_edges, 8)
        self.assertTrue(all(item["representation_unit"] == "domain_slice" for item in candidates))
        self.assertTrue(all(item["size"] >= 2 for item in candidates))
        self.assertFalse(metadata["capacity_applied"])
        self.assertIsInstance(residual, list)

    def test_candidate_has_cross_session_evidence(self):
        rows = self._rows(4)
        matrix = build_similarity_matrix(rows)
        cannot_edges, _ = cannot_link_edges(rows, matrix)
        candidates, _, _ = build_quality_skill_candidates(rows, matrix, cannot_edges, 8)
        self.assertTrue(all(item["distinct_session_count"] >= 2 for item in candidates))
        self.assertTrue(all(item["shared_motif_count"] >= 2 for item in candidates))

    def test_run_domain_writes_no_route_package(self):
        slices = {
            f"session-{index}__segment-01": synthetic_slice(f"session-{index}__segment-01")
            for index in range(4)
        }
        domain = {"domain_id": "D001", "members": list(slices)}
        with tempfile.TemporaryDirectory() as temp:
            result = run_domain(domain, slices, None, Path(temp) / "D001", 8)
            output = Path(temp) / "D001"
            self.assertEqual(result["domain_id"], "D001")
            self.assertTrue((output / "skill-candidates.json").exists())
            self.assertFalse((output / "route-packages.json").exists())


if __name__ == "__main__":
    unittest.main()
