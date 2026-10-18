"""双通道影子对比；字面通道独立排序，不借用向量分数。"""

from collections import deque
from models import ValidationError
from shadow import digest


def signature_version(snapshot):
    return digest({"model": snapshot["manifest"]["model"], "dimension": snapshot["manifest"]["dimension"],
        "skills": {key: {"description_sha256": skill["description_sha256"],
                         "triggers": sorted(set(t.casefold() for t in skill["triggers"]))}
                   for key, skill in sorted(snapshot["state"]["skills"].items())}})


def build_signature_index(snapshot):
    patterns = {}
    for skill_id, skill in sorted(snapshot["state"]["skills"].items()):
        for trigger in sorted(set(t.casefold() for t in skill["triggers"])):
            patterns.setdefault(trigger, []).append(skill_id)
    return {"version": 1, "signature_version": signature_version(snapshot), "patterns": patterns}


class SignatureMatcher:
    def __init__(self, skills):
        self.goto, self.fail, self.output = [{}], [0], [set()]
        for skill_id, skill in sorted(skills.items()):
            for trigger in skill["triggers"]:
                pattern = trigger.casefold()
                if not pattern:
                    continue
                state = 0
                for character in pattern:
                    if character not in self.goto[state]:
                        self.goto[state][character] = len(self.goto)
                        self.goto.append({})
                        self.fail.append(0)
                        self.output.append(set())
                    state = self.goto[state][character]
                self.output[state].add((skill_id, pattern))
        queue = deque(self.goto[0].values())
        while queue:
            state = queue.popleft()
            for character, child in self.goto[state].items():
                queue.append(child)
                fallback = self.fail[state]
                while fallback and character not in self.goto[fallback]:
                    fallback = self.fail[fallback]
                self.fail[child] = self.goto[fallback].get(character, 0)
                self.output[child].update(self.output[self.fail[child]])

    def scan(self, query):
        state, matched = 0, {}
        for character in query.casefold():
            while state and character not in self.goto[state]:
                state = self.fail[state]
            state = self.goto[state].get(character, 0)
            for skill_id, pattern in self.output[state]:
                matched.setdefault(skill_id, set()).add(pattern)
        strength = lambda key: (len(matched[key]), sum(map(len, matched[key])))
        ordered = sorted(matched, key=lambda key: (-strength(key)[0], -strength(key)[1], key))
        unique = bool(ordered) and (len(ordered) == 1 or strength(ordered[0]) > strength(ordered[1]))
        return {"status": "unique" if unique else ("ambiguous" if ordered else "miss"),
                "top1": ordered[0] if unique else None,
                "candidates": [{"skill_id": key, "matches": sorted(matched[key])} for key in ordered]}


def compare_channels(events, min_samples=20, agreement_threshold=.95, version=None, window_size=None):
    # 相同query重跑不增加独立证据；测试样本绝不成为生产晋级证据。
    unique = {}
    for event in events:
        if event.get("baseline_top1") is not None and "signature" in event and (version is None or event.get("signature_version") == version):
            key = (event["sample_kind"], event["query_id"])
            previous = unique.get(key)
            # 同一查询若曾有分歧，重复成功测量不能把它洗成一致。
            if previous and previous["signature"]["top1"] != previous["baseline_top1"]:
                continue
            unique[key] = event
    if window_size is not None:
        # 分开截取真实和模拟证据，避免合成流量挤掉真实窗口。
        selected = {}
        strata = {(key[0], event["signature"]["top1"]) for key, event in unique.items()}
        for kind, skill_id in sorted(strata, key=lambda item: (item[0], item[1] or "")):
            rows = [(key, event) for key, event in unique.items() if key[0] == kind and event["signature"]["top1"] == skill_id]
            selected.update(rows[-window_size:])
        unique = selected
    by_skill, totals = {}, {"queries": len(unique), "signature_miss": 0, "ambiguous": 0,
                          "unique": 0, "top1_agree": 0, "semantic_top1_in_signature_candidates": 0}
    disagreements = []
    for event in unique.values():
        signature = event["signature"]
        baseline = event["baseline_top1"]
        totals[{"miss": "signature_miss", "ambiguous": "ambiguous", "unique": "unique"}[signature["status"]]] += 1
        candidates = {hit["skill_id"] for hit in signature["candidates"]}
        totals["semantic_top1_in_signature_candidates"] += baseline in candidates
        agreed = signature["top1"] == baseline
        totals["top1_agree"] += agreed
        if not agreed:
            disagreements.append({"event_id": event["event_id"], "query": event["query"],
                "signature_status": signature["status"], "signature_top1": signature["top1"], "embedding_top1": baseline})
        if signature["status"] == "unique":
            key = signature["top1"]
            stats = by_skill.setdefault(key, {"comparisons": 0, "agreements": 0, "real_comparisons": 0, "real_agreements": 0,
                                             "event_ids": [], "real_event_ids": []})
            stats["comparisons"] += 1
            stats["agreements"] += agreed
            stats["event_ids"].append(event["event_id"])
            if event["sample_kind"] == "real":
                stats["real_comparisons"] += 1
                stats["real_agreements"] += agreed
                stats["real_event_ids"].append(event["event_id"])
    for stats in by_skill.values():
        stats["agreement_rate"] = stats["agreements"] / stats["comparisons"]
        stats["eligible_for_signature_first"] = (stats["real_comparisons"] >= min_samples and
            stats["real_agreements"] / stats["real_comparisons"] >= agreement_threshold)
    return {"totals": totals, "by_skill": by_skill, "disagreements": disagreements,
            "policy": {"min_real_unique_queries": min_samples, "agreement_threshold": agreement_threshold,
                       "signature_miss_or_ambiguity": "embedding_fallback", "applied": False}}


def update_channel_policy(snapshot, allow_simulation=False, min_samples=20, agreement_threshold=.95,
                          rollback_threshold=None, window_size=None):
    """按skill保存实际通道状态；测试证据不伪装成real。"""
    if type(min_samples) is not int or min_samples < 1 or not 0 < agreement_threshold <= 1:
        raise ValidationError("通道切换门槛无效")
    rollback_threshold = agreement_threshold if rollback_threshold is None else rollback_threshold
    if not 0 < rollback_threshold <= agreement_threshold or (window_size is not None and (type(window_size) is not int or window_size < min_samples)):
        raise ValidationError("回滚阈值或观测窗口无效")
    previous = snapshot["state"].get("channel_policy", {})
    if previous and previous["simulation"] != allow_simulation:
        raise ValidationError("模拟策略与正式策略不能混用")
    version = signature_version(snapshot) if "signature_management" in snapshot["state"] else None
    report = compare_channels(snapshot.get("observations", []), min_samples, agreement_threshold, version, window_size)
    modes, evidence = {}, {}
    history = list(previous.get("history", []))
    for skill_id in snapshot["state"]["skills"]:
        stats = report["by_skill"].get(skill_id, {})
        count = stats.get("comparisons" if allow_simulation else "real_comparisons", 0)
        agree = stats.get("agreements" if allow_simulation else "real_agreements", 0)
        old = previous.get("modes", {}).get(skill_id, "shadow")
        threshold = rollback_threshold if old == "signature_first" else agreement_threshold
        mode = "signature_first" if count >= min_samples and agree / count >= threshold else "shadow"
        modes[skill_id] = mode
        evidence[skill_id] = {"comparisons": count, "agreements": agree,
                              "event_ids": stats.get("event_ids" if allow_simulation else "real_event_ids", [])}
        if mode != old:
            history.append({"skill_id": skill_id, "before": old, "after": mode,
                            "comparisons": count, "agreements": agree, "signature_version": version})
            history[-1]["event_ids"] = list(evidence[skill_id]["event_ids"])
    snapshot["state"]["channel_policy"] = {"version": 1, "simulation": allow_simulation,
        "min_samples": min_samples, "agreement_threshold": agreement_threshold,
        "rollback_threshold": rollback_threshold, "window_size": window_size, "signature_version": version,
        "modes": modes, "evidence": evidence, "history": history}
    return snapshot["state"]["channel_policy"]


def validate_channel_policy(snapshot):
    policy = snapshot["state"].get("channel_policy")
    if policy is None:
        return
    if policy["version"] != 1 or type(policy["simulation"]) is not bool or set(policy["modes"]) != set(snapshot["state"]["skills"]):
        raise ValidationError("通道策略格式或名单无效")
    if any(mode not in ("shadow", "signature_first") for mode in policy["modes"].values()):
        raise ValidationError("未知通道状态")
    version = policy.get("signature_version")
    if version is not None and version != signature_version(snapshot):
        raise ValidationError("通道策略引用过期签名版本")
    for skill_id, mode in policy["modes"].items():
        evidence = policy["evidence"][skill_id]
        count, agree = evidence["comparisons"], evidence["agreements"]
        if type(count) is not int or type(agree) is not int or not 0 <= agree <= count:
            raise ValidationError("通道策略证据计数无效")
        if mode == "signature_first" and (count < policy["min_samples"] or agree/count < policy.get("rollback_threshold", policy["agreement_threshold"])):
            raise ValidationError("签名优先缺少足量一致性证据")


def resolve_with_policy(snapshot, query, embedding_callback, allow_simulation=False):
    """实际分流：已晋级且唯一命中时，不调用embedding_callback。"""
    validate_channel_policy(snapshot)
    signature = SignatureMatcher(snapshot["state"]["skills"]).scan(query)
    policy = snapshot["state"].get("channel_policy", {})
    enabled = bool(policy) and (not policy["simulation"] or allow_simulation)
    skill_id = signature["top1"]
    if enabled and skill_id is not None and policy["modes"].get(skill_id) == "signature_first":
        return {"channel": "signature", "skill_id": skill_id}
    skill_id = embedding_callback(query)
    if skill_id not in snapshot["state"]["skills"]:
        raise ValidationError("embedding回调返回名单外skill")
    return {"channel": "embedding", "skill_id": skill_id}
