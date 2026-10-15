"""独立事实日志、幂等导入和可回放的效用统计；不执行维护决策。"""

import copy
import math

from clustering import unit
from models import ValidationError
from shadow import digest, nonempty, normalize_observation, timestamp


def wilson_lower(good, total, z=1.96):
    if not total:
        return None
    p = good / total
    return max(0.0, (p + z*z/(2*total) - z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))) / (1 + z*z/total))


def normalize_rating(raw, observations):
    required = {"rating_id", "event_id", "skill_id", "rank", "value", "ts"}
    if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - (required | {"query"}):
        raise ValidationError("评分字段无效")
    nonempty(raw["rating_id"], "rating_id")
    nonempty(raw["event_id"], "event_id")
    nonempty(raw["skill_id"], "skill_id")
    event = observations.get(raw["event_id"])
    if event is None or event["purpose"] != "consumption":
        raise ValidationError("评分必须绑定已记录的consumption观测")
    if type(raw["rank"]) is not int or not any(hit["skill_id"] == raw["skill_id"] and hit["rank"] == raw["rank"] for hit in event["hits"]):
        raise ValidationError("评分未绑定实际召回的skill/rank")
    if raw["value"] not in ("good", "bad"):
        raise ValidationError("评分value必须为good或bad")
    if "query" in raw and raw["query"] != event["query"]:
        raise ValidationError("评分query与观测不一致")
    return dict(raw, query=event["query"], ts=timestamp(raw["ts"]))


def _counts():
    return {"R": 0, "G": 0, "B": 0}


def _finish_counts(stats, options):
    total = stats["G"] + stats["B"]
    stats["rated"] = total
    stats["usability"] = stats["G"] / total if total else None
    stats["wilson_lower"] = wilson_lower(stats["G"], total, options["wilson_z"])
    stats["evidence"] = "SUFFICIENT" if total >= options["min_feedback_samples"] else "INSUFFICIENT"


def replay(snapshot, observations, ratings, options):
    """从事实重建派生状态，供导入、验证和显式恢复共同使用。"""
    if not isinstance(options, dict) or type(options.get("min_feedback_samples")) is not int or options["min_feedback_samples"] < 1:
        raise ValidationError("反馈最小样本量无效")
    for key in ("wilson_z", "target_recall"):
        value = options.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or (key == "target_recall" and value > 1):
            raise ValidationError(f"反馈参数无效: {key}")
    by_event, rating_ids, rated_hits, cohorts = {}, set(), set(), {}
    dimension = snapshot["manifest"]["dimension"]
    for raw in observations:
        event = normalize_observation(raw, snapshot, persisted=True)
        if raw != event or event["event_id"] in by_event:
            raise ValidationError("观测日志非规范格式或event_id重复")
        by_event[event["event_id"]] = event
        if event["purpose"] != "consumption":
            continue
        key = digest([event["context"]["corpus_id"], event["sample_kind"], event["mode"]])
        if key not in cohorts:
            cohorts[key] = {"corpus_id": event["context"]["corpus_id"], "sample_kind": event["sample_kind"],
                "mode": event["mode"], "consumption_events": 0, "skills": {}, "node_rank": {}}
            for skill_id in sorted(snapshot["state"]["skills"]):
                cohorts[key]["skills"][skill_id] = dict(_counts(), query_count=0,
                    query_vector_sum=[0.0] * dimension, by_rank={})
        cohort = cohorts[key]
        cohort["consumption_events"] += 1
        vector = unit(event["query_vector"]) if event["query_vector"] is not None else None
        for hit in event["hits"]:
            stats = cohort["skills"][hit["skill_id"]]
            stats["R"] += 1
            if vector is not None:
                stats["query_count"] += 1
                stats["query_vector_sum"] = [a+b for a, b in zip(stats["query_vector_sum"], vector)]
            rank = stats["by_rank"].setdefault(str(hit["rank"]), _counts())
            rank["R"] += 1
            node_key = digest([event["context"]["layout_id"], hit["node_id"], hit["rank"]])
            node = cohort["node_rank"].setdefault(node_key, dict(_counts(),
                layout_id=event["context"]["layout_id"], node_id=hit["node_id"], rank=hit["rank"], skills={}))
            node["R"] += 1
            node["skills"].setdefault(hit["skill_id"], _counts())["R"] += 1
    for raw in ratings:
        rating = normalize_rating(raw, by_event)
        triple = (rating["event_id"], rating["skill_id"], rating["rank"])
        if raw != rating or rating["rating_id"] in rating_ids or triple in rated_hits:
            raise ValidationError("评分日志重复或非规范格式")
        rating_ids.add(rating["rating_id"])
        rated_hits.add(triple)
        event = by_event[rating["event_id"]]
        key = digest([event["context"]["corpus_id"], event["sample_kind"], event["mode"]])
        cohort = cohorts[key]
        stats = cohort["skills"][rating["skill_id"]]
        field = "G" if rating["value"] == "good" else "B"
        stats[field] += 1
        stats["by_rank"][str(rating["rank"])][field] += 1
        hit = next(hit for hit in event["hits"] if hit["skill_id"] == rating["skill_id"])
        node_key = digest([event["context"]["layout_id"], hit["node_id"], hit["rank"]])
        cohort["node_rank"][node_key][field] += 1
        cohort["node_rank"][node_key]["skills"][rating["skill_id"]][field] += 1
    for cohort in cohorts.values():
        for stats in cohort["skills"].values():
            _finish_counts(stats, options)
            for rank in stats["by_rank"].values():
                _finish_counts(rank, options)
            count, total = stats["query_count"], stats["query_vector_sum"]
            stats["query_mean"] = [v/count for v in total] if count else None
            norm = math.hypot(*total)
            stats["query_centroid"] = unit(total) if norm > 1e-14 else None
            stats["query_centroid_status"] = "AVAILABLE" if norm > 1e-14 else ("ZERO_SUM" if count else "NO_SAMPLES")
        for node in cohort["node_rank"].values():
            _finish_counts(node, options)
            for stats in node["skills"].values():
                _finish_counts(stats, options)
                stats["relative_to_node"] = stats["usability"] - node["usability"] if stats["rated"] and node["rated"] else None
                peer_total = node["rated"] - stats["rated"]
                stats["peer_usability"] = (node["G"] - stats["G"]) / peer_total if peer_total else None
                stats["relative_to_peers"] = stats["usability"] - stats["peer_usability"] if stats["rated"] and peer_total else None
    return {"version": 1, "options": dict(options), "observation_count": len(observations),
            "rating_count": len(ratings), "cohorts": cohorts}


def import_records(snapshot, records, kind, options):
    if kind not in ("observations", "ratings") or not isinstance(records, list):
        raise ValidationError("导入类型或批次无效")
    changed = copy.deepcopy(snapshot)
    changed.setdefault("observations", [])
    changed.setdefault("ratings", [])
    observations = {row["event_id"]: row for row in changed["observations"]}
    identifier = "event_id" if kind == "observations" else "rating_id"
    existing = {row[identifier]: row for row in changed[kind]}
    rated = {(row["event_id"], row["skill_id"], row["rank"]): row for row in changed["ratings"]}
    added = duplicates = 0
    for raw in records:
        raw = copy.deepcopy(raw)
        if kind == "observations":
            if isinstance(raw, dict) and isinstance(raw.get("event_id"), str) and raw["event_id"] in existing and "context" not in raw:
                raw["context"] = existing[raw["event_id"]]["context"]
            if isinstance(raw, dict) and isinstance(raw.get("event_id"), str) and raw["event_id"] in existing and "signature_version" not in raw and "signature_version" in existing[raw["event_id"]]:
                raw["signature_version"] = existing[raw["event_id"]]["signature_version"]
            record = normalize_observation(raw, snapshot, persisted=isinstance(raw, dict) and isinstance(raw.get("event_id"), str) and raw["event_id"] in existing)
        else:
            record = normalize_rating(raw, observations)
        key = record[identifier]
        if key in existing:
            if existing[key] != record:
                raise ValidationError(f"相同{identifier}内容冲突: {key}")
            duplicates += 1
            continue
        if kind == "ratings":
            triple = (record["event_id"], record["skill_id"], record["rank"])
            if triple in rated:
                raise ValidationError("同一event/skill/rank不能重复评分或改评")
            rated[triple] = record
        changed[kind].append(record)
        existing[key] = record
        if kind == "observations":
            observations[key] = record
        added += 1
    changed["state"]["feedback"] = replay(changed, changed["observations"], changed["ratings"], options)
    return changed, {"added": added, "duplicates": duplicates}


def validate_feedback(snapshot):
    has_state = "feedback" in snapshot["state"]
    if not has_state:
        if "observations" in snapshot or "ratings" in snapshot:
            raise ValidationError("事实日志缺少派生反馈状态")
        return
    if "observations" not in snapshot or "ratings" not in snapshot:
        raise ValidationError("反馈快照缺少独立事实日志")
    options = snapshot["state"]["feedback"]["options"]
    rebuilt = replay(snapshot, snapshot["observations"], snapshot["ratings"], options)
    if rebuilt != snapshot["state"]["feedback"]:
        raise ValidationError("反馈统计与事实日志不一致")


def summary(snapshot):
    feedback = snapshot["state"]["feedback"]
    result = copy.deepcopy(feedback)
    result["status"] = "EVALUATED" if feedback["observation_count"] else "NOT_EVALUATED"
    # 向量完整保存在快照中；日常汇总不输出数万维数组。
    for cohort in result["cohorts"].values():
        for stats in cohort["skills"].values():
            for key in ("query_vector_sum", "query_mean", "query_centroid"):
                stats.pop(key)
    return result
