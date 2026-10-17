import unittest

from behavior_logic_clustering import (
    build_event_rows,
    choose_clusters,
    choose_forward_groups,
    choose_reverse_groups,
    complete_linkage,
    cluster_payload,
    lcs_similarity,
    anti_partition,
    reverse_partition,
    session_id_for_slice,
    split_pressure,
    _reverse_compaction_score,
)


class BehaviorProjectionTests(unittest.TestCase):
    def test_only_requested_event_channels_are_projected(self):
        source = {
            "start_event": 1,
            "core_start_event": 1,
            "core_end_event": 7,
            "events": [
                {"category": "record:system", "role": "metadata"},
                {"category": "user_text", "text": "Build a parser"},
                {"category": "assistant_thinking", "text": "Plan the parser"},
                {"category": "assistant_text", "text": "I will inspect the source"},
                {"category": "tool_call:Write", "tool_name": "Write", "arguments": {"file_path": "parser.cpp", "content": "SECRET_IDENTIFIER repeated repeated"}},
                {"category": "tool_result", "text": "tool output must not enter"},
                {"category": "unknown_text", "text": "unknown"},
            ],
        }
        rows = build_event_rows(source, None)
        self.assertEqual([row["channel"] for row in rows], ["user", "thinking", "assistant", "tool"])
        self.assertEqual(rows[1]["symbols"], ["H"])
        self.assertEqual(rows[3]["symbols"], ["T:write"])
        self.assertNotIn("secret_identifier", rows[3]["tokens"])
        self.assertIn("filetype:.cpp", rows[3]["operation_tokens"])

    def test_order_is_directional(self):
        self.assertLess(lcs_similarity(["U", "T:read", "T:edit"], ["U", "T:edit", "T:read"]), 1.0)


class ClusteringTests(unittest.TestCase):
    def test_session_id_is_provenance_not_a_domain_label(self):
        self.assertEqual(session_id_for_slice("session-a__segment-03"), "session-a")
        self.assertEqual(session_id_for_slice("session-a"), "session-a")

    def test_core_evidence_does_not_count_generic_operations(self):
        features = [
            {
                "slice_id": "session-a__segment-01",
                "session_id": "session-a",
                "target_vector": {"op:read": 1.0},
                "problem_vector": {"op:read": 1.0},
                "target_evidence": {"op:read": 1},
                "problem_evidence": {"op:read": 1},
                "logic_evidence": {"op:read": 1},
                "resolution_evidence": {"op:read": 1},
                "verification_evidence": {"op:read": 1},
                "sequence": ["T:read"],
                "first_user_text": "",
            },
            {
                "slice_id": "session-b__segment-01",
                "session_id": "session-b",
                "target_vector": {"op:read": 1.0},
                "problem_vector": {"op:read": 1.0},
                "target_evidence": {"op:read": 1},
                "problem_evidence": {"op:read": 1},
                "logic_evidence": {"op:read": 1},
                "resolution_evidence": {"op:read": 1},
                "verification_evidence": {"op:read": 1},
                "sequence": ["T:read"],
                "first_user_text": "",
            },
        ]
        payload = cluster_payload(features, [[1.0, 0.9], [0.9, 1.0]], [[0, 1]], "logic", {})
        cluster = payload["clusters"][0]
        self.assertEqual(cluster["unique_session_count"], 2)
        self.assertEqual(cluster["core_status"], "routing_only")

    def test_core_evidence_can_use_shared_non_structural_tokens(self):
        features = []
        for session_id in ("session-a", "session-b"):
            features.append({
                "slice_id": f"{session_id}__segment-01",
                "session_id": session_id,
                "target_vector": {"parser": 1.0},
                "problem_vector": {"parser": 1.0},
                "target_evidence": {"parser": 1},
                "problem_evidence": {"parser": 1},
                "logic_evidence": {"parser": 1},
                "resolution_evidence": {"parser": 1},
                "verification_evidence": {"parser": 1},
                "sequence": ["A", "T:read"],
                "first_user_text": "",
            })
        payload = cluster_payload(features, [[1.0, 0.9], [0.9, 1.0]], [[0, 1]], "target", {})
        self.assertEqual(payload["clusters"][0]["core_status"], "cross_session_core")

    def test_complete_linkage_does_not_force_singletons(self):
        matrix = [
            [1.0, 0.9, 0.1, 0.1],
            [0.9, 1.0, 0.1, 0.1],
            [0.1, 0.1, 1.0, 0.85],
            [0.1, 0.1, 0.85, 1.0],
        ]
        self.assertEqual(complete_linkage(matrix, 0.8), [[0, 1], [2, 3]])
        clusters, metadata = choose_clusters(matrix)
        self.assertGreaterEqual(len(clusters), 2)
        self.assertIn("coverage", metadata)

    def test_reverse_partition_covers_every_slice_without_conflicts(self):
        features = [{"slice_id": f"s{index}"} for index in range(4)]
        edges = [
            {"left_slice_id": "s0", "right_slice_id": "s1"},
            {"left_slice_id": "s1", "right_slice_id": "s2"},
        ]
        groups = reverse_partition(features, edges)
        self.assertEqual(sorted(item for group in groups for item in group), [0, 1, 2, 3])
        for group in groups:
            members = {features[index]["slice_id"] for index in group}
            self.assertFalse({"s0", "s1"}.issubset(members))
            self.assertFalse({"s1", "s2"}.issubset(members))

    def test_anti_partition_covers_every_slice_and_uses_dissimilarity(self):
        matrix = [
            [1.0, 0.05, 0.90, 0.85],
            [0.05, 1.0, 0.80, 0.75],
            [0.90, 0.80, 1.0, 0.10],
            [0.85, 0.75, 0.10, 1.0],
        ]
        groups = anti_partition(matrix, 2)
        self.assertEqual(sorted(item for group in groups for item in group), [0, 1, 2, 3])
        self.assertEqual([len(group) for group in groups], [2, 2])
        self.assertLessEqual(max(matrix[group[0]][group[1]] for group in groups), 0.25)

    def test_split_pressure_is_smooth_and_increases_with_slice_count(self):
        small = split_pressure(10, 4)
        large = split_pressure(100, 4)
        self.assertEqual(small["raw_ratio"], 2.5)
        self.assertGreater(large["effective_pressure"], small["effective_pressure"])
        self.assertGreater(large["raw_ratio"], large["effective_pressure"])

    def test_forward_groups_cover_all_slices_without_fixed_cluster_count(self):
        matrix = [
            [1.0, 0.9, 0.2, 0.2, 0.1],
            [0.9, 1.0, 0.2, 0.1, 0.1],
            [0.2, 0.2, 1.0, 0.85, 0.2],
            [0.2, 0.1, 0.85, 1.0, 0.2],
            [0.1, 0.1, 0.2, 0.2, 1.0],
        ]
        groups, metadata = choose_forward_groups(matrix, ideal_groups=2)
        self.assertEqual(sorted(item for group in groups for item in group), list(range(5)))
        self.assertEqual(metadata["mode"], "forward")
        self.assertIn("pressure", metadata)

    def test_reverse_groups_are_independent_full_cover(self):
        matrix = [
            [1.0, 0.05, 0.90, 0.85],
            [0.05, 1.0, 0.80, 0.75],
            [0.90, 0.80, 1.0, 0.10],
            [0.85, 0.75, 0.10, 1.0],
        ]
        groups, metadata = choose_reverse_groups(matrix, ideal_groups=2)
        self.assertEqual(sorted(item for group in groups for item in group), [0, 1, 2, 3])
        self.assertEqual(metadata["mode"], "reverse")
        self.assertIn("mean_within_dissimilarity", metadata)

    def test_reverse_strategy_compaction_is_a_forward_regularizer(self):
        compact = _reverse_compaction_score([[0, 1, 2, 3]], [[0, 2], [1, 3]])
        fragmented = _reverse_compaction_score([[0, 1], [2, 3]], [[0, 2], [1, 3]])
        self.assertEqual(compact, 1.0)
        self.assertLess(fragmented, compact)


if __name__ == "__main__":
    unittest.main()
