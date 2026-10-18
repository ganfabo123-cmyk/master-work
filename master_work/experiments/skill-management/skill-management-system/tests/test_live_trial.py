"""真跑新增的双通道与反馈迁移逻辑的离线边界回归。"""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clustering import dot, unit
from feedback import import_records, replay
from live_trial import observation
from maintenance import apply_membership, propose_membership
from manager import load_config
from models import ValidationError
from nodes import NodeManager
from signatures import SignatureMatcher, compare_channels
from storage import SnapshotStore, validate_snapshot
from forced_switch_trial import run_trial


class SignatureTests(unittest.TestCase):
    def test_forced_agreement_switch_persistence_fallback_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = run_trial(Path(temporary) / "forced")
            self.assertEqual(result["at_19"], "shadow")
            self.assertEqual(result["at_20"], "signature_first")
            self.assertEqual(result["after_restart"]["channel"], "signature")
            self.assertEqual(result["embedding_calls_for_promoted_hit"], 0)
            self.assertEqual(result["at_22_with_2_disagreements"], "shadow")
            self.assertEqual(result["real_api_calls"], 0)

    def test_unique_ambiguous_miss_and_casefold(self):
        matcher = SignatureMatcher({"a": {"triggers": ["LNK1105"]}, "b": {"triggers": ["LNK1107"]}})
        self.assertEqual(matcher.scan("link lnk1105")['top1'], "a")
        self.assertEqual(matcher.scan("no error")['status'], "miss")
        self.assertEqual(matcher.scan("LNK1105 and LNK1107")['status'], "ambiguous")
        shared = SignatureMatcher({"a": {"triggers": ["LNK1105"]}, "b": {"triggers": ["LNK1105"]}})
        self.assertIsNone(shared.scan("LNK1105")['top1'])

    def test_promotion_requires_distinct_real_queries(self):
        signature = {"status": "unique", "top1": "a", "candidates": [{"skill_id": "a", "matches": ["error"]}]}
        events = [{"event_id": str(i), "query_id": str(i), "query": f"error {i}", "sample_kind": "synthetic",
                   "signature": signature, "baseline_top1": "a"} for i in range(20)]
        self.assertFalse(compare_channels(events)["by_skill"]["a"]["eligible_for_signature_first"])
        for event in events:
            event["sample_kind"] = "real"
        self.assertTrue(compare_channels(events)["by_skill"]["a"]["eligible_for_signature_first"])
        for event in events:
            event["query_id"] = "repeated"
        self.assertFalse(compare_channels(events)["by_skill"]["a"]["eligible_for_signature_first"])


class MembershipFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config.json")
        cls.source = SnapshotStore(cls.config["data_dir"]).read()
        cls.source['observations'] = []
        cls.source['ratings'] = []
        cls.source['state']['feedback'] = replay(cls.source, [], [], cls.config['feedback'])
        cls.target = "skill:handle-locked-or-stale-test-binaries"

    def rated_scenario(self, value):
        snapshot = copy.deepcopy(self.source)
        manager = NodeManager(snapshot["state"]["clustering"], {k:v["vector"] for k,v in snapshot["vectors"]["entries"].items()})
        original = list(manager.layout["assignments"][self.target])
        vector = snapshot["vectors"]["entries"][self.target]["vector"]
        wrong = min((n for n in manager.layout["nodes"] if n not in original),
                    key=lambda n: dot(unit(vector), manager.layout["nodes"][n]["centroid"]))
        manager.assign(self.target, [wrong])
        snapshot["state"]["clustering"] = manager.layout
        events, ratings = [], []
        for i in range(20):
            hits = [{"skill_id": self.target, "score": 1., "rank": 1, "node_id": wrong}]
            events.append(observation(snapshot, {"query": f"fixture {i}"}, vector, hits,
                list(manager.layout["nodes"]), .5, len(manager.layout["nodes"]), True, "consumption", f"move-{i}"))
            ratings.append({"rating_id": f"move-rating-{i}", "event_id": f"move-{i}", "skill_id": self.target,
                            "rank": 1, "value": value, "ts": events[-1]["ts"]})
        snapshot = import_records(snapshot, events, "observations", self.config["feedback"])[0]
        snapshot = import_records(snapshot, ratings, "ratings", self.config["feedback"])[0]
        cohort = next(iter(snapshot["state"]["feedback"]["cohorts"]))
        return snapshot, cohort, original

    def test_good_use_query_position_moves_and_preserves_snapshot_contract(self):
        snapshot, cohort, original = self.rated_scenario("good")
        self.assertEqual(propose_membership(snapshot, cohort), [])
        proposals = propose_membership(snapshot, cohort, allow_simulation=True)
        proposal = next(p for p in proposals if p["skill_id"] == self.target)
        apply_membership(snapshot, proposal)
        self.assertEqual(snapshot["state"]["clustering"]["assignments"][self.target], original)
        validate_snapshot(snapshot)
        with self.assertRaisesRegex(ValidationError, "过期"):
            apply_membership(snapshot, proposal)

    def test_bad_utility_only_marks_content_review(self):
        snapshot, cohort, _ = self.rated_scenario("bad")
        proposal = next(p for p in propose_membership(snapshot, cohort, allow_simulation=True) if p["skill_id"] == self.target)
        self.assertEqual(proposal["action"], "content_review")
        with self.assertRaises(ValidationError):
            apply_membership(snapshot, proposal)


if __name__ == "__main__":
    unittest.main()
