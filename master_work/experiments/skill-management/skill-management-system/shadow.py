"""观测协议、影子指标及已有参数实验的对比；不执行检索。"""

from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math

from embeddings import validate_vector
from models import ValidationError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def nonempty(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field}必须为非空字符串")
    return value


def timestamp(value):
    nonempty(value, "ts")
    try:
        if datetime.fromisoformat(value).utcoffset() is None:
            raise ValueError("missing timezone")
    except ValueError as exc:
        raise ValidationError("ts必须为带时区的ISO时间") from exc
    return value


def context_for(snapshot):
    layout = snapshot["state"].get("clustering")
    if layout is None:
        raise ValidationError("影子观测需要已初始化的节点")
    context = {
        "model": snapshot["manifest"]["model"], "dimension": snapshot["manifest"]["dimension"],
        "fingerprints": {key: entry["sha256"] for key, entry in sorted(snapshot["vectors"]["entries"].items())},
        "node_members": {key: sorted(node["members"]) for key, node in sorted(layout["nodes"].items())},
    }
    context["corpus_id"] = digest({key: context[key] for key in ("model", "dimension", "fingerprints")})
    context["layout_id"] = digest(context)
    return context


def validate_context(context, snapshot):
    if not isinstance(context, dict) or set(context) != {"model", "dimension", "fingerprints", "node_members", "corpus_id", "layout_id"}:
        raise ValidationError("观测context字段无效")
    if context["model"] != snapshot["manifest"]["model"] or context["dimension"] != snapshot["manifest"]["dimension"]:
        raise ValidationError("观测模型或维度与管理空间不一致")
    ids = set(snapshot["state"]["skills"])
    if not isinstance(context["fingerprints"], dict) or set(context["fingerprints"]) != ids:
        raise ValidationError("观测context名单不一致")
    for fingerprint in context["fingerprints"].values():
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ValidationError("观测context指纹无效")
    members = context["node_members"]
    if not isinstance(members, dict) or not members:
        raise ValidationError("观测context缺少节点")
    counts = {skill: 0 for skill in ids}
    for node, skills in members.items():
        nonempty(node, "node_id")
        if not isinstance(skills, list) or not skills or not all(isinstance(skill, str) for skill in skills) or len(set(skills)) != len(skills) or not set(skills) <= ids:
            raise ValidationError("观测context节点成员无效")
        for skill in skills:
            counts[skill] += 1
    if any(not 1 <= count <= 2 for count in counts.values()):
        raise ValidationError("观测context必须覆盖全部成员且最多双挂")
    corpus_id = digest({key: context[key] for key in ("model", "dimension", "fingerprints")})
    if context["corpus_id"] != corpus_id or context["layout_id"] != digest({key: value for key, value in context.items() if key != "layout_id"}):
        raise ValidationError("观测context指纹不一致")


def normalize_observation(raw, snapshot, persisted=False):
    required = {"event_id", "query", "query_vector", "model", "baseline_top1", "selected_nodes",
                "hits", "parameters", "ts", "sample_kind", "mode", "purpose", "global_fallback"}
    allowed = required | {"context", "query_id", "signature", "signature_version", "channel"}
    if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - allowed:
        raise ValidationError("观测缺少必填字段或包含未知字段")
    event_id = nonempty(raw["event_id"], "event_id")
    query = nonempty(raw["query"], "query")
    if raw["model"] != snapshot["manifest"]["model"]:
        raise ValidationError("查询向量模型不一致")
    channel = raw.get("channel", "embedding")
    if channel not in ("embedding", "signature"):
        raise ValidationError("未知检索通道")
    signature_only = channel == "signature"
    vector = None if signature_only and raw["query_vector"] is None else list(validate_vector(raw["query_vector"], snapshot["manifest"]["dimension"], event_id))
    context = raw.get("context")
    if context is None:
        if persisted:
            raise ValidationError("持久观测缺少历史context")
        context = context_for(snapshot)
    validate_context(context, snapshot)
    if not persisted and context["corpus_id"] != context_for(snapshot)["corpus_id"]:
        raise ValidationError("新观测的语料指纹已过期")
    nodes, ids = context["node_members"], context["fingerprints"]
    baseline = raw["baseline_top1"]
    if baseline not in ids and not (signature_only and vector is None and baseline is None):
        raise ValidationError("baseline_top1必须来自管理名单")
    if vector is None and (raw["purpose"] != "consumption" or baseline is not None):
        raise ValidationError("无向量签名记录只能为消费事实，不能冒充影子评估")
    selected = raw["selected_nodes"]
    if not isinstance(selected, list) or not all(isinstance(node, str) for node in selected) or len(set(selected)) != len(selected) or not set(selected) <= set(nodes):
        raise ValidationError("selected_nodes含重复或未知节点")
    parameters = raw["parameters"]
    if not isinstance(parameters, dict) or set(parameters) != {"k", "tau", "m"}:
        raise ValidationError("parameters必须包含k/tau/m")
    if type(parameters["k"]) is not int or parameters["k"] != len(nodes) or type(parameters["m"]) is not int or not 1 <= parameters["m"] <= len(nodes):
        raise ValidationError("k/m与历史节点规模不一致")
    tau = parameters["tau"]
    if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not math.isfinite(tau) or not -1 <= tau <= 1:
        raise ValidationError("tau必须为[-1,1]的有限数")
    if type(raw["global_fallback"]) is not bool or len(selected) < parameters["m"]:
        raise ValidationError("节点束小于m或global_fallback无效")
    if raw["global_fallback"] and set(selected) != set(nodes):
        raise ValidationError("全局兜底必须记录全部被搜索节点")
    for field, choices in (("sample_kind", ("real", "synthetic", "fixture")),
                           ("mode", ("regular", "exploration")), ("purpose", ("evaluation", "consumption"))):
        if raw[field] not in choices:
            raise ValidationError(f"{field}无效")
    if not isinstance(raw["hits"], list):
        raise ValidationError("hits必须为列表")
    hits, seen = [], set()
    for rank, hit in enumerate(raw["hits"], 1):
        if not isinstance(hit, dict) or set(hit) != {"skill_id", "score", "rank", "node_id"}:
            raise ValidationError("hit字段无效")
        skill, node, score = hit["skill_id"], hit["node_id"], hit["score"]
        nonempty(skill, "hit.skill_id")
        nonempty(node, "hit.node_id")
        if skill in seen or node not in selected or skill not in nodes[node]:
            raise ValidationError("hit重复或不属于被搜索节点")
        if type(hit["rank"]) is not int or hit["rank"] != rank:
            raise ValidationError("hit排名必须从1连续递增")
        if not (signature_only and score is None) and (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not -1 <= score <= 1):
            raise ValidationError("hit分数无效")
        seen.add(skill)
        hits.append(dict(hit))
    query_id = digest({"query": query, "query_vector": vector})
    if "query_id" in raw and raw["query_id"] != query_id:
        raise ValidationError("query_id与输入不一致")
    if "signature" in raw:
        signature = raw["signature"]
        if not isinstance(signature, dict) or set(signature) != {"status", "top1", "candidates"} or signature["status"] not in ("unique", "ambiguous", "miss"):
            raise ValidationError("签名观测格式无效")
        if not isinstance(signature["candidates"], list):
            raise ValidationError("签名候选必须为列表")
        seen_signatures = set()
        for candidate in signature["candidates"]:
            if not isinstance(candidate, dict) or set(candidate) != {"skill_id", "matches"}:
                raise ValidationError("签名候选格式无效")
            key = nonempty(candidate["skill_id"], "signature.skill_id")
            if key not in ids or key in seen_signatures or not isinstance(candidate["matches"], list) or not candidate["matches"] or not all(isinstance(s, str) and s and s in query.casefold() for s in candidate["matches"]):
                raise ValidationError("签名候选引用或匹配证据无效")
            seen_signatures.add(key)
        if (signature["status"] == "unique" and signature["top1"] not in seen_signatures) or (signature["status"] != "unique" and signature["top1"] is not None) or (signature["status"] == "miss") != (not seen_signatures):
            raise ValidationError("签名状态与候选不一致")
        if not persisted and "signature_management" in snapshot["state"]:
            from signatures import SignatureMatcher, signature_version
            current_version = signature_version(snapshot)
            if raw.get("signature_version", current_version) != current_version or signature != SignatureMatcher(snapshot["state"]["skills"]).scan(query):
                raise ValidationError("签名观测与当前签名版本或实际字面匹配不一致")
            raw = dict(raw, signature_version=current_version)
    if "signature_version" in raw:
        if "signature" not in raw or not isinstance(raw["signature_version"], str) or len(raw["signature_version"]) != 64:
            raise ValidationError("signature_version必须与签名观测配套")
    if signature_only:
        if raw["purpose"] != "consumption":
            raise ValidationError("签名通道记录只能为消费事实")
        if "signature" not in raw or "signature_version" not in raw or raw["signature"]["status"] != "unique" or len(hits) != 1 or hits[0]["skill_id"] != raw["signature"]["top1"] or hits[0]["score"] is not None:
            raise ValidationError("签名消费必须绑定唯一实际命中，且余弦分数为null")
        if not persisted:
            policy = snapshot["state"].get("channel_policy", {})
            if policy.get("simulation", True) or policy.get("modes", {}).get(hits[0]["skill_id"]) != "signature_first":
                raise ValidationError("签名消费需要正式晋级策略")
    return dict(raw, event_id=event_id, query=query, query_vector=vector, query_id=query_id,
                selected_nodes=sorted(selected), hits=hits, context=context, ts=timestamp(raw["ts"]))


def evaluate(events):
    """按语料、历史布局、样本类型、探索模式和参数分别统计。"""
    grouped = defaultdict(list)
    for event in events:
        if event["query_vector"] is None or event.get("channel") == "signature":
            continue
        key = (event["context"]["corpus_id"], event["context"]["layout_id"], event["sample_kind"],
               event["mode"], event["purpose"], event["parameters"]["k"], event["parameters"]["tau"], event["parameters"]["m"])
        grouped[key].append(event)
    reports = []
    for key, rows in sorted(grouped.items()):
        misses, coverage, candidates, hit_rates, fallback_rates = [], [], [], [], []
        skill_queries = defaultdict(lambda: defaultdict(list))
        unique = defaultdict(list)
        for event in rows:
            unique[event["query_id"]].append(event)
        for repetitions in unique.values():
            node_counts, candidate_counts, hits, fallbacks = [], [], [], []
            for event in repetitions:
                members = event["context"]["node_members"]
                searched = {skill for node in event["selected_nodes"] for skill in members[node]}
                node_counts.append(len(event["selected_nodes"]))
                candidate_counts.append(len(searched))
                fallbacks.append(event["global_fallback"])
                covered = event["baseline_top1"] in searched
                skill_queries[event["baseline_top1"]][event["query_id"]].append(covered)
                hits.append(covered)
                if not covered:
                    misses.append({"event_id": event["event_id"], "query_id": event["query_id"], "skill_id": event["baseline_top1"]})
            coverage.append(sum(node_counts)/len(repetitions))
            candidates.append(sum(candidate_counts)/len(repetitions))
            hit_rates.append(sum(hits)/len(repetitions))
            fallback_rates.append(sum(fallbacks)/len(repetitions))
        count = len(unique)
        per_skill = {}
        for skill_id in rows[0]["context"]["fingerprints"]:
            samples = skill_queries.get(skill_id, {})
            per_skill[skill_id] = {"baseline_queries": len(samples),
                "route_recall": sum(sum(values)/len(values) for values in samples.values())/len(samples) if samples else None}
        reports.append(dict(zip(("corpus_id", "layout_id", "sample_kind", "mode", "purpose", "k", "tau", "m"), key),
            observations=len(rows), queries=count, route_hit_rate=sum(hit_rates)/count,
            avg_search_nodes=sum(coverage)/count, avg_candidates=sum(candidates)/count,
            fallback_rate=sum(fallback_rates)/count, misses=misses, query_ids=sorted(unique), per_skill=per_skill,
            baseline_id=digest({query: sorted({event["baseline_top1"] for event in repetitions}) for query, repetitions in unique.items()})))
    return {"status": "EVALUATED" if reports else "NOT_EVALUATED", "groups": reports}


def calibrate(events, target_recall):
    report = evaluate(events)
    groups = report["groups"]
    # 不同布局可比较，但必须同语料、同查询集合、同类型/用途/探索模式。
    cohorts = defaultdict(list)
    for row in groups:
        key = (row["corpus_id"], row["sample_kind"], row["mode"], row["purpose"], tuple(row["query_ids"]), row["baseline_id"])
        cohorts[key].append(row)
    results = []
    for rows in cohorts.values():
        frontier = []
        for row in rows:
            if not any(other["route_hit_rate"] >= row["route_hit_rate"] and
                       other["avg_candidates"] <= row["avg_candidates"] and
                       other["avg_search_nodes"] <= row["avg_search_nodes"] and
                       (other["route_hit_rate"] > row["route_hit_rate"] or other["avg_candidates"] < row["avg_candidates"] or other["avg_search_nodes"] < row["avg_search_nodes"])
                       for other in rows):
                frontier.append(row)
        eligible = [row for row in frontier if row["route_hit_rate"] >= target_recall]
        chosen = min(eligible, key=lambda row: (row["avg_candidates"], row["avg_search_nodes"], row["k"], row["m"], row["tau"], row["layout_id"])) if eligible else None
        results.append({"corpus_id": rows[0]["corpus_id"], "sample_kind": rows[0]["sample_kind"],
            "mode": rows[0]["mode"], "purpose": rows[0]["purpose"], "queries": rows[0]["queries"],
            "frontier": frontier, "recommended": chosen, "target_met": chosen is not None})
    return {"status": "EVALUATED" if groups else "NOT_EVALUATED", "target_recall": target_recall,
            "scope": "observed_parameter_cells_only", "cohorts": results}
