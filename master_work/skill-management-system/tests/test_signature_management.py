"""第四阶段管理流程；所有构造观测只写临时目录，不调用API。"""

import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from live_trial import observation
from manager import feedback_operation, load_config, signature_operation, verify
from models import ValidationError
from signatures import SignatureMatcher, compare_channels, resolve_with_policy, signature_version
from storage import SnapshotStore


class SignatureManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config.json")
        cls.base = SnapshotStore(cls.config["data_dir"]).read()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = dict(self.config, data_dir=Path(temporary.name))
        self.store = SnapshotStore(self.config["data_dir"])
        self.store.publish(self.base)
        feedback_operation(self.config, "feedback-init")
        signature_operation(self.config, "signature-init")
        self.snapshot = self.store.read()
        matcher = SignatureMatcher(self.snapshot["state"]["skills"])
        self.trigger, self.target = next((t, matcher.scan(t)["top1"])
            for s in self.snapshot["state"]["skills"].values() for t in s["triggers"] if matcher.scan(t)["status"] == "unique")
        self.other = next(k for k in self.snapshot["state"]["skills"] if k != self.target)

    def event(self, index, query=None, kind="real", target=None):
        # real字段仅用于在临时测试数据中覆盖正式证据门槛；向量与返回值是本地构造。
        target = target or self.target
        nodes = list(self.snapshot["state"]["clustering"]["nodes"])
        node = self.snapshot["state"]["clustering"]["assignments"][target][0]
        vector = self.snapshot["vectors"]["entries"][target]["vector"]
        result = observation(self.snapshot, {"query": query or f"{self.trigger} case-{index}"}, vector,
            [{"skill_id": target, "score": 1., "rank": 1, "node_id": node}], nodes, .5, len(nodes), True,
            "evaluation", f"stage4:{index}")
        result["baseline_top1"] = target
        result["sample_kind"] = kind
        return result

    def mine(self, phrase="novel reactor handshake EZX9911"):
        events = [self.event(i, f"{phrase} worker {i}") for i in range(3)]
        feedback_operation(self.config, "observe", events)
        signature_operation(self.config, "signature-mine")
        return self.store.read()["review_queue"]["candidates"]

    def test_init_materializes_exact_35_and_is_idempotent(self):
        generation = (self.store.root / "CURRENT").read_text().strip()
        files = list((self.store.root / "snapshots" / generation / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(files), 35)
        self.assertEqual(self.snapshot["vectors"], self.base["vectors"])
        self.assertEqual(self.snapshot["state"]["clustering"], self.base["state"]["clustering"])
        self.assertFalse(signature_operation(self.config, "signature-init")["changed"])

    def test_window_is_per_skill_and_duplicate_success_cannot_erase_disagreement(self):
        def event(index, skill, baseline=None, query_id=None):
            return {"event_id": str(index), "query_id": query_id or str(index), "query": "error " + str(index),
                    "sample_kind": "real", "baseline_top1": baseline or skill,
                    "signature": {"status": "unique", "top1": skill, "candidates": [{"skill_id": skill, "matches": ["error"]}]}}
        events = [event(i, "a") for i in range(3)] + [event(10+i, "b") for i in range(10)]
        report = compare_channels(events, min_samples=3, window_size=5)
        self.assertEqual(report["by_skill"]["a"]["real_comparisons"], 3)
        self.assertTrue(report["by_skill"]["a"]["eligible_for_signature_first"])
        report = compare_channels([event(1, "a", "b", "same"), event(2, "a", "a", "same")], min_samples=1)
        self.assertEqual(report["by_skill"]["a"]["real_agreements"], 0)

    def test_formal_observe_promotes_and_rolls_back_with_hysteresis(self):
        events = [self.event(i) for i in range(23)]
        feedback_operation(self.config, "observe", events[:19])
        self.assertEqual(self.store.read()["state"]["channel_policy"]["modes"][self.target], "shadow")
        feedback_operation(self.config, "observe", events[19:20])
        promoted = self.store.read()
        self.assertEqual(promoted["state"]["channel_policy"]["modes"][self.target], "signature_first")
        def forbidden(query):
            raise AssertionError("晋级后不应调用embedding")
        self.assertEqual(resolve_with_policy(promoted, self.trigger, forbidden)["channel"], "signature")
        for event in events[20:]:
            event["baseline_top1"] = self.other
        feedback_operation(self.config, "observe", events[20:22])
        self.assertEqual(self.store.read()["state"]["channel_policy"]["modes"][self.target], "signature_first")
        feedback_operation(self.config, "observe", events[22:])
        policy = self.store.read()["state"]["channel_policy"]
        self.assertEqual(policy["modes"][self.target], "shadow")
        self.assertEqual(len(policy["history"][-1]["event_ids"]), 23)

    def test_synthetic_does_not_promote_and_repeat_import_is_noop(self):
        events = [self.event(i, kind="synthetic") for i in range(20)]
        feedback_operation(self.config, "observe", events)
        self.assertEqual(self.store.read()["state"]["channel_policy"]["modes"][self.target], "shadow")
        pointer = (self.store.root / "CURRENT").read_bytes()
        self.assertFalse(feedback_operation(self.config, "observe", events)["changed"])
        self.assertEqual((self.store.root / "CURRENT").read_bytes(), pointer)
        self.assertEqual(signature_operation(self.config, "signature-mine")["eligible_queries"], 0)

    def test_mine_approve_updates_managed_file_only_and_resets_old_evidence(self):
        original_events = [self.event(100+i) for i in range(20)]
        feedback_operation(self.config, "observe", original_events)
        candidates = self.mine()
        candidate = next(c for c in candidates.values() if c["text"] == "EZX9911")
        source = Path(self.snapshot["state"]["skills"][self.target]["source_path"])
        fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
        before_version = signature_version(self.store.read())
        self.assertFalse(signature_operation(self.config, "signature-mine")["changed"])
        result = signature_operation(self.config, "signature-review", candidate["candidate_id"], "approve", "test-reviewer", "测试审核")
        saved = self.store.read()
        self.assertNotEqual(before_version, signature_version(saved))
        self.assertIn("EZX9911", saved["state"]["skills"][self.target]["triggers"])
        self.assertIn(self.target, saved["signature_index"]["patterns"]["ezx9911"])
        self.assertEqual(saved["vectors"], self.snapshot["vectors"])
        self.assertEqual(saved["state"]["clustering"], self.snapshot["state"]["clustering"])
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), fingerprint)
        self.assertEqual(saved["state"]["channel_policy"]["modes"][self.target], "shadow")
        self.assertEqual(saved["state"]["channel_policy"]["evidence"][self.target]["comparisons"], 0)
        managed = self.store.root / "snapshots" / result["generation"] / "skills" / saved["state"]["skills"][self.target]["name"] / "SKILL.md"
        self.assertIn('"EZX9911"', managed.read_text(encoding="utf-8"))
        self.assertEqual(verify(self.config)["signatures"], "PASS")
        self.assertFalse(signature_operation(self.config, "signature-review", candidate["candidate_id"], "approve", "test-reviewer", "测试审核")["changed"])
        # 旧版本重试仍幂等，不把旧证据改挂到新版本。
        self.assertFalse(feedback_operation(self.config, "observe", [original_events[0]])["changed"])
        stale = copy.deepcopy(next(e for e in saved["observations"] if e["event_id"] == original_events[0]["event_id"]))
        stale["event_id"] = "new-event-with-old-signature-version"
        with self.assertRaisesRegex(ValidationError, "当前签名版本"):
            feedback_operation(self.config, "observe", [stale])

    def test_reject_is_audited_and_does_not_change_index(self):
        candidate = next(iter(self.mine().values()))
        before = self.store.read()["signature_index"]
        signature_operation(self.config, "signature-review", candidate["candidate_id"], "reject", "reviewer", "不够特异")
        saved = self.store.read()
        self.assertEqual(saved["signature_index"], before)
        self.assertEqual(saved["review_queue"]["candidates"][candidate["candidate_id"]]["status"], "rejected")
        with self.assertRaises(ValidationError):
            signature_operation(self.config, "signature-review", candidate["candidate_id"], "approve", "reviewer", "改为通过")

    def test_cross_skill_common_pattern_is_filtered(self):
        events = [self.event(i, f"common reactor handshake EZX9911 first {i}") for i in range(3)]
        events += [self.event(10+i, f"common reactor handshake EZX9911 other {i}", target=self.other) for i in range(3)]
        feedback_operation(self.config, "observe", events)
        signature_operation(self.config, "signature-mine")
        self.assertFalse(any(c["text"] == "EZX9911" for c in self.store.read()["review_queue"]["candidates"].values()))

    def test_stale_candidate_requires_remine_and_quotes_roundtrip(self):
        candidates = self.mine('novel "quoted" failure \\cache EZX9911')
        first = next(c for c in candidates.values() if c["text"] == "EZX9911")
        second = next(c for c in candidates.values() if c["text"] == 'novel "quoted" failure \\cache')
        signature_operation(self.config, "signature-review", first["candidate_id"], "approve", "reviewer", "特异错误码")
        with self.assertRaisesRegex(ValidationError, "过期"):
            signature_operation(self.config, "signature-review", second["candidate_id"], "approve", "reviewer", "原文短语")
        signature_operation(self.config, "signature-mine")
        signature_operation(self.config, "signature-review", second["candidate_id"], "approve", "reviewer", "原文短语")
        self.assertIn(second["text"], self.store.read()["state"]["skills"][self.target]["triggers"])

    def test_approval_publication_failure_preserves_pending_and_files(self):
        candidate = next(iter(self.mine().values()))
        old = self.store.read()
        pointer = (self.store.root / "CURRENT").read_bytes()
        with patch("storage.os.replace", side_effect=OSError("模拟发布失败")):
            with self.assertRaises(OSError):
                signature_operation(self.config, "signature-review", candidate["candidate_id"], "approve", "reviewer", "测试")
        self.assertEqual((self.store.root / "CURRENT").read_bytes(), pointer)
        self.assertEqual(self.store.read(), old)

    def test_corrupt_index_evidence_and_materialized_file_are_rejected(self):
        candidates = self.mine()
        snapshot = self.store.read()
        bad = copy.deepcopy(snapshot)
        bad["signature_index"]["patterns"]["unknown"] = [self.target]
        with self.assertRaisesRegex(ValidationError, "签名索引"):
            self.store.publish(bad)
        bad = copy.deepcopy(snapshot)
        candidate = bad["review_queue"]["candidates"][next(iter(candidates))]
        candidate["evidence"][0]["span"] = [0, 1]
        with self.assertRaisesRegex(ValidationError, "原文证据"):
            self.store.publish(bad)
        generation = (self.store.root / "CURRENT").read_text().strip()
        path = next((self.store.root / "snapshots" / generation / "skills").glob("*/SKILL.md"))
        path.write_text("corrupted", encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "管理副本"):
            self.store.read()


if __name__ == "__main__":
    unittest.main()
