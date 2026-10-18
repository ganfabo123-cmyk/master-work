"""几何指标的已知答案、可复现性、节点不变量和事务边界。"""

import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clustering import adjusted_rand, bisect, select_k, silhouette, unit
from manager import cluster, load_config, manage_nodes, verify
from models import ValidationError
from nodes import NodeManager, create_layout, validate_layout
from storage import SnapshotStore


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.vectors = {str(i): unit(v) for i, v in enumerate([
            [1, .01], [1, .05], [1, .1], [.01, 1], [.05, 1], [.1, 1]])}

    def fit_layout(self, k=2, distance=0.0):
        fit = bisect(list(self.vectors.values()), k, seed=42)
        return create_layout(self.vectors, fit, distance)

    def test_known_metric_answers(self):
        self.assertAlmostEqual(adjusted_rand([0, 0, 1, 1], [0, 1, 0, 1]), -0.5)
        self.assertEqual(adjusted_rand([0, 0, 1, 1], [9, 9, 8, 8]), 1)
        self.assertAlmostEqual(silhouette([[1, 0], [1, 0], [0, 1]], [0, 0, 1]), 2 / 3)
        self.assertIsNone(silhouette([[1, 0], [0, 1]], [0, 0]))

    def test_bisect_tree_and_reproducibility(self):
        first = bisect(list(self.vectors.values()), 3, seed=42)
        self.assertEqual(first, bisect(list(self.vectors.values()), 3, seed=42))
        self.assertEqual(len(first["groups"]), 3)
        self.assertEqual(sorted(i for indices in first["groups"].values() for i in indices), list(range(6)))
        self.assertEqual(len(first["tree"]), 2)

    def test_single_node_and_unsplittable_input(self):
        layout = self.fit_layout(k=1)
        self.assertEqual(layout["nodes"]["n0"]["count"], 6)
        validate_layout(layout, self.vectors)
        with self.assertRaises(ValidationError):
            bisect([[1, 0]] * 3, 2)
        with self.assertRaises(ValidationError):
            unit([0, 0])

    def test_geometric_selection_is_reproducible_and_not_task_calibrated(self):
        options = {"k_candidates": [2, 3], "seed": 42, "max_iterations": 20,
                   "bootstrap_rounds": 2, "min_stability": 0.0}
        first = select_k(list(self.vectors.values()), options)
        self.assertEqual(first, select_k(list(self.vectors.values()), options))
        self.assertFalse(first[1]["task_calibrated"])
        self.assertEqual(len(first[1]["evaluations"]), 2)
        options["min_stability"] = 2.0
        fallback, report = select_k(list(self.vectors.values()), options)
        self.assertEqual(len(fallback["groups"]), 1)
        self.assertEqual(report["selected_k"], 1)

    def test_soft_assignment_never_exceeds_two_and_recomputes_centroids(self):
        layout = self.fit_layout(k=3, distance=2.0)
        self.assertTrue(all(len(names) == 2 for names in layout["assignments"].values()))
        validate_layout(layout, self.vectors)
        for node in layout["nodes"].values():
            self.assertAlmostEqual(math.hypot(*node["centroid"]), 1)

    def test_incremental_move_attach_detach_and_last_member_removal(self):
        manager = NodeManager(self.fit_layout(), self.vectors)
        names = list(manager.layout["nodes"])
        member = manager.layout["nodes"][names[0]]["members"][0]
        manager.assign(member, names)
        validate_layout(manager.layout, self.vectors)
        manager.assign(member, [names[1]])
        validate_layout(manager.layout, self.vectors)
        for remaining in list(manager.layout["nodes"][names[0]]["members"]):
            manager.assign(remaining, [names[1]])
        self.assertNotIn(names[0], manager.layout["nodes"])
        self.assertEqual(manager.layout["nodes"][names[1]]["count"], 6)
        validate_layout(manager.layout, self.vectors)

    def test_rejects_invalid_membership_without_partial_updates(self):
        manager = NodeManager(self.fit_layout(k=3), self.vectors)
        before = copy.deepcopy(manager.layout)
        for skill_id, names in [("0", []), ("0", list(before["nodes"])),
                                ("unknown", [next(iter(before["nodes"]))]), ("0", ["missing"])]:
            with self.subTest(skill_id=skill_id, names=names):
                with self.assertRaises(ValidationError):
                    manager.assign(skill_id, names)
                self.assertEqual(manager.layout, before)

    def test_zero_centroid_change_is_rejected_atomically(self):
        vectors = {"a": [1, 0], "b": [-1, 0], "c": [0, 1]}
        fit = {"groups": {"a": [0], "b": [1], "c": [2]}, "centroids": dict(vectors), "tree": {}}
        manager = NodeManager(create_layout(vectors, fit, 0), vectors)
        before = copy.deepcopy(manager.layout)
        with self.assertRaises(ValidationError):
            manager.assign("a", ["b"])
        self.assertEqual(manager.layout, before)

    def test_local_split_preserves_unaffected_node_and_secondary_memberships(self):
        manager = NodeManager(self.fit_layout(distance=2.0), self.vectors)
        target, other = list(manager.layout["nodes"])
        unaffected = copy.deepcopy(manager.layout["nodes"][other])
        manager.split(target, reason="test")
        self.assertEqual(manager.layout["nodes"][other], unaffected)
        self.assertTrue(all(len(names) == 2 for names in manager.layout["assignments"].values()))
        self.assertNotIn(target, manager.layout["nodes"])
        self.assertEqual(len(manager.layout["lineage"][target]), 2)
        self.assertEqual(manager.layout["changes"][-1]["reason"], "test")
        validate_layout(manager.layout, self.vectors)

    def test_size_limit_is_strictly_greater_than_twice_target(self):
        manager = NodeManager(self.fit_layout(k=1), self.vectors)
        self.assertEqual(manager.oversized(3), [])
        self.assertEqual(manager.oversized(2), ["n0"])


class SnapshotIntegrationTests(unittest.TestCase):
    def test_real_vectors_cluster_persist_membership_and_split(self):
        config = load_config(ROOT / "config.json")
        existing = SnapshotStore(config["data_dir"]).read()
        with tempfile.TemporaryDirectory() as temporary:
            config["data_dir"] = Path(temporary)
            store = SnapshotStore(config["data_dir"])
            store.publish(existing)
            cluster(config, 2)
            layout = store.read()["state"]["clustering"]
            cluster(config, 2)
            self.assertEqual(layout, store.read()["state"]["clustering"])
            names = sorted(layout["nodes"])
            skill_id = layout["nodes"][names[0]]["members"][0]
            manage_nodes(config, "assign", skill_id, names)
            self.assertEqual(len(store.read()["state"]["clustering"]["assignments"][skill_id]), 2)
            manage_nodes(config, "recluster", node_id=names[0])
            self.assertEqual(verify(config)["clustering"], "PASS")
            saved = store.read()
            pointer = (store.root / "CURRENT").read_bytes()
            node = next(iter(saved["state"]["clustering"]["nodes"].values()))
            node["centroid"][0] += .1
            with self.assertRaisesRegex(ValidationError, "质心不变量"):
                store.publish(saved)
            self.assertEqual((store.root / "CURRENT").read_bytes(), pointer)


if __name__ == "__main__":
    unittest.main()
