"""Skill query execution. Query facts and management state share one publication."""

from datetime import datetime, timezone
from pathlib import Path
import math
import random
import uuid
import time

from clustering import dot, unit
from embeddings import validate_vector
from feedback import import_records
from manager import load_config
from models import ValidationError
from shadow import context_for, nonempty
from signature_mining import refresh_policy
from signatures import SignatureMatcher, signature_version
from storage import SnapshotStore
from transactions import writer_lock
from runtime_audit import (RuntimeAudit, audited_retrieval, embedding_unavailable,
                           record_embedding)


def rank(snapshot, vector, selected, top_k, minimum=-1.0):
    nodes = snapshot["state"]["clustering"]["nodes"]
    members = {skill for node in selected for skill in nodes[node]["members"]}
    query = unit(vector)
    scored = sorted(((max(-1., min(1., dot(query, unit(snapshot["vectors"]["entries"][skill]["vector"])))), skill)
                     for skill in members), key=lambda pair: (-pair[0], pair[1]))
    return [{"skill_id": skill, "score": score, "rank": i, "node_id": next(
        node for node in sorted(selected) if skill in nodes[node]["members"])}
        for i, (score, skill) in enumerate((pair for pair in scored if pair[0] >= minimum), 1)][:top_k]


def route(snapshot, vector, tau, m):
    nodes = snapshot["state"]["clustering"]["nodes"]
    query = unit(vector)
    scores = {node: dot(query, item["centroid"]) for node, item in nodes.items()}
    ordered = sorted(scores, key=lambda node: (-scores[node], node))
    fallback = scores[ordered[0]] < tau
    return (ordered if fallback else sorted(set(ordered[:m]) | {n for n, s in scores.items() if s >= tau})), fallback


class SkillSystem:
    """One local API. Embedding providers expose model, dimension and embed([text])."""

    def __init__(self, config_path=None, *, embedding=None, config=None):
        self.config = dict(config) if config is not None else load_config(
            Path(config_path) if config_path else Path(__file__).with_name("config.json"))
        self.store = SnapshotStore(self.config["data_dir"])
        self.embedding = embedding
        self.audit = RuntimeAudit(self.config["data_dir"])

    def _query_vector(self, query, snapshot, minimum, purpose):
        started = time.monotonic()
        self.audit.emit('embedding_started', purpose=purpose, query=query,
                        model=snapshot['manifest']['model'])
        try:
            provider = self.embedding
            if provider is None:
                raise ValidationError('本次需要查询embedding，请配置embedding provider')
            if provider.model != snapshot['manifest']['model'] or provider.dimension != snapshot['manifest']['dimension']:
                raise ValidationError('embedding provider模型或维度与快照不一致')
            vectors = provider.embed([query])
            if not isinstance(vectors, list) or len(vectors) != 1:
                raise ValidationError('embedding provider必须返回一个查询向量')
            vector = list(validate_vector(vectors[0], snapshot['manifest']['dimension'], 'query'))
            candidates = rank(snapshot, vector, list(snapshot['state']['clustering']['nodes']),
                              len(snapshot['state']['skills']))
            for hit in candidates:
                hit['name'] = snapshot['state']['skills'][hit['skill_id']]['name']
                hit['passes_min_similarity'] = hit['score'] >= minimum
            details = {'status': 'measured', 'purpose': purpose, 'query': query,
                       'model': provider.model, 'min_similarity': minimum,
                       'elapsed_ms': round((time.monotonic()-started)*1000, 3),
                       'top_similarity': candidates[0]['score'] if candidates else None,
                       'candidates': candidates}
            record_embedding(self.audit, details)
            return vector
        except Exception as exc:
            record_embedding(self.audit, dict(embedding_unavailable(str(exc)),
                             status='failed', purpose=purpose, error_type=type(exc).__name__,
                             elapsed_ms=round((time.monotonic()-started)*1000, 3)))
            raise

    def diagnostic_similarity(self, query, *, min_similarity=.5, snapshot=None):
        """Extra audit-only embedding; never changes routing, hits or observations."""
        if not isinstance(query, str) or not query.strip():
            details = embedding_unavailable('empty_text')
            record_embedding(self.audit, details)
            return details
        try:
            self._query_vector(query, snapshot if snapshot is not None else self.store.read(),
                               min_similarity, 'diagnostic_only')
        except Exception as exc:
            # The failure has its own audit event; a diagnostic must not turn a
            # non-trigger/signature result into a retrieval failure.
            record_embedding(self.audit, dict(embedding_unavailable(str(exc)),
                             status='failed', purpose='diagnostic_only', error_type=type(exc).__name__))
            self.audit.emit('diagnostic_failed', error_type=type(exc).__name__, error=str(exc))
            return None

    @audited_retrieval
    def retrieve(self, query, *, top_k=3, min_similarity=.5, tau=.5, m=1,
                 signature_audit_rate=.1, sample_kind="real", mode="regular"):
        nonempty(query, "query")
        for name, value in (("top_k", top_k), ("m", m)):
            if type(value) is not int or value < 1:
                raise ValidationError(f"{name}必须为正整数")
        for name, value, low in (("tau", tau, -1), ("min_similarity", min_similarity, -1),
                                 ("signature_audit_rate", signature_audit_rate, 0)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= 1:
                raise ValidationError(f"{name}超出范围")
        if sample_kind not in ("real", "synthetic", "fixture") or mode not in ("regular", "exploration"):
            raise ValidationError("样本类型或模式无效")
        # Deliberately serialize network + read/modify/publish at this small scale.
        # No manager can replace the query's layout or policy halfway through execution.
        with writer_lock(self.config["data_dir"]):
            generation = (self.store.root / "CURRENT").read_text(encoding="utf-8").strip()
            snapshot = self.store.read()
            for required in ("clustering", "feedback", "signature_management"):
                if required not in snapshot["state"]:
                    raise ValidationError(f"管理库尚未初始化: {required}")
            nodes = snapshot["state"]["clustering"]["nodes"]
            if m > len(nodes):
                raise ValidationError("m超过当前节点数")
            signature = SignatureMatcher(snapshot["state"]["skills"]).scan(query)
            policy = snapshot["state"].get("channel_policy", {})
            cheap = signature["top1"] is not None and not policy.get("simulation", True) and (
                policy.get("modes", {}).get(signature["top1"]) == "signature_first")
            audited = cheap and random.random() < signature_audit_rate
            self.audit.emit('signature_decision', signature=signature,
                            signature_first=cheap, shadow_audited=audited)
            vector, baseline, evaluation = None, None, None
            event_id = uuid.uuid4().hex
            now = datetime.now(timezone.utc).isoformat()
            base = {"query": query, "model": snapshot["manifest"]["model"], "ts": now,
                    "sample_kind": sample_kind, "mode": mode, "context": context_for(snapshot),
                    "signature": signature, "signature_version": signature_version(snapshot)}
            if not cheap or audited:
                vector = self._query_vector(query, snapshot, min_similarity, 'retrieval')
                baseline = rank(snapshot, vector, list(nodes), 1)[0]["skill_id"]
                selected, fallback = route(snapshot, vector, tau, m)
                hits = rank(snapshot, vector, selected, top_k, min_similarity)
                if not hits and not fallback:
                    selected, fallback = list(nodes), True
                    hits = rank(snapshot, vector, selected, top_k, min_similarity)
                self.audit.emit('routing_completed', selected_nodes=selected,
                    centroid_scores={node: dot(unit(vector), item['centroid']) for node,item in nodes.items()},
                    global_fallback=fallback, min_similarity=min_similarity, hits=hits)
                evaluation = dict(base, event_id=event_id + ":evaluation", query_vector=vector,
                    baseline_top1=baseline, selected_nodes=selected, hits=hits,
                    parameters={"k": len(nodes), "tau": tau, "m": m}, purpose="evaluation",
                    global_fallback=fallback, channel="embedding")
            channel = "signature" if cheap and (not audited or signature["top1"] == baseline) else "embedding"
            if channel == "signature":
                skill = signature["top1"]
                selected = [sorted(snapshot["state"]["clustering"]["assignments"][skill])[0]]
                hits = [{"skill_id": skill, "rank": 1, "score": None, "node_id": selected[0]}]
                fallback = False
                if vector is None:
                    self.diagnostic_similarity(query, min_similarity=min_similarity, snapshot=snapshot)
            consumption = dict(base, event_id=event_id, query_vector=vector, baseline_top1=baseline,
                selected_nodes=selected, hits=hits, parameters={"k": len(nodes), "tau": tau,
                "m": 1 if channel == "signature" else m}, purpose="consumption",
                global_fallback=fallback, channel=channel)
            records = [consumption] + ([evaluation] if evaluation else [])
            updated, _ = import_records(snapshot, records, "observations", self.config["feedback"])
            refresh_policy(updated)
            published = self.store.publish(updated)
            return {"event_id": event_id, "query": query, "channel": channel,
                "snapshot_generation": generation, "published_generation": published,
                "context": base["context"], "signature_version": base["signature_version"],
                "signature": signature, "embedding_called": vector is not None,
                "signature_audited": audited, "global_fallback": fallback,
                "items": [dict(hit, name=snapshot["state"]["skills"][hit["skill_id"]]["name"],
                    description=snapshot["state"]["skills"][hit["skill_id"]]["description"],
                    body=snapshot["state"]["skills"][hit["skill_id"]]["body"],
                    full_content=snapshot["state"]["skills"][hit["skill_id"]]["full_content"],
                    source_path=snapshot["state"]["skills"][hit["skill_id"]]["source_path"]) for hit in hits]}

    def feedback(self, *, event_id, skill_id, rank, value, rating_id):
        """The caller supplies a stable rating_id for idempotent delivery retries."""
        with writer_lock(self.config["data_dir"]):
            snapshot = self.store.read()
            previous = next((r for r in snapshot["ratings"] if r["rating_id"] == rating_id), None)
            record = {"event_id": event_id, "skill_id": skill_id, "rank": rank, "value": value,
                "rating_id": rating_id, "ts": previous["ts"] if previous else datetime.now(timezone.utc).isoformat()}
            updated, counts = import_records(snapshot, [record], "ratings", self.config["feedback"])
            if counts["added"]:
                self.store.publish(updated)
            return {"status": "PASS", **counts}

    def agent_session(self, **strategies):
        from agent import AgentSession
        return AgentSession(self, **strategies)
