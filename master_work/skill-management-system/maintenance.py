"""基于真实查询位置和效用的归属建议；演练样本必须显式放行。"""

from clustering import dot
from models import ValidationError
from nodes import NodeManager
from shadow import context_for
from shadow import digest
import copy
import math
from datetime import datetime, timezone


def _time(value):
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError("timezone required")
        return result
    except (ValueError, TypeError) as exc:
        raise ValidationError("维护时间必须为带时区的ISO时间") from exc


def initialize_maintenance(snapshot, options):
    validate_maintenance_options(options)
    if "clustering" not in snapshot["state"] or "feedback" not in snapshot["state"]:
        raise ValidationError("维护需要已初始化的节点和反馈状态")
    state = snapshot["state"].setdefault("maintenance", {"version": 1, "sequence": 0,
        "last_window_at": None, "last_changes": {}, "last_node_split": {}})
    state["options"] = dict(options)
    snapshot.setdefault("maintenance_queue", {"version": 1, "plans": {}, "content_reviews": {}, "reviews": []})
    snapshot.setdefault("maintenance_log", [])


def validate_maintenance_options(options):
    if not isinstance(options, dict):
        raise ValidationError("维护配置必须为对象")
    for key in ("min_feedback_samples", "max_moves_per_window", "max_splits_per_window", "min_new_feedback", "route_window_queries"):
        if type(options.get(key)) is not int or options[key] < 1:
            raise ValidationError(f"无效维护配置: {key}")
    for key in ("cooldown_windows", "min_window_seconds"):
        if type(options.get(key)) is not int or options[key] < 0:
            raise ValidationError(f"无效维护配置: {key}")
    for key in ("good_wilson_lower", "low_usability", "relative_margin", "move_margin", "dual_min_similarity", "dual_max_gap", "orphan_similarity", "route_drop", "route_recall_target"):
        value = options.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValidationError(f"无效维护配置: {key}")
    if options["orphan_similarity"] >= options["dual_min_similarity"] or options["low_usability"] >= options["good_wilson_lower"] or options["route_drop"] <= 0:
        raise ValidationError("维护阈值顺序或质量下降阈值无效")


def maintenance_fingerprint(snapshot):
    return digest({"skills": snapshot["state"]["skills"], "vectors": snapshot["vectors"],
        "clustering": snapshot["state"]["clustering"], "feedback": snapshot["state"]["feedback"],
        "maintenance": snapshot["state"]["maintenance"],
        "content_reviews": snapshot["maintenance_queue"]["content_reviews"],
        "signature_index": snapshot.get("signature_index"), "review_queue": snapshot.get("review_queue")})


def _evidence(snapshot, cohort_id, skill_id, stats):
    cohort = snapshot["state"]["feedback"]["cohorts"][cohort_id]
    events = {e["event_id"]: e for e in snapshot.get("observations", [])}
    rating_ids = [r["rating_id"] for r in snapshot.get("ratings", []) if r["skill_id"] == skill_id and
                  events[r["event_id"]]["context"]["corpus_id"] == cohort["corpus_id"] and
                  events[r["event_id"]]["sample_kind"] == cohort["sample_kind"] and events[r["event_id"]]["mode"] == cohort["mode"]]
    baselines = []
    for node in cohort["node_rank"].values():
        own = node["skills"].get(skill_id)
        if own is not None:
            baselines.append({"layout_id": node["layout_id"], "node_id": node["node_id"], "rank": node["rank"],
                "rated": own["rated"], "peer_rated": node["rated"]-own["rated"],
                "relative_to_peers": own["relative_to_peers"]})
    return {"cohort_id": cohort_id, "R": stats["R"], "G": stats["G"], "B": stats["B"],
        "rated": stats["rated"], "query_count": stats["query_count"], "rating_ids": sorted(rating_ids),
        "wilson_lower": stats["wilson_lower"], "rank_baselines": baselines, "simulation": cohort["sample_kind"] != "real"}


def _membership_candidates(snapshot, allow_simulation):
    state, layout = snapshot["state"]["maintenance"], snapshot["state"]["clustering"]
    options, next_window = state["options"], state["sequence"] + 1
    corpus_id = context_for(snapshot)["corpus_id"]
    grouped, deferred = {}, []
    for cohort_id, cohort in sorted(snapshot["state"]["feedback"]["cohorts"].items()):
        if cohort["corpus_id"] != corpus_id or (cohort["sample_kind"] != "real" and not allow_simulation):
            continue
        for skill_id, stats in sorted(cohort["skills"].items()):
            if stats["rated"] < options["min_feedback_samples"]:
                continue
            evidence = _evidence(snapshot, cohort_id, skill_id, stats)
            relative_low = any(b["rated"] >= options["min_feedback_samples"] and b["peer_rated"] >= options["min_feedback_samples"] and
                               b["relative_to_peers"] is not None and b["relative_to_peers"] < -options["relative_margin"] for b in evidence["rank_baselines"])
            if stats["usability"] < options["low_usability"] or relative_low:
                evidence["review_reason"] = "low_relative_utility" if relative_low else "low_usability"
                grouped.setdefault(skill_id, []).append({"action": "content_review", "skill_id": skill_id, "evidence": evidence})
                continue
            if stats["query_count"] < options["min_feedback_samples"] or stats["query_centroid"] is None or stats["wilson_lower"] < options["good_wilson_lower"]:
                continue
            last = state["last_changes"].get(skill_id)
            if last:
                if next_window - last["window"] <= options["cooldown_windows"]:
                    deferred.append({"skill_id": skill_id, "reason": "cooldown"})
                    continue
                if len(set(evidence["rating_ids"]) - set(last["rating_ids"])) < options["min_new_feedback"]:
                    deferred.append({"skill_id": skill_id, "reason": "not_enough_new_feedback"})
                    continue
            scores = {node: dot(stats["query_centroid"], value["centroid"]) for node, value in layout["nodes"].items()}
            ordered = sorted(scores, key=lambda node: (-scores[node], node))
            best, old = ordered[0], list(layout["assignments"][skill_id])
            current = max(scores[node] for node in old)
            action, after = None, None
            if scores[best] < options["orphan_similarity"]:
                if len(old) == 1 and layout["nodes"][old[0]]["count"] == 1:
                    continue
                action, after = "isolate", ["isolated-" + digest(skill_id)[:16]]
            elif len(ordered) > 1 and scores[ordered[1]] >= options["dual_min_similarity"] and scores[best] - scores[ordered[1]] <= options["dual_max_gap"]:
                after = ordered[:2]
                if set(after) != set(old):
                    action = "attach"
            elif (best not in old and scores[best] - current >= options["move_margin"]) or (best in old and len(old) == 2 and scores[best] - min(scores[n] for n in old) >= options["move_margin"]):
                action, after = "move", [best]
            if action:
                grouped.setdefault(skill_id, []).append({"action": action, "skill_id": skill_id, "before": old,
                    "after": after, "gain": scores[best] - current, "evidence": evidence})
    selected = []
    for skill_id, candidates in grouped.items():
        content = [candidate for candidate in candidates if candidate["action"] == "content_review"]
        if content:
            selected.append(max(content, key=lambda c: (c["evidence"]["rated"], c["evidence"]["cohort_id"])))
            continue
        destinations = {tuple(sorted(c["after"])) for c in candidates}
        if len(destinations) > 1:
            deferred.append({"skill_id": skill_id, "reason": "conflicting_cohort_destinations"})
        else:
            selected.append(max(candidates, key=lambda c: (c["evidence"]["rated"], c["evidence"]["cohort_id"])))
    return sorted(selected, key=lambda c: (c["action"] != "content_review", -c["evidence"]["rated"], c["skill_id"])), deferred


def _quality_splits(snapshot, allow_simulation):
    options = snapshot["state"]["maintenance"]["options"]
    context = context_for(snapshot)
    groups = {}
    for event in snapshot.get("observations", []):
        if event["context"]["layout_id"] != context["layout_id"] or event["purpose"] != "evaluation" or event["mode"] != "regular" or (event["sample_kind"] != "real" and not allow_simulation):
            continue
        p = event["parameters"]
        key = (event["sample_kind"], p["k"], p["tau"], p["m"])
        groups.setdefault(key, {}).setdefault(event["query_id"], event)
    result = {}
    count = options["route_window_queries"]
    def covered(event):
        return any(event["baseline_top1"] in context["node_members"][n] for n in event["selected_nodes"])
    for events in groups.values():
        rows = list(events.values())
        if len(rows) < 2*count:
            continue
        previous, recent = rows[-2*count:-count], rows[-count:]
        before, after = sum(map(covered, previous))/count, sum(map(covered, recent))/count
        if before-after+1e-12 < options["route_drop"] or after >= options["route_recall_target"]:
            continue
        for event in recent:
            if not covered(event):
                for node, members in context["node_members"].items():
                    if event["baseline_top1"] in members:
                        result[node] = {"reason": "route_quality_drop", "previous_recall": before, "recent_recall": after,
                                        "event_ids": [e["event_id"] for e in previous+recent]}
    return result


def _execute_membership(snapshot, action):
    layout = snapshot["state"]["clustering"]
    if layout["assignments"].get(action["skill_id"]) != action["before"]:
        raise ValidationError("维护动作的旧归属不一致")
    manager = NodeManager(layout, {key: value["vector"] for key, value in snapshot["vectors"]["entries"].items()})
    if action["action"] == "isolate":
        manager.isolate(action["skill_id"], action["after"][0])
    else:
        manager.assign(action["skill_id"], action["after"])
    manager.layout["changes"][-1]["feedback_evidence"] = action["evidence"]
    snapshot["state"]["clustering"] = manager.layout


def create_maintenance_plan(snapshot, now=None, allow_simulation=False):
    now = now or datetime.now(timezone.utc).isoformat()
    _time(now)
    state, queue = snapshot["state"]["maintenance"], snapshot["maintenance_queue"]
    options = state["options"]
    fingerprint = maintenance_fingerprint(snapshot)
    for existing in queue["plans"].values():
        if existing["input_fingerprint"] == fingerprint and existing["simulation"] == allow_simulation:
            return existing
    candidates, deferred = _membership_candidates(snapshot, allow_simulation)
    projected, actions, moves = copy.deepcopy(snapshot), [], 0
    for action in candidates:
        if action["action"] == "content_review":
            key = digest([action["skill_id"], snapshot["state"]["skills"][action["skill_id"]]["description_sha256"]])
            action["case_id"] = key
            old = queue["content_reviews"].get(key)
            if old and len(set(action["evidence"]["rating_ids"]) - set(old["evidence"]["rating_ids"])) < options["min_new_feedback"]:
                continue
            actions.append(action)
            continue
        if moves >= options["max_moves_per_window"]:
            deferred.append({"skill_id": action["skill_id"], "reason": "window_move_limit"})
            continue
        try:
            _execute_membership(projected, action)
        except ValidationError as exc:
            deferred.append({"skill_id": action["skill_id"], "reason": str(exc)})
            continue
        actions.append(action)
        moves += 1
    layout = projected["state"]["clustering"]
    manager = NodeManager(layout, {key: value["vector"] for key, value in projected["vectors"]["entries"].items()})
    triggers = _quality_splits(snapshot, allow_simulation)
    for node in manager.oversized(layout["target_size"]):
        triggers[node] = {"reason": "size_limit", "count": layout["nodes"][node]["count"], "target_size": layout["target_size"]}
    splits = 0
    for node, evidence in sorted(triggers.items()):
        if node not in manager.layout["nodes"] or manager.layout["nodes"][node]["count"] < 2:
            continue
        if splits >= options["max_splits_per_window"]:
            deferred.append({"node_id": node, "reason": "window_split_limit"})
            continue
        last = state["last_node_split"].get(node)
        if last is not None and state["sequence"]+1-last <= options["cooldown_windows"]:
            deferred.append({"node_id": node, "reason": "split_cooldown"})
            continue
        before = list(manager.layout["nodes"][node]["members"])
        try:
            manager.split(node, seed=layout.get("config", {}).get("seed", 42),
                          max_iterations=layout.get("config", {}).get("max_iterations", 50), reason=evidence["reason"])
        except ValidationError as exc:
            deferred.append({"node_id": node, "reason": str(exc)})
            continue
        actions.append({"action": "split", "node_id": node, "before_members": before, "evidence": evidence,
                        "after_members": manager.layout["changes"][-1]["after_members"]})
        splits += 1
    plan_id = digest([fingerprint, allow_simulation, digest(actions)])
    plan = {"plan_id": plan_id, "input_fingerprint": fingerprint, "created_at": now,
            "sequence": state["sequence"]+1, "simulation": allow_simulation,
            "actions": actions, "deferred": deferred, "status": "pending", "result": None}
    queue["plans"][plan_id] = plan
    return plan


def apply_maintenance_plan(snapshot, plan_id, now=None, allow_simulation=False):
    """全部动作先在深副本成功，再返回可发布的新状态。"""
    now = now or datetime.now(timezone.utc).isoformat()
    instant = _time(now)
    plan = snapshot["maintenance_queue"]["plans"].get(plan_id)
    if plan is None:
        raise ValidationError("维护计划不存在")
    if plan["status"] == "applied":
        return copy.deepcopy(snapshot), False
    if plan["simulation"] and not allow_simulation:
        raise ValidationError("模拟维护计划不能在正式执行入口生效")
    if plan["input_fingerprint"] != maintenance_fingerprint(snapshot):
        raise ValidationError("维护计划已过期，请基于当前数据重新规划")
    state = snapshot["state"]["maintenance"]
    options = state["options"]
    if plan["sequence"] != state["sequence"]+1 or sum(a["action"] in ("move", "attach", "isolate") for a in plan["actions"]) > options["max_moves_per_window"] or sum(a["action"] == "split" for a in plan["actions"]) > options["max_splits_per_window"]:
        raise ValidationError("维护计划超过窗口限额或序号不一致")
    if instant < _time(plan["created_at"]):
        raise ValidationError("执行时间不能早于计划创建时间")
    if state["last_window_at"] is not None and (instant-_time(state["last_window_at"])).total_seconds() < options["min_window_seconds"]:
        raise ValidationError("尚未到下一个维护窗口")
    changed = copy.deepcopy(snapshot)
    state = changed["state"]["maintenance"]
    before_layout = digest(changed["state"]["clustering"])
    sequence = state["sequence"]+1
    for action in plan["actions"]:
        kind = action["action"]
        if kind == "content_review":
            key = action["case_id"]
            old = changed["maintenance_queue"]["content_reviews"].get(key)
            changed["maintenance_queue"]["content_reviews"][key] = {"case_id": key, "skill_id": action["skill_id"],
                "description_sha256": changed["state"]["skills"][action["skill_id"]]["description_sha256"],
                "status": "open", "evidence": action["evidence"], "opened_window": old["opened_window"] if old else sequence,
                "updated_window": sequence, "review": None}
        elif kind == "split":
            manager = NodeManager(changed["state"]["clustering"], {key: value["vector"] for key, value in changed["vectors"]["entries"].items()})
            if manager.layout["nodes"].get(action["node_id"], {}).get("members") != action["before_members"]:
                raise ValidationError("局部拆分前成员已改变")
            options_for_split = changed["state"]["clustering"].get("config", {})
            manager.split(action["node_id"], seed=options_for_split.get("seed", 42),
                          max_iterations=options_for_split.get("max_iterations", 50), reason=action["evidence"]["reason"])
            if manager.layout["changes"][-1]["after_members"] != action["after_members"]:
                raise ValidationError("局部拆分结果与计划不一致")
            changed["state"]["clustering"] = manager.layout
            for node in manager.layout["changes"][-1]["children"]:
                state["last_node_split"][node] = sequence
            for skill_id in action["before_members"]:
                state["last_changes"][skill_id] = {"window": sequence,
                    "rating_ids": sorted(r["rating_id"] for r in changed.get("ratings", []) if r["skill_id"] == skill_id)}
        else:
            _execute_membership(changed, action)
            state["last_changes"][action["skill_id"]] = {"window": sequence, "rating_ids": action["evidence"]["rating_ids"]}
    state["sequence"], state["last_window_at"] = sequence, now
    result = {"window": sequence, "applied_at": now, "actions": len(plan["actions"]),
              "membership_changes": sum(a["action"] in ("move", "attach", "isolate") for a in plan["actions"]),
              "splits": sum(a["action"] == "split" for a in plan["actions"]),
              "content_reviews": sum(a["action"] == "content_review" for a in plan["actions"])}
    completed = changed["maintenance_queue"]["plans"][plan_id]
    completed["status"], completed["result"] = "applied", result
    changed["maintenance_log"].append({"window": sequence, "plan_id": plan_id, "ts": now,
        "simulation": plan["simulation"], "before_layout": before_layout,
        "after_layout": digest(changed["state"]["clustering"]), "options": dict(options), "actions": copy.deepcopy(plan["actions"])})
    return changed, True


def review_content(snapshot, case_id, decision, reviewer, reason):
    if decision not in ("resolved", "dismissed") or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValidationError("内容审核需要resolved/dismissed、审核者和理由")
    queue = snapshot["maintenance_queue"]
    case = queue["content_reviews"].get(case_id)
    if case is None:
        raise ValidationError("内容修订项不存在")
    if case["status"] != "open":
        if case["status"] == decision and case["review"]["reviewer"] == reviewer and case["review"]["reason"] == reason:
            return False
        raise ValidationError("已关闭的内容修订项不能改写决定")
    review = {"case_id": case_id, "decision": decision, "reviewer": reviewer, "reason": reason,
              "ts": datetime.now(timezone.utc).isoformat()}
    case["status"], case["review"] = decision, review
    queue["reviews"].append(review)
    return True


def validate_maintenance(snapshot):
    state = snapshot["state"].get("maintenance")
    if state is None:
        if "maintenance_queue" in snapshot or "maintenance_log" in snapshot:
            raise ValidationError("维护产物缺少维护状态")
        return
    queue, log = snapshot["maintenance_queue"], snapshot["maintenance_log"]
    validate_maintenance_options(state["options"])
    ratings = {r["rating_id"]: r for r in snapshot.get("ratings", [])}
    if state["version"] != 1 or queue["version"] != 1 or type(state["sequence"]) is not int or state["sequence"] != len(log):
        raise ValidationError("维护序号与日志不一致")
    if state["last_window_at"] != (log[-1]["ts"] if log else None):
        raise ValidationError("维护窗口时间与日志不一致")
    for index, record in enumerate(log, 1):
        plan = queue["plans"].get(record["plan_id"])
        if record["window"] != index or plan is None or plan["status"] != "applied" or plan["result"]["window"] != index or plan["actions"] != record["actions"] or record["simulation"] != plan["simulation"]:
            raise ValidationError("维护日志与已执行计划不一致")
        limits = record["options"]
        validate_maintenance_options(limits)
        moves = sum(a["action"] in ("move", "attach", "isolate") for a in record["actions"])
        splits = sum(a["action"] == "split" for a in record["actions"])
        reviews = sum(a["action"] == "content_review" for a in record["actions"])
        if moves > limits["max_moves_per_window"] or splits > limits["max_splits_per_window"]:
            raise ValidationError("历史维护窗口超过当时限额")
        if plan["result"] != {"window": index, "applied_at": record["ts"], "actions": len(record["actions"]),
                              "membership_changes": moves, "splits": splits, "content_reviews": reviews}:
            raise ValidationError("维护执行结果与动作不一致")
        _time(record["ts"])
    for key, plan in queue["plans"].items():
        if key != plan["plan_id"] or key != digest([plan["input_fingerprint"], plan["simulation"], digest(plan["actions"])]) or plan["status"] not in ("pending", "applied"):
            raise ValidationError("维护计划标识或状态无效")
        _time(plan["created_at"])
        if plan["status"] == "pending" and plan["result"] is not None:
            raise ValidationError("待执行计划不能有执行结果")
        if plan["status"] == "applied" and sum(record["plan_id"] == key for record in log) != 1:
            raise ValidationError("已执行计划缺少唯一窗口日志")
        for action in plan["actions"]:
            if action["action"] not in ("move", "attach", "isolate", "split", "content_review"):
                raise ValidationError("未知维护动作")
            if action["action"] != "split" and action["skill_id"] not in snapshot["state"]["skills"]:
                raise ValidationError("维护动作指向名单外skill")
            if action["action"] != "split":
                evidence = action["evidence"]
                refs = evidence["rating_ids"]
                if len(refs) != len(set(refs)) or len(refs) != evidence["G"]+evidence["B"] or any(key not in ratings or ratings[key]["skill_id"] != action["skill_id"] for key in refs):
                    raise ValidationError("维护反馈证据引用或计数不一致")
                if sum(ratings[key]["value"] == "good" for key in refs) != evidence["G"]:
                    raise ValidationError("维护反馈好差评与原始评分不一致")
    for skill_id, change in state["last_changes"].items():
        if skill_id not in snapshot["state"]["skills"] or not 1 <= change["window"] <= state["sequence"] or any(key not in ratings for key in change["rating_ids"]):
            raise ValidationError("成员冷却状态无效")
    for key, case in queue["content_reviews"].items():
        if case["skill_id"] not in snapshot["state"]["skills"] or key != case["case_id"] or key != digest([case["skill_id"], case["description_sha256"]]) or case["status"] not in ("open", "resolved", "dismissed"):
            raise ValidationError("内容修订项无效")
        if case["status"] == "open" and case["review"] is not None:
            raise ValidationError("打开的修订项不能有关闭决定")
        if case["status"] != "open" and (case["review"] not in queue["reviews"] or case["review"]["decision"] != case["status"]):
            raise ValidationError("内容修订项缺少对应审核记录")


def propose_membership(snapshot, cohort_id, allow_simulation=False, margin=.03):
    feedback = snapshot["state"]["feedback"]
    cohort = feedback["cohorts"][cohort_id]
    if cohort["sample_kind"] != "real" and not allow_simulation:
        return []
    if cohort["corpus_id"] != context_for(snapshot)["corpus_id"]:
        return []
    layout = snapshot["state"]["clustering"]
    result = []
    minimum = feedback["options"]["min_feedback_samples"]
    for skill_id, stats in cohort["skills"].items():
        if stats["rated"] < minimum:
            continue
        evidence = {"cohort_id": cohort_id, "R": stats["R"], "G": stats["G"], "B": stats["B"],
                    "simulation": cohort["sample_kind"] != "real"}
        if stats["usability"] < .5:
            result.append({"action": "content_review", "skill_id": skill_id, "evidence": evidence})
            continue
        query = stats["query_centroid"]
        if stats["usability"] < .8 or stats["query_count"] < minimum or query is None:
            continue
        scores = {key: dot(query, node["centroid"]) for key, node in layout["nodes"].items()}
        target = min(scores, key=lambda key: (-scores[key], key))
        old = layout["assignments"][skill_id]
        current = max(scores[name] for name in old)
        if target not in old and scores[target] - current >= margin:
            result.append({"action": "move", "skill_id": skill_id, "before": list(old), "after": [target],
                "gain": scores[target] - current, "evidence": evidence})
    return result


def apply_membership(snapshot, proposal):
    if proposal["action"] != "move":
        raise ValidationError("内容修订建议不能用于节点移动")
    layout = snapshot["state"]["clustering"]
    if layout["assignments"].get(proposal["skill_id"]) != proposal["before"]:
        raise ValidationError("归属已改变，拒绝执行过期建议")
    manager = NodeManager(layout, {key: value["vector"] for key, value in snapshot["vectors"]["entries"].items()})
    manager.assign(proposal["skill_id"], proposal["after"])
    manager.layout["changes"][-1]["feedback_evidence"] = proposal["evidence"]
    snapshot["state"]["clustering"] = manager.layout
