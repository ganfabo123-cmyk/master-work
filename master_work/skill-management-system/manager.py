"""本地语料、聚类与节点管理，无网络调用。"""

import argparse
import json
import math
from pathlib import Path
import sys

from corpus import load_corpus
from embeddings import import_vectors
from models import ValidationError
from transactions import serialized, writer_lock
from storage import SnapshotStore, build_snapshot
from clustering import bisect, select_k, unit
from nodes import NodeManager, create_layout
from feedback import import_records, summary
from shadow import calibrate, evaluate
from signatures import SignatureMatcher, compare_channels, signature_version
from signature_mining import initialize_signatures, mine_candidates, review_candidate, refresh_policy
from maintenance import (initialize_maintenance, create_maintenance_plan, apply_maintenance_plan,
                         maintenance_fingerprint, review_content)


def load_config(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("配置必须为对象")
    for key in ("corpus_root", "index_path", "embedding_cache", "data_dir"):
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValidationError(f"配置缺少路径: {key}")
        payload[key] = (path.parent / value).resolve()
    if payload.get("embedding_model") != "text-embedding-v4" or type(payload.get("embedding_dimension")) is not int or payload["embedding_dimension"] != 1024:
        raise ValidationError("本阶段要求text-embedding-v4、1024维")
    # 数据目录不能覆盖来源目录或其上级。
    data = payload["data_dir"]
    for source in (payload["corpus_root"], payload["index_path"], payload["embedding_cache"]):
        if source.is_relative_to(data) or data.is_relative_to(payload["corpus_root"]):
            raise ValidationError("管理数据目录不能与来源语料重叠")
    clustering = payload.get("clustering")
    if not isinstance(clustering, dict):
        raise ValidationError("缺少clustering配置")
    for key in ("seed", "max_iterations", "bootstrap_rounds"):
        if type(clustering.get(key)) is not int or clustering[key] < (0 if key == "seed" else 1):
            raise ValidationError(f"无效聚类配置: {key}")
    candidates = clustering.get("k_candidates")
    if not isinstance(candidates, list) or not candidates or any(type(k) is not int or not 2 <= k <= 23 for k in candidates) or len(set(candidates)) != len(candidates):
        raise ValidationError("k_candidates必须为2到23之间不重复的整数列表")
    for key, upper in (("min_stability", 1), ("assign_max_cosine_distance", 2)):
        value = clustering.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= upper:
            raise ValidationError(f"无效聚类配置: {key}")
    options = payload.get("feedback")
    if not isinstance(options, dict) or type(options.get("min_feedback_samples")) is not int or options["min_feedback_samples"] < 1:
        raise ValidationError("min_feedback_samples必须为正整数")
    for key in ("wilson_z", "target_recall"):
        value = options.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or (key == "target_recall" and value > 1):
            raise ValidationError(f"无效反馈配置: {key}")
    signatures = payload.get("signatures")
    if not isinstance(signatures, dict):
        raise ValidationError("缺少signatures配置")
    for key in ("min_samples", "window_size", "min_support", "min_ngram_words", "max_ngram_words", "max_candidates"):
        if type(signatures.get(key)) is not int or signatures[key] < 1:
            raise ValidationError(f"无效签名配置: {key}")
    if signatures["window_size"] < signatures["min_samples"] or not 3 <= signatures["min_ngram_words"] <= signatures["max_ngram_words"] <= 8:
        raise ValidationError("签名窗口或n-gram范围无效")
    for key in ("promotion_threshold", "rollback_threshold", "max_other_query_fraction"):
        value = signatures.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValidationError(f"无效签名配置: {key}")
    if not 0 < signatures["rollback_threshold"] <= signatures["promotion_threshold"]:
        raise ValidationError("签名回滚阈值必须为正且不高于晋级阈值")
    maintenance = payload.get("maintenance")
    if not isinstance(maintenance, dict):
        raise ValidationError("缺少maintenance配置")
    for key in ("min_feedback_samples", "max_moves_per_window", "max_splits_per_window", "min_new_feedback", "route_window_queries"):
        if type(maintenance.get(key)) is not int or maintenance[key] < 1:
            raise ValidationError(f"无效维护配置: {key}")
    for key in ("cooldown_windows", "min_window_seconds"):
        if type(maintenance.get(key)) is not int or maintenance[key] < 0:
            raise ValidationError(f"无效维护配置: {key}")
    for key in ("good_wilson_lower", "low_usability", "relative_margin", "move_margin", "dual_min_similarity", "dual_max_gap", "orphan_similarity", "route_drop", "route_recall_target"):
        value = maintenance.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValidationError(f"无效维护配置: {key}")
    if maintenance["orphan_similarity"] >= maintenance["dual_min_similarity"] or maintenance["low_usability"] >= maintenance["good_wilson_lower"] or maintenance["route_drop"] <= 0:
        raise ValidationError("维护阈值顺序或质量下降阈值无效")
    return payload


def initialize(config: dict) -> dict:
    skills = load_corpus(config["corpus_root"], config["index_path"])
    vectors = import_vectors(config["embedding_cache"], skills, config["embedding_model"], config["embedding_dimension"])
    snapshot = build_snapshot(skills, vectors, config["embedding_model"], config["embedding_dimension"])
    with writer_lock(config["data_dir"]):
        generation = SnapshotStore(config["data_dir"]).publish(snapshot)
    return {"status": "PASS", "operation": "initialize", "skills": len(skills),
            "vectors": len(vectors), "model": config["embedding_model"],
            "dimension": config["embedding_dimension"], "generation": generation,
            "data_dir": str(config["data_dir"])}


def verify(config: dict, snapshot=None) -> dict:
    if snapshot is None:
        snapshot = SnapshotStore(config["data_dir"]).read()
    manifest = snapshot["manifest"]
    if manifest["model"] != config["embedding_model"] or manifest["dimension"] != config["embedding_dimension"]:
        raise ValidationError("快照模型或维度与配置不一致")
    skills = load_corpus(config["corpus_root"], config["index_path"])
    expected = {skill.skill_id: skill for skill in skills}
    if set(expected) != set(snapshot["state"]["skills"]):
        raise ValidationError("快照名单与当前来源名单不一致")
    for skill_id, skill in expected.items():
        saved = snapshot["state"]["skills"][skill_id]
        source_hash = snapshot["state"].get("signature_management", {}).get("source_content_sha256", {}).get(skill_id, saved["content_sha256"])
        if (source_hash != skill.content_sha256 or saved["source_path"] != skill.source_path
                or saved["provenance"] != skill.provenance):
            raise ValidationError(f"{skill_id}: 来源已变化，需要重新初始化")
    return {"status": "PASS", "operation": "verify", "skills": len(skills),
            "vectors": len(snapshot["vectors"]["entries"]), "source_consistency": "PASS",
            "model": manifest["model"], "dimension": manifest["dimension"],
            "clustering": "PASS" if "clustering" in snapshot["state"] else "NOT_INITIALIZED",
            "nodes": len(snapshot["state"].get("clustering", {}).get("nodes", {})),
            "feedback": "PASS" if "feedback" in snapshot["state"] else "NOT_INITIALIZED",
            "observations": len(snapshot.get("observations", [])), "ratings": len(snapshot.get("ratings", [])),
            "signatures": "PASS" if "signature_management" in snapshot["state"] else "NOT_INITIALIZED",
            "signature_first_skills": sum(mode == "signature_first" for mode in snapshot["state"].get("channel_policy", {}).get("modes", {}).values()),
            "maintenance": "PASS" if "maintenance" in snapshot["state"] else "NOT_INITIALIZED",
            "maintenance_windows": snapshot["state"].get("maintenance", {}).get("sequence", 0)}


@serialized
def feedback_operation(config, operation, records=None):
    store = SnapshotStore(config["data_dir"])
    snapshot = store.read(rebuild_feedback=operation == "rebuild-feedback")
    verify(config, snapshot)
    if operation in ("feedback-init", "observe", "rate", "rebuild-feedback"):
        kind = "ratings" if operation == "rate" else "observations"
        if operation in ("observe", "rate") and records is None:
            raise ValidationError("导入操作需要records")
        if operation in ("feedback-init", "rebuild-feedback"):
            records = []
        if operation == "observe" and "signature_management" in snapshot["state"]:
            matcher = SignatureMatcher(snapshot["state"]["skills"])
            existing = {event["event_id"]: event for event in snapshot.get("observations", [])}
            enriched = []
            for raw in records:
                if not isinstance(raw, dict):
                    raise ValidationError("观测必须为对象")
                raw = dict(raw)
                prior = existing.get(raw.get("event_id")) if isinstance(raw.get("event_id"), str) else None
                if "signature" not in raw:
                    raw["signature"] = prior["signature"] if prior and "signature" in prior else matcher.scan(raw.get("query", ""))
                if "signature_version" not in raw:
                    raw["signature_version"] = prior.get("signature_version", signature_version(snapshot)) if prior else signature_version(snapshot)
                enriched.append(raw)
            records = enriched
        changed, counts = import_records(snapshot, records, kind, config["feedback"])
        if "signature_management" in changed["state"]:
            refresh_policy(changed)
        if changed == snapshot and operation != "rebuild-feedback":
            return {"status": "PASS", "operation": operation, "changed": False, **counts}
        generation = store.publish(changed)
        return {"status": "PASS", "operation": operation, "generation": generation,
                "changed": True, **counts, "observations": len(changed["observations"]), "ratings": len(changed["ratings"])}
    if operation == "shadow-report":
        return evaluate(snapshot.get("observations", []))
    if operation == "calibrate":
        return calibrate(snapshot.get("observations", []), config["feedback"]["target_recall"])
    if operation == "feedback-report":
        if "feedback" not in snapshot["state"]:
            return {"status": "NOT_INITIALIZED"}
        return summary(snapshot)
    raise ValidationError("未知反馈操作")


@serialized
def signature_operation(config, operation, candidate_id=None, decision=None, reviewer=None, reason=None):
    store = SnapshotStore(config["data_dir"])
    snapshot = store.read()
    verify(config, snapshot)
    if operation == "signature-report":
        if "signature_management" not in snapshot["state"]:
            return {"status": "NOT_INITIALIZED"}
        options = snapshot["state"]["signature_management"]["options"]
        comparison = compare_channels(snapshot.get("observations", []), options["min_samples"], options["promotion_threshold"], signature_version(snapshot), options["window_size"])
        comparison["policy"]["applied"] = True
        return {"status": "PASS", "signature_version": signature_version(snapshot),
            "comparison": comparison,
            "channel_policy": snapshot["state"]["channel_policy"]}
    if operation == "signature-queue":
        return snapshot.get("review_queue", {"status": "NOT_INITIALIZED"})
    before = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    if operation == "signature-init":
        initialize_signatures(snapshot, config["signatures"])
        result = {"skills": len(snapshot["state"]["skills"]), "patterns": len(snapshot["signature_index"]["patterns"])}
    else:
        if "signature_management" not in snapshot["state"]:
            raise ValidationError("请先执行signature-init")
        if operation == "signature-refresh":
            policy = refresh_policy(snapshot)
            result = {"signature_first_skills": sum(mode == "signature_first" for mode in policy["modes"].values())}
        elif operation == "signature-mine":
            result = mine_candidates(snapshot)
        elif operation == "signature-review":
            result = {"review_changed": review_candidate(snapshot, candidate_id, decision, reviewer, reason)}
        else:
            raise ValidationError("未知签名管理操作")
    changed = before != json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    if changed:
        result["generation"] = store.publish(snapshot)
    return {"status": "PASS", "operation": operation, "changed": changed, **result}


@serialized
def maintenance_operation(config, operation, plan_id=None, case_id=None, decision=None, reviewer=None, reason=None, now=None):
    store = SnapshotStore(config["data_dir"])
    snapshot = store.read()
    verify(config, snapshot)
    before = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    if operation == "maintenance-init":
        initialize_maintenance(snapshot, config["maintenance"])
        result = {"window": snapshot["state"]["maintenance"]["sequence"]}
    else:
        if "maintenance" not in snapshot["state"]:
            raise ValidationError("请先执行maintenance-init")
        if operation == "maintenance-plan":
            plan = create_maintenance_plan(snapshot, now=now)
            result = {"plan": plan}
        elif operation == "maintenance-apply":
            snapshot, applied = apply_maintenance_plan(snapshot, plan_id, now=now)
            result = {"applied": applied, "result": snapshot["maintenance_queue"]["plans"][plan_id]["result"]}
        elif operation == "maintenance-review":
            result = {"review_changed": review_content(snapshot, case_id, decision, reviewer, reason)}
        elif operation == "maintenance-report":
            fingerprint = maintenance_fingerprint(snapshot)
            return {"status": "PASS", "maintenance": snapshot["state"]["maintenance"],
                    "plans": [{"plan_id": p["plan_id"], "status": p["status"], "actions": len(p["actions"]),
                               "stale": p["status"] == "pending" and p["input_fingerprint"] != fingerprint} for p in snapshot["maintenance_queue"]["plans"].values()],
                    "content_reviews": snapshot["maintenance_queue"]["content_reviews"], "log": snapshot["maintenance_log"]}
        else:
            raise ValidationError("未知维护操作")
    changed = before != json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    if changed:
        result["generation"] = store.publish(snapshot)
    return {"status": "PASS", "operation": operation, "changed": changed, **result}


@serialized
def cluster(config: dict, k: int | None = None) -> dict:
    verify(config)
    store = SnapshotStore(config["data_dir"])
    snapshot = store.read()
    options = config["clustering"]
    vectors = {key: unit(entry["vector"]) for key, entry in sorted(snapshot["vectors"]["entries"].items())}
    if k is None:
        fit, report = select_k(list(vectors.values()), options)
    else:
        fit = bisect(list(vectors.values()), k, options["seed"], options["max_iterations"])
        report = {"selection": "explicit_k", "selected_k": k, "task_calibrated": False, "evaluations": []}
    layout = create_layout(vectors, fit, options["assign_max_cosine_distance"])
    layout["config"] = dict(options)
    layout["selection_report"] = report
    layout["target_size"] = math.ceil(len(vectors) / len(layout["nodes"]))
    snapshot["state"]["clustering"] = layout
    generation = store.publish(snapshot)
    return {"status": "PASS", "operation": "cluster", "skills": len(vectors),
            "nodes": len(layout["nodes"]), "dual_memberships": sum(len(ns) == 2 for ns in layout["assignments"].values()),
            "task_calibrated": False, "selection_report": report, "generation": generation}


@serialized
def manage_nodes(config: dict, operation: str, skill_id=None, node_ids=None, node_id=None) -> dict:
    if operation not in ("assign", "recluster"):
        raise ValidationError("未知节点操作")
    verify(config)
    store = SnapshotStore(config["data_dir"])
    snapshot = store.read()
    layout = snapshot["state"].get("clustering")
    if layout is None:
        raise ValidationError("请先初始化聚类")
    vectors = {key: entry["vector"] for key, entry in snapshot["vectors"]["entries"].items()}
    manager = NodeManager(layout, vectors)
    if operation == "assign":
        manager.assign(skill_id, node_ids)
    else:
        targets = [node_id] if node_id is not None else manager.oversized(layout["target_size"])
        for target in targets:
            manager.split(target, config["clustering"]["seed"], config["clustering"]["max_iterations"],
                          reason="manual" if node_id else "size_limit")
        if not targets:
            return {"status": "PASS", "operation": operation, "changed": False, "reason": "no_oversized_nodes"}
    snapshot["state"]["clustering"] = manager.layout
    generation = store.publish(snapshot)
    return {"status": "PASS", "operation": operation, "changed": True,
            "nodes": len(manager.layout["nodes"]), "generation": generation,
            "changes": manager.layout["changes"][len(layout["changes"]):]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("initialize", "verify", "cluster", "assign", "recluster", "feedback-init", "observe", "rate", "rebuild-feedback", "shadow-report", "calibrate", "feedback-report", "signature-init", "signature-report", "signature-refresh", "signature-mine", "signature-queue", "signature-review", "maintenance-init", "maintenance-plan", "maintenance-apply", "maintenance-report", "maintenance-review"))
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--k", type=int, help="显式指定k；缺省为几何选型")
    parser.add_argument("--skill", help="assign使用的skill:<name>")
    parser.add_argument("--nodes", nargs="+", help="assign的1到2个目标节点")
    parser.add_argument("--node", help="局部重聚类节点；缺省只处理规模超限节点")
    parser.add_argument("--input", type=Path, help="observe/rate导入的JSONL文件")
    parser.add_argument("--candidate", help="候选签名ID")
    parser.add_argument("--decision", choices=("approve", "reject", "resolved", "dismissed"))
    parser.add_argument("--plan", help="维护计划ID")
    parser.add_argument("--case", help="内容修订项ID")
    parser.add_argument("--reviewer", help="人工审核者")
    parser.add_argument("--reason", help="审核理由")
    args = parser.parse_args()
    try:
        config = load_config(args.config.resolve())
        if args.operation == "initialize":
            result = initialize(config)
        elif args.operation == "verify":
            result = verify(config)
        elif args.operation == "cluster":
            result = cluster(config, args.k)
        elif args.operation in ("assign", "recluster"):
            result = manage_nodes(config, args.operation, args.skill, args.nodes, args.node)
        elif args.operation.startswith("signature-"):
            result = signature_operation(config, args.operation, args.candidate, args.decision, args.reviewer, args.reason)
        elif args.operation.startswith("maintenance-"):
            result = maintenance_operation(config, args.operation, args.plan, args.case, args.decision, args.reviewer, args.reason)
        else:
            records = None
            if args.operation in ("observe", "rate"):
                if args.input is None:
                    raise ValidationError("observe/rate需要--input JSONL文件")
                records = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
            result = feedback_operation(config, args.operation, records)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
