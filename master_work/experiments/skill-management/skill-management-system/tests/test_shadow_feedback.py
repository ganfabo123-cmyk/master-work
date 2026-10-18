"""测试观测与评分协议、已知指标、幂等性、回放和原子发布。"""

import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feedback import import_records, replay, summary, wilson_lower
from manager import feedback_operation, load_config, verify
from models import ValidationError
from shadow import calibrate, evaluate
from storage import SnapshotStore


class ShadowFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config.json")
        cls.base = SnapshotStore(cls.config["data_dir"]).read()
        cls.base.pop("observations", None)
        cls.base.pop("ratings", None)
        cls.base["state"].pop("feedback", None)
        cls.options = cls.config["feedback"]
        cls.nodes = sorted(cls.base["state"]["clustering"]["nodes"])
        cls.node = cls.nodes[0]
        cls.skill = cls.base["state"]["clustering"]["nodes"][cls.node]["members"][0]
        cls.other_skill = cls.base["state"]["clustering"]["nodes"][cls.nodes[1]]["members"][0]

    def event(self, event_id="e1", **updates):
        event = {"event_id": event_id, "query": "fixture query " + event_id,
            "query_vector": self.base["vectors"]["entries"][self.skill]["vector"],
            "model": "text-embedding-v4", "baseline_top1": self.skill,
            "selected_nodes": [self.node], "hits": [{"skill_id": self.skill, "score": .8, "rank": 1, "node_id": self.node}],
            "parameters": {"k": len(self.nodes), "tau": .5, "m": 1},
            "ts": "2026-10-15T17:00:00+08:00", "sample_kind": "fixture", "mode": "regular",
            "purpose": "consumption", "global_fallback": False}
        event.update(updates)
        return event

    def rating(self, rating_id="r1", event_id="e1", **updates):
        result = {"rating_id": rating_id, "event_id": event_id, "skill_id": self.skill,
                  "rank": 1, "value": "good", "ts": "2026-10-15T17:01:00+08:00"}
        result.update(updates)
        return result

    def load_events(self, events):
        return import_records(self.base, events, "observations", self.options)[0]

    def stats(self, snapshot, skill=None):
        return next(iter(snapshot["state"]["feedback"]["cohorts"].values()))["skills"][skill or self.skill]

    def test_empty_state_reports_not_evaluated(self):
        snapshot = self.load_events([])
        self.assertEqual(evaluate([])["status"], "NOT_EVALUATED")
        self.assertEqual(calibrate([], .95)["cohorts"], [])
        self.assertEqual(summary(snapshot)["status"], "NOT_EVALUATED")

    def test_known_shadow_hit_rate_cost_and_missing_case(self):
        snapshot = self.load_events([self.event(), self.event("e2", baseline_top1=self.other_skill)])
        row = evaluate(snapshot["observations"])["groups"][0]
        self.assertEqual(row["route_hit_rate"], .5)
        self.assertEqual(row["avg_search_nodes"], 1)
        self.assertEqual(row["avg_candidates"], len(self.base["state"]["clustering"]["nodes"][self.node]["members"]))
        self.assertEqual(row["misses"][0]["event_id"], "e2")
        self.assertEqual(row["per_skill"][self.skill], {"baseline_queries": 1, "route_recall": 1.0})
        self.assertEqual(row["per_skill"][self.other_skill], {"baseline_queries": 1, "route_recall": 0.0})

    def test_event_duplicates_do_not_increment_and_conflict_rejects(self):
        snapshot = self.load_events([self.event(), self.event()])
        self.assertEqual(self.stats(snapshot)["R"], 1)
        unchanged, counts = import_records(snapshot, [self.event()], "observations", self.options)
        self.assertEqual(unchanged, snapshot)
        self.assertEqual(counts, {"added": 0, "duplicates": 1})
        with self.assertRaisesRegex(ValidationError, "内容冲突"):
            import_records(snapshot, [self.event(query="different")], "observations", self.options)

    def test_rating_duplicate_conflicting_id_and_double_vote(self):
        snapshot = self.load_events([self.event()])
        rated, counts = import_records(snapshot, [self.rating(), self.rating()], "ratings", self.options)
        self.assertEqual(counts, {"added": 1, "duplicates": 1})
        self.assertEqual((self.stats(rated)["G"], self.stats(rated)["B"]), (1, 0))
        for rating in (self.rating(value="bad"), self.rating("r2")):
            with self.assertRaises(ValidationError):
                import_records(rated, [rating], "ratings", self.options)

    def test_invalid_observation_batch_never_mutates_input(self):
        before = copy.deepcopy(self.base)
        invalid = self.event("bad", model="other-model")
        with self.assertRaises(ValidationError):
            self.load_events([self.event(), invalid])
        self.assertEqual(self.base, before)
        cases = [dict(query_vector=[0.] * 1024), dict(baseline_top1="skill:outsider"),
                 dict(selected_nodes=["unknown"]), dict(ts="2026-10-15T17:00:00"),
                 dict(global_fallback=True), dict(sample_kind="unverified")]
        for changes in cases:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValidationError):
                    self.load_events([self.event(**changes)])

    def test_rating_requires_actual_consumption_hit_and_rank(self):
        snapshot = self.load_events([self.event(), self.event("eval", purpose="evaluation")])
        for rating in (self.rating(event_id="missing"), self.rating(event_id="eval"),
                       self.rating(rank=2), self.rating(skill_id=self.other_skill), self.rating(query="wrong")):
            with self.assertRaises(ValidationError):
                import_records(snapshot, [rating], "ratings", self.options)

    def test_query_centroid_is_normalized_mean_and_zero_sum_is_explicit(self):
        a, b = [1.] + [0.] * 1023, [0., 1.] + [0.] * 1022
        snapshot = self.load_events([self.event(query_vector=a), self.event("e2", query_vector=b)])
        stats = self.stats(snapshot)
        self.assertEqual(stats["query_count"], 2)
        self.assertEqual(stats["query_mean"][:2], [.5, .5])
        self.assertAlmostEqual(stats["query_centroid"][0], 1/math.sqrt(2))
        cancelled = self.load_events([self.event(query_vector=a), self.event("e2", query_vector=[-v for v in a])])
        self.assertEqual(self.stats(cancelled)["query_centroid_status"], "ZERO_SUM")
        self.assertIsNone(self.stats(cancelled)["query_centroid"])

    def test_sample_kind_exploration_and_evaluation_do_not_contaminate_utility(self):
        snapshot = self.load_events([self.event(), self.event("real", sample_kind="real"),
            self.event("explore", mode="exploration"), self.event("eval", purpose="evaluation")])
        cohorts = snapshot["state"]["feedback"]["cohorts"]
        self.assertEqual(len(cohorts), 3)
        self.assertTrue(all(c["skills"][self.skill]["R"] == 1 for c in cohorts.values()))
        self.assertEqual(len(evaluate(snapshot["observations"])["groups"]), 4)

    def test_wilson_sample_gate_rank_and_relative_node_baseline(self):
        second = self.base["state"]["clustering"]["nodes"][self.node]["members"][1]
        hits = [{"skill_id": second, "score": .8, "rank": 1, "node_id": self.node}]
        snapshot = self.load_events([self.event(), self.event("e2", hits=hits)])
        snapshot = import_records(snapshot, [self.rating(), self.rating("r2", "e2", skill_id=second, value="bad")], "ratings", self.options)[0]
        node = next(iter(next(iter(snapshot["state"]["feedback"]["cohorts"].values()))["node_rank"].values()))
        self.assertEqual(node["usability"], .5)
        self.assertEqual(node["skills"][self.skill]["relative_to_node"], .5)
        self.assertEqual(node["skills"][self.skill]["relative_to_peers"], 1)
        self.assertEqual(self.stats(snapshot)["by_rank"]["1"]["G"], 1)
        self.assertEqual(self.stats(snapshot)["evidence"], "INSUFFICIENT")
        self.assertIsNone(wilson_lower(0, 0))
        self.assertAlmostEqual(wilson_lower(1, 2), .09452865480086611)
        events = [self.event(f"e{i}") for i in range(20)]
        ratings = [self.rating(f"r{i}", f"e{i}") for i in range(20)]
        enough = import_records(self.load_events(events), ratings, "ratings", self.options)[0]
        self.assertEqual(self.stats(enough)["evidence"], "SUFFICIENT")

    def test_parameter_calibration_uses_paired_cohorts_and_observed_cells(self):
        events = []
        for i in range(2):
            baseline = self.skill if i == 0 else self.other_skill
            one = self.event(f"one{i}", query=f"q{i}", baseline_top1=baseline, purpose="evaluation")
            two = copy.deepcopy(one)
            two.update(event_id=f"two{i}", selected_nodes=self.nodes[:2])
            two["parameters"]["m"] = 2
            events.extend([one, two])
        snapshot = self.load_events(events)
        result = calibrate(snapshot["observations"], .95)
        self.assertEqual(len(result["cohorts"]), 1)
        self.assertEqual(result["cohorts"][0]["recommended"]["m"], 2)
        self.assertEqual(len(result["cohorts"][0]["frontier"]), 2)
        partial = self.event("partial", query="unpaired", purpose="evaluation")
        snapshot = import_records(snapshot, [partial], "observations", self.options)[0]
        self.assertEqual(len(calibrate(snapshot["observations"], .95)["cohorts"]), 2)

    def test_repeated_query_measurements_are_equally_weighted(self):
        first = self.event(query="same")
        second = self.event("e2", query="same", selected_nodes=[self.nodes[1]], hits=[])
        third = self.event("e3", query="other")
        snapshot = self.load_events([first, second, third])
        row = evaluate(snapshot["observations"])["groups"][0]
        self.assertEqual((row["observations"], row["queries"]), (3, 2))
        self.assertEqual(row["route_hit_rate"], .75)

    def test_historical_membership_survives_current_node_rename(self):
        snapshot = self.load_events([self.event()])
        layout = snapshot["state"]["clustering"]
        layout["nodes"]["renamed"] = layout["nodes"].pop(self.node)
        for names in layout["assignments"].values():
            names[:] = ["renamed" if n == self.node else n for n in names]
        rebuilt = replay(snapshot, snapshot["observations"], [], self.options)
        self.assertEqual(rebuilt, snapshot["state"]["feedback"])
        duplicate, counts = import_records(snapshot, [self.event()], "observations", self.options)
        self.assertEqual(duplicate, snapshot)
        self.assertEqual(counts["duplicates"], 1)

    def test_snapshot_atomicity_replay_and_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = dict(self.config, data_dir=Path(temporary))
            store = SnapshotStore(config["data_dir"])
            store.publish(self.base)
            feedback_operation(config, "feedback-init")
            feedback_operation(config, "observe", [self.event()])
            feedback_operation(config, "rate", [self.rating()])
            self.assertEqual(verify(config)["ratings"], 1)
            pointer = (store.root / "CURRENT").read_bytes()
            with patch("storage.os.replace", side_effect=OSError("publication interrupted")):
                with self.assertRaises(OSError):
                    feedback_operation(config, "observe", [self.event("new")])
            self.assertEqual((store.root / "CURRENT").read_bytes(), pointer)
            self.assertEqual(len(store.read()["observations"]), 1)
            path = store.root / "snapshots" / pointer.decode().strip() / "state.json"
            state = json.loads(path.read_text(encoding="utf-8"))
            cohort = next(iter(state["feedback"]["cohorts"].values()))
            cohort["skills"][self.skill]["R"] = 999
            path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "统计与事实日志不一致"):
                store.read()
            result = feedback_operation(config, "rebuild-feedback")
            self.assertTrue(result["changed"])
            self.assertEqual(self.stats(store.read())["R"], 1)
            self.assertEqual(verify(config)["feedback"], "PASS")


if __name__ == "__main__":
    unittest.main()
