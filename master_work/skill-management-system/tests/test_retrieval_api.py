"""Integrated Trace/query/feedback checks; all writes use temporary stores."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_protocol import RetrievalQuery, RetrievalStatus
from embedding_client import EmbeddingApiClient, EmbeddingApiConfig
from feedback import import_records
from live_trial import observation
from manager import load_config, manage_nodes, signature_operation
from models import ValidationError
from retrieval import SkillSystem
from shadow import evaluate
from signature_mining import refresh_policy
from signatures import SignatureMatcher, compare_channels
from storage import SnapshotStore
from transactions import writer_lock


class Provider:
    model = "text-embedding-v4"
    dimension = 1024

    def __init__(self, vector):
        self.vector, self.calls = vector, []

    def embed(self, texts):
        self.calls.extend(texts)
        return [list(self.vector) for _ in texts]


class RetrievalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config.json")
        cls.base = SnapshotStore(cls.config["data_dir"]).read()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.config = dict(self.config, data_dir=Path(tmp.name))
        self.store = SnapshotStore(self.config["data_dir"])
        self.snapshot = copy.deepcopy(self.base)
        self.store.publish(self.snapshot)
        matcher = SignatureMatcher(self.snapshot["state"]["skills"])
        self.trigger, self.target = next((t, matcher.scan(t)["top1"])
            for s in self.snapshot["state"]["skills"].values() for t in s["triggers"]
            if matcher.scan(t)["status"] == "unique")
        self.vector = self.snapshot["vectors"]["entries"][self.target]["vector"]
        self.provider = Provider(self.vector)
        self.system = SkillSystem(config=self.config, embedding=self.provider)

    def current(self):
        return (self.store.root / "CURRENT").read_text()

    def promote(self):
        # Constructed "real" labels exercise production gates only in this temp store.
        nodes = list(self.snapshot["state"]["clustering"]["nodes"])
        node = self.snapshot["state"]["clustering"]["assignments"][self.target][0]
        rows = [observation(self.snapshot, {"query": self.trigger + f" seed {i}"}, self.vector,
            [{"skill_id": self.target, "rank": 1, "score": 1., "node_id": node}], nodes,
            .5, 1, True, "evaluation", f"seed-{i}",
            SignatureMatcher(self.snapshot["state"]["skills"]).scan(self.trigger + f" seed {i}")) for i in range(20)]
        for row in rows:
            row["sample_kind"] = "real"
        self.snapshot, _ = import_records(self.snapshot, rows, "observations", self.config["feedback"])
        refresh_policy(self.snapshot)
        self.assertEqual(self.snapshot["state"]["channel_policy"]["modes"][self.target], "signature_first")
        self.store.publish(self.snapshot)

    def test_default_trace_trigger_empty_and_exact_query(self):
        session = self.system.agent_session(retrieval_options={"sample_kind": "fixture"})
        before = self.current()
        for trace in ({"role": "assistant", "content": "hello"}, {"type": "tool_result", "content": "error"}):
            self.assertEqual(session.handle_raw_trace(trace).status, RetrievalStatus.NOT_TRIGGERED)
        self.assertEqual(session.handle_raw_trace("  ").status, RetrievalStatus.EMPTY_QUERY)
        self.assertEqual(self.current(), before)
        self.assertEqual(self.provider.calls, [])
        text = "  " + self.trigger + " current only  "
        result = session.handle_raw_trace({"message": {"role": "user", "content": [{"text": text}]}})
        # Legacy content-list conversion strips segment boundary whitespace.
        self.assertEqual(result.query.query_text, text.strip())
        self.assertEqual(self.provider.calls, [text.strip()])
        self.assertEqual(len(session.trajectory.raw_events), 4)
        self.assertEqual(result.status, RetrievalStatus.COMPLETED)
        self.assertIn("event_id", result.metadata)
        self.assertEqual(result.items[0].document.document_id, self.target)
        self.assertTrue(result.items[0].matched_content)

    def test_custom_trigger_and_query_use_full_trajectory_and_session_isolation(self):
        session = self.system.agent_session(
            trigger_strategy=lambda t: len(t.events) >= 2 and t.latest_event.event_type == "tool_result",
            query_builder=lambda t: RetrievalQuery(t.events[0].content + " " + t.latest_event.content, top_k=1),
            retrieval_options={"sample_kind": "fixture"})
        self.assertEqual(session.handle_raw_trace({"role": "assistant", "content": "context"}).status,
                         RetrievalStatus.NOT_TRIGGERED)
        result = session.handle_raw_trace({"type": "tool_result", "content": self.trigger})
        self.assertEqual(self.provider.calls, ["context " + self.trigger])
        self.assertEqual(len(result.items), 1)
        self.assertEqual(len(self.system.agent_session().trajectory.events), 0)

    def test_invalid_strategy_contracts_and_filters_never_call_provider(self):
        for kwargs in ({"trigger_strategy": lambda t: 1}, {"query_builder": lambda t: "bad"}):
            with self.assertRaises(TypeError):
                self.system.agent_session(**kwargs).handle_raw_trace("query")
        with self.assertRaises(ValueError):
            self.system.agent_session(query_builder=lambda t: RetrievalQuery("q", filters={"x": 1})).handle_raw_trace("q")
        self.assertEqual(self.provider.calls, [])

    def test_vector_execution_and_feedback_are_atomic_and_idempotent(self):
        result = self.system.retrieve(self.trigger, sample_kind="fixture", tau=1)
        self.assertEqual(result["channel"], "embedding")
        self.assertTrue(result["global_fallback"])
        saved = self.store.read()
        self.assertEqual(len(saved["observations"]), 2)
        self.assertEqual(sum(e["purpose"] == "consumption" for e in saved["observations"]), 1)
        hit = result["items"][0]
        rating = dict(event_id=result["event_id"], skill_id=hit["skill_id"], rank=hit["rank"],
                      value="good", rating_id="receipt-1")
        self.assertEqual(self.system.feedback(**rating)["added"], 1)
        current = self.current()
        self.assertEqual(self.system.feedback(**rating)["duplicates"], 1)
        self.assertEqual(self.current(), current)
        with self.assertRaises(ValidationError):
            self.system.feedback(**dict(rating, value="bad"))
        self.assertEqual(self.current(), current)

    def test_pure_signature_cost_and_utility_without_fake_geometry(self):
        self.promote()
        result = self.system.retrieve(self.trigger, signature_audit_rate=0)
        self.assertEqual(result["channel"], "signature")
        self.assertIsNone(result["items"][0]["score"])
        self.assertEqual(self.provider.calls, [])
        self.system.feedback(event_id=result["event_id"], skill_id=self.target, rank=1,
                             value="good", rating_id="signature-rating")
        saved = self.store.read()
        event = next(e for e in saved["observations"] if e["event_id"] == result["event_id"])
        self.assertIsNone(event["query_vector"])
        self.assertIsNone(event["baseline_top1"])
        cohort = next(iter(saved["state"]["feedback"]["cohorts"].values()))
        stats = cohort["skills"][self.target]
        self.assertEqual((stats["R"], stats["G"], stats["query_count"]), (1, 1, 0))
        self.assertIsNone(stats["query_centroid"])
        self.assertEqual(compare_channels(saved["observations"])["totals"]["queries"], 20)
        self.assertEqual(sum(r["observations"] for r in evaluate(saved["observations"])["groups"]), 20)
        signature_operation(self.config, "signature-mine")

    def test_sampled_disagreement_serves_embedding_and_rolls_back(self):
        self.promote()
        other = next(k for k in self.snapshot["state"]["skills"] if k != self.target)
        self.provider.vector = self.snapshot["vectors"]["entries"][other]["vector"]
        for i in range(3):
            result = self.system.retrieve(self.trigger + f" audit {i}", signature_audit_rate=1)
            self.assertTrue(result["signature_audited"])
            self.assertEqual(result["channel"], "embedding")
        self.assertEqual(self.store.read()["state"]["channel_policy"]["modes"][self.target], "shadow")
        result = self.system.retrieve(self.trigger + " after rollback", signature_audit_rate=0)
        self.assertEqual(result["channel"], "embedding")
        self.assertEqual(len(self.provider.calls), 4)

    def test_sampled_agreement_records_actual_signature_consumption(self):
        self.promote()
        result = self.system.retrieve(self.trigger + " agreement audit", signature_audit_rate=1)
        self.assertEqual(result["channel"], "signature")
        self.assertEqual(len(self.provider.calls), 1)
        self.assertIsNone(result["items"][0]["score"])
        saved = self.store.read()
        self.assertEqual(len(saved["observations"]), 22)
        consumption = next(e for e in saved["observations"] if e["event_id"] == result["event_id"])
        self.assertIsNotNone(consumption["query_vector"])
        self.assertEqual(compare_channels(saved["observations"])["totals"]["queries"], 21)
        # No provider is needed for a promoted, unaudited literal hit.
        result = SkillSystem(config=self.config).retrieve(self.trigger, signature_audit_rate=0)
        self.assertFalse(result["embedding_called"])

    def test_legacy_fixed_entry_uses_managed_retrieval_and_preserves_types_and_hooks(self):
        source = ROOT.parent / "dynamic-retrieval-test" / "retrieval_program.py"
        spec = importlib.util.spec_from_file_location("legacy_entry_under_test", source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(lambda: sys.modules.pop(spec.name, None))
        spec.loader.exec_module(module)
        with patch("retrieval.SkillSystem", return_value=self.system), patch.object(
                module, "developer_embedding_api_config", return_value=None):
            program = module.create_developer_program()
        program.retrieval_options["sample_kind"] = "fixture"
        self.assertIsInstance(program.handle_raw_trace({"role": "assistant", "content": "x"}), module.RetrievalResult)
        seen = []
        def hook(trajectory):
            self.assertIsInstance(trajectory, module.Trajectory)
            seen.append(trajectory.latest_event.content)
            return trajectory.latest_event.event_type == "tool_result"
        with patch.object(module, "developer_should_retrieve", side_effect=hook), patch.object(
                module, "developer_build_query", return_value=module.RetrievalQuery(self.trigger, top_k=1)):
            result = program.handle_raw_trace({"type": "tool_result", "content": "actual tool failure"})
        self.assertEqual(seen, ["actual tool failure"])
        self.assertIsInstance(result, module.RetrievalResult)
        self.assertIsInstance(result.query, module.RetrievalQuery)
        self.assertIsInstance(result.items[0], module.RetrievalHit)
        self.assertIsInstance(result.items[0].document, module.RetrievalDocument)
        self.assertIn("event_id", result.metadata)
        with patch.object(module, "developer_embedding_api_config", return_value=None):
            old = module.create_legacy_program()
        self.assertIsInstance(old, module.DynamicRetrievalProgram)
        self.assertTrue(old.documents)

    def test_backup_manifest_and_independent_legacy_import(self):
        backup = ROOT / "backups" / "legacy-retrieval-20261015-180607"
        manifest = json.loads((backup / "BACKUP_MANIFEST.json").read_text(encoding="utf-8"))
        for record in manifest:
            self.assertEqual(hashlib.sha256((backup / record["path"]).read_bytes()).hexdigest(), record["sha256"])
        self.assertFalse((backup / ".env").exists())
        spec = importlib.util.spec_from_file_location("independent_backup_under_test", backup / "retrieval_program.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(lambda: sys.modules.pop(spec.name, None))
        spec.loader.exec_module(module)
        with patch.object(module, "developer_embedding_api_config", return_value=None):
            program = module.create_developer_program()
            result = program.handle_raw_trace("legacy standalone")
        self.assertIsInstance(program, module.DynamicRetrievalProgram)
        self.assertEqual(result.status, module.RetrievalStatus.COMPLETED)
        self.assertTrue(program.documents)

    def test_provider_or_publication_failure_never_publishes_partial_facts(self):
        before = self.current()
        self.provider.model = "wrong-model"
        with self.assertRaises(ValidationError):
            self.system.retrieve("query", sample_kind="fixture")
        self.assertEqual(self.provider.calls, [])
        self.provider.model = "text-embedding-v4"
        self.provider.vector = [0.] * 1024
        with self.assertRaises(ValidationError):
            self.system.retrieve("query", sample_kind="fixture")
        self.provider.vector = self.vector
        with patch.object(self.system.store, "publish", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.system.retrieve("query", sample_kind="fixture")
        self.assertEqual(self.current(), before)
        self.assertEqual(self.store.read()["observations"], self.base["observations"])

    def test_next_query_reads_new_layout_and_threads_do_not_lose_updates(self):
        old_layout = self.system.retrieve("one", sample_kind="fixture")["context"]["layout_id"]
        current_nodes = self.snapshot["state"]["clustering"]["assignments"][self.target]
        other = next(n for n in self.snapshot["state"]["clustering"]["nodes"] if n not in current_nodes)
        manage_nodes(self.config, "assign", self.target, [other])
        result = self.system.retrieve("two", sample_kind="fixture")
        self.assertNotEqual(old_layout, result["context"]["layout_id"])
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda q: self.system.retrieve(q, sample_kind="fixture"), ["three", "four"]))
        saved = self.store.read()
        self.assertEqual(len(saved["observations"]), 8)
        self.assertEqual(len({r["event_id"] for r in results}), 2)

    def test_writer_lock_also_excludes_other_processes(self):
        script = "from transactions import writer_lock\nimport sys\ntry:\n with writer_lock(sys.argv[1]): pass\nexcept (RuntimeError, OSError): sys.exit(7)\n"
        with writer_lock(self.store.root):
            completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.store.root)],
                cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 7, completed.stderr)
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.store.root)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_http_provider_complete_chain_uses_only_query_text(self):
        payloads = []
        vector = self.vector
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                payloads.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                body = json.dumps({"data": [{"index": 0, "embedding": vector}]}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = EmbeddingApiClient(EmbeddingApiConfig(
                endpoint=f"http://127.0.0.1:{server.server_port}/embeddings", model="text-embedding-v4"))
            result = SkillSystem(config=self.config, embedding=provider).agent_session(
                retrieval_options={"sample_kind": "fixture"}).handle_raw_trace(self.trigger)
            self.assertEqual(result.status, RetrievalStatus.COMPLETED)
            self.assertEqual(payloads, [{"model": "text-embedding-v4", "input": [self.trigger]}])
            self.assertEqual(len(self.store.read()["observations"]), 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
