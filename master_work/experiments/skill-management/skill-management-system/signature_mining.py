"""带原文证据的签名候选收割、人工审核及管理副本更新。"""

from datetime import datetime, timezone
import json
import re

from corpus import parse_skill
from models import ValidationError, text_hash
from shadow import context_for, digest
from signatures import build_signature_index, signature_version, update_channel_policy


def refresh_policy(snapshot):
    options = snapshot["state"]["signature_management"]["options"]
    return update_channel_policy(snapshot, min_samples=options["min_samples"],
        agreement_threshold=options["promotion_threshold"], rollback_threshold=options["rollback_threshold"],
        window_size=options["window_size"])


def initialize_signatures(snapshot, options):
    if "signature_management" not in snapshot["state"]:
        snapshot["state"]["signature_management"] = {"version": 1, "options": dict(options),
            "source_content_sha256": {key: s["content_sha256"] for key, s in snapshot["state"]["skills"].items()}}
        snapshot["review_queue"] = {"version": 1, "candidates": {}, "decisions": []}
    else:
        snapshot["state"]["signature_management"]["options"] = dict(options)
    snapshot["signature_index"] = build_signature_index(snapshot)
    refresh_policy(snapshot)


def extract_patterns(query, min_words, max_words):
    patterns = {}
    tokens = list(re.finditer(r"\w+(?:-\w+)*", query))
    for n in range(min_words, max_words + 1):
        for index in range(len(tokens) - n + 1):
            text = query[tokens[index].start():tokens[index+n-1].end()]
            if 8 <= len(text) <= 160:
                patterns.setdefault(text, set()).add("ngram")
    for expression in (r"\b[A-Z]{2,12}\d{2,10}\b", r"\berror code\s+\d+\b", r"\b0x[0-9a-fA-F]{8}\b", r"\bE[A-Z]{3,16}\b"):
        for match in re.finditer(expression, query):
            patterns.setdefault(match.group(), set()).add("machine_pattern")
    for match in re.finditer(r'''["']([^"'\r\n]{8,160})["']''', query):
        patterns.setdefault(match.group(1), set()).add("quoted_text")
    return patterns


def mine_candidates(snapshot, allow_simulation=False):
    management = snapshot["state"]["signature_management"]
    options, queue = management["options"], snapshot["review_queue"]
    corpus_id = context_for(snapshot)["corpus_id"]
    unique = {}
    for event in snapshot.get("observations", []):
        if event.get("baseline_top1") is not None and event["context"]["corpus_id"] == corpus_id and (event["sample_kind"] == "real" or allow_simulation):
            unique.setdefault((event["sample_kind"], event["query_id"]), event)
    groups = {}
    for event in unique.values():
        groups.setdefault(event["baseline_top1"], []).append(event)
    generated = []
    for skill_id, events in sorted(groups.items()):
        existing = {t.casefold() for t in snapshot["state"]["skills"][skill_id]["triggers"]}
        patterns = {}
        for event in events:
            for text, methods in extract_patterns(event["query"], options["min_ngram_words"], options["max_ngram_words"]).items():
                key = text.casefold()
                if key not in existing:
                    candidate = patterns.setdefault(key, {"text": text, "methods": set()})
                    candidate["methods"].update(methods)
        others = [event for event in unique.values() if event["baseline_top1"] != skill_id]
        for pattern in patterns.values():
            expression = re.compile(re.escape(pattern["text"]), re.IGNORECASE)
            evidence = []
            for event in events:
                match = expression.search(event["query"])
                if match:
                    evidence.append({"event_id": event["event_id"], "query_id": event["query_id"],
                        "sample_kind": event["sample_kind"], "span": [match.start(), match.end()], "quote": match.group()})
            other_count = sum(expression.search(event["query"]) is not None for event in others)
            fraction = other_count / len(others) if others else 0.0
            if len(evidence) < options["min_support"] or fraction > options["max_other_query_fraction"]:
                continue
            candidate_id = digest([skill_id, pattern["text"].casefold()])
            generated.append({"candidate_id": candidate_id, "skill_id": skill_id, "text": pattern["text"],
                "status": "pending", "signature_version": signature_version(snapshot),
                "methods": sorted(pattern["methods"]), "evidence": evidence,
                "other_query_count": other_count, "other_query_fraction": fraction, "review": None})
    generated.sort(key=lambda item: (-len(item["evidence"]), -len(item["text"]), item["candidate_id"]))
    added = updated = 0
    for candidate in generated[:options["max_candidates"]]:
        old = queue["candidates"].get(candidate["candidate_id"])
        if old is None:
            queue["candidates"][candidate["candidate_id"]] = candidate
            added += 1
        elif old["status"] == "pending" and old != candidate:
            queue["candidates"][candidate["candidate_id"]] = candidate
            updated += 1
    return {"eligible_queries": len(unique), "added": added, "updated": updated,
            "pending": sum(c["status"] == "pending" for c in queue["candidates"].values())}


def _append_trigger(content, text):
    lines = content.splitlines()
    closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    start = next(i for i in range(1, closing) if lines[i].startswith("triggers:"))
    end = start + 1
    while end < closing and (not lines[end].strip() or lines[end][0].isspace()):
        end += 1
    lines[start] = "triggers:"
    lines.insert(end, "  - " + json.dumps(text, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def review_candidate(snapshot, candidate_id, decision, reviewer, reason, allow_simulation=False):
    if decision not in ("approve", "reject") or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValidationError("审核需要approve/reject、审核者及非空理由")
    queue = snapshot["review_queue"]
    candidate = queue["candidates"].get(candidate_id)
    if candidate is None:
        raise ValidationError("候选不存在")
    status = "approved" if decision == "approve" else "rejected"
    if candidate["status"] != "pending":
        if candidate["status"] == status and candidate["review"]["reviewer"] == reviewer and candidate["review"]["reason"] == reason:
            return False
        raise ValidationError("已审核候选不能改写决定")
    if decision == "approve":
        if candidate["signature_version"] != signature_version(snapshot):
            raise ValidationError("候选基于过期签名版本，请重新收割后审核")
        if not allow_simulation and any(e["sample_kind"] != "real" for e in candidate["evidence"]):
            raise ValidationError("正式审核不能将模拟证据写入签名")
        skill = snapshot["state"]["skills"][candidate["skill_id"]]
        if candidate["text"].casefold() not in {t.casefold() for t in skill["triggers"]}:
            content = _append_trigger(skill["full_content"], candidate["text"])
            name, description, triggers, body = parse_skill(content)
            if (name, description, body) != (skill["name"], skill["description"], skill["body"]):
                raise ValidationError("签名更新不能改变名称、description或正文")
            skill.update(full_content=content, triggers=list(triggers), content_sha256=text_hash(content))
    review = {"decision": decision, "reviewer": reviewer, "reason": reason,
              "ts": datetime.now(timezone.utc).isoformat()}
    candidate["status"], candidate["review"] = status, review
    queue["decisions"].append({"candidate_id": candidate_id, **review})
    snapshot["signature_index"] = build_signature_index(snapshot)
    refresh_policy(snapshot)
    return True


def validate_signature_management(snapshot):
    management = snapshot["state"].get("signature_management")
    if management is None:
        if "review_queue" in snapshot or "signature_index" in snapshot:
            raise ValidationError("签名派生产物缺少管理状态")
        return
    ids = set(snapshot["state"]["skills"])
    if management["version"] != 1 or set(management["source_content_sha256"]) != ids:
        raise ValidationError("签名管理来源名单无效")
    if snapshot.get("signature_index") != build_signature_index(snapshot):
        raise ValidationError("签名索引与当前triggers不一致")
    queue = snapshot["review_queue"]
    if queue["version"] != 1:
        raise ValidationError("审核队列版本无效")
    events = {event["event_id"]: event for event in snapshot.get("observations", [])}
    decisions = {}
    for decision in queue["decisions"]:
        if decision["candidate_id"] in decisions:
            raise ValidationError("候选有重复审核决定")
        decisions[decision["candidate_id"]] = decision
    if not set(decisions) <= set(queue["candidates"]):
        raise ValidationError("审核记录指向未知候选")
    for key, candidate in queue["candidates"].items():
        if candidate["skill_id"] not in ids or key != candidate["candidate_id"] or key != digest([candidate["skill_id"], candidate["text"].casefold()]):
            raise ValidationError("候选ID或所属skill无效")
        text = candidate["text"]
        if not text.strip() or any(c in text for c in "\r\n\x00") or candidate["status"] not in ("pending", "approved", "rejected"):
            raise ValidationError("候选文本或状态无效")
        if not candidate["evidence"]:
            raise ValidationError("签名候选不能没有原文证据")
        query_ids = set()
        for evidence in candidate["evidence"]:
            event = events.get(evidence["event_id"])
            if event is None or event["baseline_top1"] != candidate["skill_id"] or event["query_id"] != evidence["query_id"] or event["sample_kind"] != evidence["sample_kind"]:
                raise ValidationError("候选证据未绑定正确观测")
            start, end = evidence["span"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(event["query"]) or event["query"][start:end] != evidence["quote"] or evidence["quote"].casefold() != text.casefold():
                raise ValidationError("候选原文证据或位置无效")
            query_key = (event["sample_kind"], event["query_id"])
            if query_key in query_ids:
                raise ValidationError("候选证据重复计数")
            query_ids.add(query_key)
        if candidate["status"] == "pending":
            if candidate["review"] is not None or key in decisions:
                raise ValidationError("待审候选不能有审核决定")
        else:
            if decisions.get(key) != {"candidate_id": key, **candidate["review"]}:
                raise ValidationError("审核状态与审核记录不一致")
            if candidate["review"]["decision"] != {"approved": "approve", "rejected": "reject"}[candidate["status"]] or not candidate["review"]["reviewer"].strip() or not candidate["review"]["reason"].strip():
                raise ValidationError("审核决定或审核者/理由无效")
            if candidate["status"] == "approved" and text.casefold() not in {t.casefold() for t in snapshot["state"]["skills"][candidate["skill_id"]]["triggers"]}:
                raise ValidationError("已通过候选未进入triggers")
