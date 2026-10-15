"""验证真实语料契约和失败边界；所有写入只发生在临时目录。"""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corpus import load_corpus
from embeddings import import_vectors
from manager import initialize, load_config, verify
from models import ValidationError
from storage import SnapshotStore, build_snapshot


class PhaseOneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config.json")
        cls.skills = load_corpus(cls.config["corpus_root"], cls.config["index_path"])
        cls.cache = json.loads(cls.config["embedding_cache"].read_text(encoding="utf-8"))
        cls.vectors = import_vectors(cls.config["embedding_cache"], cls.skills, "text-embedding-v4", 1024)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def write_json(self, name, payload):
        path = self.directory / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def snapshot(self):
        return build_snapshot(self.skills, self.vectors, "text-embedding-v4", 1024)

    def test_real_corpus_roundtrip_excludes_nonmembers_and_preserves_sources(self):
        paths = [self.config["index_path"], self.config["embedding_cache"]]
        paths.extend(Path(skill.source_path) for skill in self.skills)
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        config = dict(self.config, data_dir=self.directory / "data")
        result = initialize(config)
        self.assertEqual((result["skills"], result["vectors"]), (35, 35))
        self.assertEqual(verify(config)["status"], "PASS")
        saved = SnapshotStore(config["data_dir"]).read()
        ids = {skill.skill_id for skill in self.skills}
        self.assertEqual(set(saved["vectors"]["entries"]), ids)
        self.assertEqual(sum(len(s.triggers) for s in self.skills), 96)
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, before)

    def test_rejects_wrong_count_duplicate_and_non_b_arm(self):
        rows = [json.loads(line) for line in self.config["index_path"].read_text(encoding="utf-8").splitlines() if line.strip()]
        cases = [rows[:-1], rows[:-1] + [rows[0]], copy.deepcopy(rows)]
        cases[-1][0]["arm"] = "A-original"
        for rows in cases:
            with self.subTest(case=len(rows)):
                path = self.directory / "index.jsonl"
                path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    load_corpus(self.config["corpus_root"], path)

    def test_rejects_missing_stale_and_invalid_vectors(self):
        skill_id = self.skills[0].skill_id
        for case in ("missing", "sha256", "dimension", "nan", "infinity", "boolean", "zero", "model"):
            with self.subTest(case=case):
                cache = copy.deepcopy(self.cache)
                entry = cache["entries"][skill_id]
                if case == "missing":
                    del cache["entries"][skill_id]
                elif case == "sha256":
                    entry["sha256"] = "outdated"
                elif case == "dimension":
                    entry["vector"] = [1.0]
                elif case == "zero":
                    entry["vector"] = [0.0] * 1024
                elif case == "model":
                    cache["model"] = "other-model"
                else:
                    entry["vector"][0] = {"nan": float("nan"), "infinity": float("inf"), "boolean": True}[case]
                cache_path = self.write_json("cache.json", cache)
                with self.assertRaises(ValidationError):
                    import_vectors(cache_path, self.skills, "text-embedding-v4", 1024)

    def test_invalid_input_never_creates_published_state(self):
        cache = copy.deepcopy(self.cache)
        cache["entries"][self.skills[0].skill_id]["sha256"] = "stale"
        config = dict(self.config, embedding_cache=self.write_json("bad-cache.json", cache), data_dir=self.directory / "data")
        with self.assertRaises(ValidationError):
            initialize(config)
        self.assertFalse(config["data_dir"].exists())

    def test_pointer_failure_preserves_previous_snapshot(self):
        store = SnapshotStore(self.directory / "data")
        store.publish(self.snapshot())
        pointer = (store.root / "CURRENT").read_bytes()
        old = store.read()
        changed = self.snapshot()
        changed["manifest"]["created_at"] = "new-generation"
        with patch("storage.os.replace", side_effect=OSError("simulated publication failure")):
            with self.assertRaises(OSError):
                store.publish(changed)
        self.assertEqual((store.root / "CURRENT").read_bytes(), pointer)
        self.assertEqual(store.read(), old)

    def test_snapshot_rejects_extra_member_and_content_corruption(self):
        store = SnapshotStore(self.directory / "data")
        for case in ("extra", "body", "fingerprint"):
            with self.subTest(case=case):
                snapshot = self.snapshot()
                skill_id = self.skills[0].skill_id
                if case == "extra":
                    snapshot["vectors"]["entries"]["skill:outsider"] = snapshot["vectors"]["entries"][skill_id]
                elif case == "body":
                    snapshot["state"]["skills"][skill_id]["body"] = "corrupt"
                else:
                    snapshot["vectors"]["entries"][skill_id]["sha256"] = "corrupt"
                with self.assertRaises(ValidationError):
                    store.publish(snapshot)
        self.assertFalse(store.root.exists())

    def test_verify_detects_changed_source_index(self):
        config = dict(self.config, data_dir=self.directory / "data")
        initialize(config)
        rows = [json.loads(line) for line in self.config["index_path"].read_text(encoding="utf-8").splitlines() if line.strip()]
        rows[0]["status"] = "changed"
        index = self.directory / "changed.jsonl"
        index.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "来源已变化"):
            verify(dict(config, index_path=index))


if __name__ == "__main__":
    unittest.main()
