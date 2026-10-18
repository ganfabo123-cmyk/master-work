"""第五阶段：受控几何/评分、窗口防抖和整批发布失败；不调用API。"""

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clustering import bisect, dot, unit
from feedback import import_records
from live_trial import observation
from maintenance import (initialize_maintenance, create_maintenance_plan, apply_maintenance_plan,
                         review_content, validate_maintenance)
from manager import load_config, maintenance_operation, verify
from models import ValidationError
from nodes import NodeManager, create_layout
from storage import SnapshotStore, validate_snapshot


class MaintenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config.json")
        cls.source = SnapshotStore(cls.config["data_dir"]).read()
        cls.target = "skill:handle-locked-or-stale-test-binaries"
        cls.second = "skill:fix-test-macro-token-paste-counter"

    def setUp(self):
        self.snapshot = copy.deepcopy(self.source)
        for key in ("maintenance_queue", "maintenance_log", "observations", "ratings"):
            self.snapshot.pop(key, None)
        self.snapshot["state"].pop("maintenance", None)
        self.snapshot["state"].pop("feedback", None)
        self.snapshot = import_records(self.snapshot, [], "observations", self.config["feedback"])[0]
        initialize_maintenance(self.snapshot, self.config["maintenance"])

    def time(self, hours=0):
        return (datetime(2026, 10, 15, tzinfo=timezone.utc) + timedelta(hours=hours)).isoformat()

    def manager(self, snapshot=None):
        s = snapshot or self.snapshot
        return NodeManager(s["state"]["clustering"], {key:v["vector"] for key,v in s["vectors"]["entries"].items()})

    def misplace(self, targets=None):
        manager = self.manager()
        originals = {}
        for target in targets or [self.target]:
            originals[target] = list(manager.layout["assignments"][target])
            vector = unit(self.snapshot["vectors"]["entries"][target]["vector"])
            wrong = min((n for n in manager.layout["nodes"] if n not in originals[target]),
                        key=lambda n: dot(vector, manager.layout["nodes"][n]["centroid"]))
            manager.assign(target, [wrong])
        self.snapshot["state"]["clustering"] = manager.layout
        return originals

    def feedback(self, target=None, count=20, value="good", vector=None, prefix="batch", mode="regular"):
        target = target or self.target
        vector = vector or self.snapshot["vectors"]["entries"][target]["vector"]
        nodes = list(self.snapshot["state"]["clustering"]["nodes"])
        node = self.snapshot["state"]["clustering"]["assignments"][target][0]
        events, ratings = [], []
        for i in range(count):
            key = f"fixture:{prefix}:{target}:{i}"
            hits = [{"skill_id": target, "rank": 1, "score": .8, "node_id": node}]
            event = observation(self.snapshot, {"query": key}, vector, hits, nodes, .5, len(nodes), True,
                                "consumption", key)
            event["sample_kind"] = "fixture"
            event["mode"] = mode
            events.append(event)
            ratings.append({"rating_id": "rating:"+key, "event_id": key, "skill_id": target, "rank": 1,
                            "value": value, "ts": event["ts"]})
        self.snapshot = import_records(self.snapshot, events, "observations", self.config["feedback"])[0]
        self.snapshot = import_records(self.snapshot, ratings, "ratings", self.config["feedback"])[0]

    def plan(self, hours=0, simulated=True):
        return create_maintenance_plan(self.snapshot, now=self.time(hours), allow_simulation=simulated)

    def apply(self, plan, hours=0):
        self.snapshot, changed = apply_maintenance_plan(self.snapshot, plan["plan_id"], now=self.time(hours), allow_simulation=True)
        validate_snapshot(self.snapshot)
        return changed

    def test_default_ignores_fixture_and_sufficient_feedback_moves_atomically(self):
        original = self.misplace()
        self.feedback()
        self.assertFalse(self.plan(simulated=False)["actions"])
        plan = self.plan()
        action = next(a for a in plan["actions"] if a.get("skill_id") == self.target)
        self.assertEqual(action["action"], "move")
        with self.assertRaisesRegex(ValidationError, "模拟维护计划"):
            apply_maintenance_plan(self.snapshot, plan["plan_id"], now=self.time())
        self.assertTrue(self.apply(plan))
        self.assertEqual(self.snapshot["state"]["clustering"]["assignments"][self.target], original[self.target])
        self.assertFalse(self.apply(plan))

    def test_small_sample_does_not_move(self):
        self.misplace()
        self.feedback(count=19)
        self.assertFalse(self.plan()["actions"])

    def test_rank_peer_relative_utility_can_request_content_review(self):
        self.snapshot["state"]["maintenance"]["options"]["relative_margin"] = .04
        node = self.snapshot["state"]["clustering"]["assignments"][self.target][0]
        peer = next(s for s in self.snapshot["state"]["clustering"]["nodes"][node]["members"] if s != self.target)
        self.feedback(count=19, prefix="good")
        self.feedback(count=1, value="bad", prefix="bad")
        self.feedback(target=peer, prefix="peer")
        plan = self.plan()
        action = next(a for a in plan["actions"] if a.get("skill_id") == self.target)
        self.assertEqual(action["action"], "content_review")
        self.assertEqual(action["evidence"]["review_reason"], "low_relative_utility")
        self.assertTrue(action["evidence"]["rank_baselines"])

    def test_conflicting_cohorts_defer_moves_and_bad_utility_takes_priority(self):
        self.misplace()
        self.feedback()
        other_vector = self.snapshot["vectors"]["entries"][self.second]["vector"]
        self.feedback(prefix="exploration", mode="exploration", vector=other_vector)
        plan = self.plan()
        self.assertNotIn(self.target, [a.get("skill_id") for a in plan["actions"]])
        self.assertIn("conflicting_cohort_destinations", [d["reason"] for d in plan["deferred"]])
        self.feedback(count=25, value="bad", prefix="bad-exploration", mode="exploration", vector=other_vector)
        plan = self.plan()
        actions = [a for a in plan["actions"] if a.get("skill_id") == self.target]
        self.assertEqual([a["action"] for a in actions], ["content_review"])

    def test_low_utility_only_opens_review_and_human_closure_is_audited(self):
        self.misplace()
        before = copy.deepcopy(self.snapshot["state"]["clustering"])
        self.feedback(value="bad")
        plan = self.plan()
        self.assertEqual([a["action"] for a in plan["actions"]], ["content_review"])
        self.apply(plan)
        self.assertEqual(self.snapshot["state"]["clustering"], before)
        case_id = next(iter(self.snapshot["maintenance_queue"]["content_reviews"]))
        self.assertTrue(review_content(self.snapshot, case_id, "dismissed", "fixture-reviewer", "测试关闭"))
        self.assertFalse(review_content(self.snapshot, case_id, "dismissed", "fixture-reviewer", "测试关闭"))
        validate_maintenance(self.snapshot)
        self.feedback(count=5, value="bad", prefix="new")
        self.apply(self.plan(hours=1), hours=1)
        self.assertEqual(self.snapshot["maintenance_queue"]["content_reviews"][case_id]["status"], "open")
        self.assertEqual(len(self.snapshot["maintenance_queue"]["reviews"]), 1)

    def test_boundary_query_can_attach_to_two_nodes(self):
        layout = self.snapshot["state"]["clustering"]
        primary = layout["assignments"][self.target][0]
        vector = None
        for other in layout["nodes"]:
            if other == primary:
                continue
            candidate = unit([a+b for a,b in zip(layout["nodes"][primary]["centroid"], layout["nodes"][other]["centroid"])])
            scores = sorted(((dot(candidate,n["centroid"]), key) for key,n in layout["nodes"].items()), reverse=True)
            if primary in [n for _,n in scores[:2]] and scores[0][0]-scores[1][0] <= .04 and scores[1][0] >= .55:
                vector = candidate
                break
        self.assertIsNotNone(vector)
        self.feedback(vector=vector)
        plan = self.plan()
        self.assertEqual(plan["actions"][0]["action"], "attach")
        self.apply(plan)
        self.assertEqual(len(self.snapshot["state"]["clustering"]["assignments"][self.target]), 2)

    def test_isolated_query_creates_singleton_with_description_centroid(self):
        vector = [-v for v in self.snapshot["vectors"]["entries"][self.target]["vector"]]
        self.feedback(vector=vector)
        plan = self.plan()
        self.assertEqual(plan["actions"][0]["action"], "isolate")
        self.apply(plan)
        node = self.snapshot["state"]["clustering"]["assignments"][self.target][0]
        self.assertEqual(self.snapshot["state"]["clustering"]["nodes"][node]["count"], 1)
        expected = unit(self.snapshot["vectors"]["entries"][self.target]["vector"])
        for actual, value in zip(self.snapshot["state"]["clustering"]["nodes"][node]["centroid"], expected):
            self.assertAlmostEqual(actual, value)

    def test_cooldown_then_new_feedback_gate(self):
        self.misplace()
        self.feedback()
        self.apply(self.plan())
        self.misplace()
        for hour in (1, 2):
            plan = self.plan(hours=hour)
            self.assertIn("cooldown", [row["reason"] for row in plan["deferred"]])
            self.apply(plan, hours=hour)
        blocked = self.plan(hours=3)
        self.assertIn("not_enough_new_feedback", [row["reason"] for row in blocked["deferred"]])
        self.feedback(count=5, prefix="new")
        self.assertTrue(self.plan(hours=3)["actions"])
        self.apply(self.plan(hours=3), hours=3)

    def test_stale_plan_and_minimum_window_interval(self):
        self.misplace()
        self.feedback()
        plan = self.plan()
        self.feedback(count=1, prefix="invalidate")
        with self.assertRaisesRegex(ValidationError, "过期"):
            self.apply(plan)
        self.apply(self.plan())
        plan = self.plan(hours=.01)
        with self.assertRaisesRegex(ValidationError, "下一个维护窗口"):
            self.apply(plan, hours=.01)

    def test_move_limit_and_failure_after_first_action_leaves_input_unchanged(self):
        self.misplace([self.target, self.second])
        self.feedback(self.target)
        self.feedback(self.second)
        plan = self.plan()
        self.assertEqual(sum(a["action"] in ("move","attach","isolate") for a in plan["actions"]), 2)
        before = copy.deepcopy(self.snapshot)
        import maintenance
        execute = maintenance._execute_membership
        calls = []
        def interrupted(snapshot, action):
            calls.append(action)
            if len(calls) == 2:
                raise ValidationError("模拟第二个动作失败")
            return execute(snapshot, action)
        with patch("maintenance._execute_membership", side_effect=interrupted):
            with self.assertRaisesRegex(ValidationError, "第二个动作"):
                self.apply(plan)
        self.assertEqual(self.snapshot, before)
        self.snapshot["state"]["maintenance"]["options"]["max_moves_per_window"] = 1
        capped = self.plan()
        self.assertEqual(sum(a["action"] in ("move","attach","isolate") for a in capped["actions"]), 1)
        self.assertIn("window_move_limit", [d["reason"] for d in capped["deferred"]])

    def make_oversized(self):
        vectors = {k:unit(v["vector"]) for k,v in sorted(self.snapshot["vectors"]["entries"].items())}
        layout = create_layout(vectors, bisect(list(vectors.values()), 1), .15)
        layout["target_size"] = 2
        self.snapshot["state"]["clustering"] = layout

    def test_size_split_and_child_cooldown(self):
        self.make_oversized()
        plan = self.plan(simulated=False)
        self.assertEqual([a["action"] for a in plan["actions"]], ["split"])
        self.apply(plan)
        self.assertEqual(len(self.snapshot["state"]["clustering"]["nodes"]), 2)
        next_plan = self.plan(hours=1, simulated=False)
        self.assertFalse(next_plan["actions"])
        self.assertIn("split_cooldown", [d["reason"] for d in next_plan["deferred"]])

    def test_quality_drop_triggers_local_split_using_current_layout_only(self):
        layout = self.snapshot["state"]["clustering"]
        correct = layout["assignments"][self.target][0]
        wrong = next(n for n in layout["nodes"] if self.target not in layout["nodes"][n]["members"])
        vector = self.snapshot["vectors"]["entries"][self.target]["vector"]
        events = []
        for i in range(40):
            selected = [correct] if i < 38 else [wrong]
            event = observation(self.snapshot, {"query": f"quality fixture {i}"}, vector, [], selected, .5, 1, False,
                                "evaluation", f"quality:{i}")
            event["baseline_top1"], event["sample_kind"] = self.target, "fixture"
            events.append(event)
        self.snapshot = import_records(self.snapshot, events, "observations", self.config["feedback"])[0]
        plan = self.plan()
        split = next(a for a in plan["actions"] if a["action"] == "split")
        self.assertEqual(split["evidence"]["reason"], "route_quality_drop")
        self.assertEqual((split["evidence"]["previous_recall"], split["evidence"]["recent_recall"]), (1, .9))
        self.apply(plan)
        self.assertNotIn(correct, self.snapshot["state"]["clustering"]["nodes"])

    def test_publication_failure_and_retry_keep_entire_window_consistent(self):
        self.make_oversized()
        with tempfile.TemporaryDirectory() as temporary:
            config = dict(self.config, data_dir=Path(temporary))
            store = SnapshotStore(config["data_dir"])
            store.publish(self.snapshot)
            plan = maintenance_operation(config, "maintenance-plan", now=self.time())["plan"]
            pointer = (store.root / "CURRENT").read_bytes()
            with patch("storage.os.replace", side_effect=OSError("模拟窗口发布失败")):
                with self.assertRaises(OSError):
                    maintenance_operation(config, "maintenance-apply", plan_id=plan["plan_id"], now=self.time())
            self.assertEqual((store.root / "CURRENT").read_bytes(), pointer)
            self.assertEqual(store.read()["maintenance_queue"]["plans"][plan["plan_id"]]["status"], "pending")
            maintenance_operation(config, "maintenance-apply", plan_id=plan["plan_id"], now=self.time())
            self.assertFalse(maintenance_operation(config, "maintenance-apply", plan_id=plan["plan_id"], now=self.time())["changed"])
            self.assertEqual(verify(config)["maintenance_windows"], 1)

    def test_tampered_plan_and_log_are_rejected(self):
        self.misplace()
        self.feedback()
        plan = self.plan()
        bad = copy.deepcopy(self.snapshot)
        bad["maintenance_queue"]["plans"][plan["plan_id"]]["actions"][0]["gain"] = 999
        with self.assertRaisesRegex(ValidationError, "计划标识"):
            validate_snapshot(bad)
        self.apply(plan)
        self.snapshot["maintenance_log"][0]["window"] = 99
        with self.assertRaisesRegex(ValidationError, "维护日志"):
            validate_snapshot(self.snapshot)


if __name__ == "__main__":
    unittest.main()
