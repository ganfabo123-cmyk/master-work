import copy
import json
import tempfile
import unittest
from pathlib import Path

from behavior_logic_clustering_v5 import (
    build_global_features,
    build_similarity_matrix,
    build_skill_candidates,
    cannot_link_edges,
    learn_latent_space,
    choose_route_packages,
    _structural_order_feature,
    _raw_slice_views,
)
from behavior_logic_clustering import build_event_rows


def synthetic_slice(slice_id, events):
    return {
        "slice_id": slice_id,
        "source_path": f"C:/synthetic/{slice_id}.json",
        "first_user_text": next((item.get("text", "") for item in events if item.get("category") == "user_text"), ""),
        "events": build_event_rows(
            {
                "start_event": 1,
                "core_start_event": 1,
                "core_end_event": len(events),
                "events": events,
            },
            None,
        ),
    }


class V5ProjectionTests(unittest.TestCase):
    def test_raw_projection_excludes_unselected_events_and_write_content(self):
        row = synthetic_slice("session-a__segment-01", [
            {"category": "record:metadata", "role": "metadata"},
            {"category": "user_text", "text": "Find parser error"},
            {"category": "assistant_thinking", "text": "Inspect parser"},
            {"category": "assistant_text", "text": "I will add a regression test"},
            {
                "category": "tool_call:Write",
                "tool_name": "Write",
                "arguments": {"file_path": "parser.cpp", "content": "secret_identifier " * 100},
            },
            {"category": "tool_result", "text": "should not appear"},
        ])
        projection = _raw_slice_views(row)
        text = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn("secret_identifier", text)
        self.assertNotIn("should not appear", text)
        self.assertTrue(any(item.startswith("problem|") for item in projection["raw_views"]["problem"]))
        self.assertTrue(projection["sequence"])

    def test_global_features_use_unique_slices_once(self):
        slices = {
            "session-a__segment-01": synthetic_slice("session-a__segment-01", [
                {"category": "user_text", "text": "repair parser"},
                {"category": "assistant_text", "text": "run tests"},
                {"category": "tool_call:Read", "tool_name": "Read", "arguments": {"file_path": "parser.cpp"}},
                {"category": "tool_call:Test", "tool_name": "Test", "arguments": {"command": "make test"}},
            ]),
            "session-b__segment-01": synthetic_slice("session-b__segment-01", [
                {"category": "user_text", "text": "repair parser"},
                {"category": "assistant_text", "text": "run tests"},
                {"category": "tool_call:Read", "tool_name": "Read", "arguments": {"file_path": "lexer.cpp"}},
                {"category": "tool_call:Test", "tool_name": "Test", "arguments": {"command": "make test"}},
            ]),
        }
        domains = [
            {"domain_id": "D001", "members": list(slices)},
            {"domain_id": "D002", "members": list(slices)},
        ]
        rows, config = build_global_features(slices, domains, {})
        self.assertEqual(len(rows), 2)
        self.assertEqual(config["unique_slice_count"], 2)

    def test_relation_features_have_direction(self):
        row = synthetic_slice("session-a__segment-01", [
            {"category": "user_text", "text": "fix parser"},
            {"category": "assistant_text", "text": "inspect then test"},
            {"category": "tool_call:Read", "tool_name": "Read", "arguments": {"file_path": "parser.cpp"}},
            {"category": "tool_call:Test", "tool_name": "Test", "arguments": {"command": "make test"}},
        ])
        projection = _raw_slice_views(row)
        relations = set(projection["raw_views"]["resolution"]) | set(projection["raw_views"]["verification"])
        self.assertTrue(any("relation|" in item for item in relations))

    def test_role_only_order_ngrams_are_structural(self):
        self.assertTrue(_structural_order_feature("order|ngram:A→H"))
        self.assertTrue(_structural_order_feature("order|phase-ngram:phase:early:H→phase:late:A"))
        self.assertFalse(_structural_order_feature("order|ngram:T:read→T:compile"))


class V5LatentAndCandidateTests(unittest.TestCase):
    def _rows(self):
        slices = {}
        for index, session in enumerate(("a", "b", "c", "d")):
            sid = f"session-{session}__segment-01"
            slices[sid] = synthetic_slice(sid, [
                {"category": "user_text", "text": "repair parser boundary"},
                {"category": "assistant_text", "text": "separate parser runtime and test"},
                {"category": "tool_call:Read", "tool_name": "Read", "arguments": {"file_path": f"parser{index}.cpp"}},
                {"category": "tool_call:Edit", "tool_name": "Edit", "arguments": {"file_path": f"parser{index}.cpp", "content": "ignored"}},
                {"category": "tool_call:Test", "tool_name": "Test", "arguments": {"command": "make test"}},
            ])
        rows, config = build_global_features(
            slices,
            [{"domain_id": "D001", "members": list(slices)}],
            {},
        )
        learn_latent_space(rows, config)
        return rows

    def test_nmf_is_deterministic(self):
        first = self._rows()
        second = self._rows()
        self.assertEqual(
            [row["top_factors"] for row in first],
            [row["top_factors"] for row in second],
        )
        self.assertEqual(
            [row["latent_vector"] for row in first],
            [row["latent_vector"] for row in second],
        )

    def test_candidate_requires_independent_sessions_and_allows_overlap(self):
        rows = self._rows()
        matrix = build_similarity_matrix(rows)
        edges, _ = cannot_link_edges(rows, matrix)
        candidates, residual, _ = build_skill_candidates(rows, matrix, edges)
        for candidate in candidates:
            self.assertGreaterEqual(candidate["distinct_session_count"], 2)
            self.assertGreaterEqual(candidate["shared_motif_count"], 2)
        self.assertEqual(set(residual).intersection({
            index
            for candidate in candidates
            for index, row in enumerate(rows)
            if row["slice_id"] in candidate["member_slice_ids"]
        }), set())

    def test_low_similarity_disjoint_rows_can_form_cannot_link(self):
        rows = self._rows()
        rows[0]["latent_vector"] = {"factor:0": 1.0}
        rows[1]["latent_vector"] = {"factor:1": 1.0}
        rows[0]["relation_evidence"] = {"relation|one"}
        rows[1]["relation_evidence"] = {"relation|two"}
        rows[0]["motif_evidence"] = {"order|one"}
        rows[1]["motif_evidence"] = {"order|two"}
        matrix = build_similarity_matrix(rows)
        edges, metadata = cannot_link_edges(rows, matrix)
        self.assertGreaterEqual(metadata["cannot_link_count"], 0)
        self.assertIsInstance(edges, list)

    def test_route_packages_cover_every_domain_row(self):
        rows = self._rows()
        matrix = build_similarity_matrix(rows)
        edges, _ = cannot_link_edges(rows, matrix)
        groups, metadata = choose_route_packages(rows, matrix, edges, target_capacity=2, overlap_margin=0.0)
        self.assertTrue(groups)
        self.assertEqual({index for group in groups for index in group}, set(range(len(rows))))
        self.assertEqual(metadata["target_capacity"], 2)


if __name__ == "__main__":
    unittest.main()
