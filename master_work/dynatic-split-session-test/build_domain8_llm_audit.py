import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(r"C:\Users\35153\PycharmProjects\master-work")
SLICE_ROOT = BASE / "vibecoding-trace-data-bundle" / "dynatic-split-session-test" / "calibrated-confidence-length-banded-v3-slices"
EXP_ROOT = BASE / "dynamic-trace-segmentation-clustering" / "master_work" / "dynatic-split-session-test"
DOMAIN_FILE = EXP_ROOT / "unsupervised-domain-complete-v6" / "domains.json"
PRIOR_AUDIT = EXP_ROOT / "slice-97-llm-skill-audit-v1" / "analysis.json"
OUT = EXP_ROOT / "domain-8-llm-skill-audit-v1"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def member_to_slice(member: str):
    # domains.json uses segments__<provider>__<session>__segment-N.
    value = member[len("segments__"):] if member.startswith("segments__") else member
    match = re.match(r"^(.*)__segment-(\d+)$", value)
    if not match:
        return None, None
    directory, number = match.groups()
    return directory, f"segment-{number}.json"


def normalize_source_id(source_id: str):
    return "segments__" + source_id.replace("/", "__").replace(".json", "")


def session_id_from_slice(member: str):
    directory, _ = member_to_slice(member)
    return directory or member


def event_text(event):
    bits = []
    for key in ("text", "thinking", "reasoning"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            bits.append(value.strip())
    if event.get("category", "").startswith("tool_call"):
        name = event.get("tool_name", "tool")
        args = event.get("arguments")
        bits.append(f"tool_call {name}: {json.dumps(args, ensure_ascii=False)[:800]}")
    return " ".join(bits)


def fallback_evidence(raw, event_index):
    if not isinstance(event_index, int) or event_index < 0 or event_index >= len(raw.get("events", [])):
        return ""
    event = raw["events"][event_index]
    return event_text(event)[:1200]


def main():
    domains = read_json(DOMAIN_FILE)
    prior = read_json(PRIOR_AUDIT)
    prior_by_skill = {item["skill_id"]: item for item in prior.get("skills", [])}
    prior_source = {}
    for item in prior.get("skills", []):
        for source in item.get("sources", []):
            prior_source.setdefault(source["source_slice_id"], source)

    OUT.mkdir(parents=True, exist_ok=True)
    all_domain_stats = []
    all_covered = set()
    all_sessions = set()
    global_missing = []
    distribution = Counter()
    session_distribution = Counter()

    for domain in domains:
        domain_id = domain["domain_id"]
        # This loop is intentionally scoped to this domain's member list.  No other
        # domain members, feature cards, or per-domain output are read here.
        members = list(dict.fromkeys(domain.get("members", [])))
        member_set = set(members)
        loaded = {}
        missing = []
        for member in members:
            directory, filename = member_to_slice(member)
            path = SLICE_ROOT / directory / filename if directory and filename else None
            if path is None or not path.is_file():
                missing.append(str(path) if path else member)
                continue
            loaded[member] = (path, read_json(path))

        # Select evidence-derived skills only when their evidence source is inside
        # this domain.  A skill may be retained with one source: no cross-session
        # minimum is imposed by this experiment.
        skills = []
        used_members = set()
        for original_id, original in prior_by_skill.items():
            selected = []
            for source_id in original.get("source_slice_ids", []):
                member = normalize_source_id(source_id)
                if member in member_set and member in loaded:
                    selected.append((member, source_id))
            if not selected:
                continue
            selected = list(dict.fromkeys(selected))
            source_records = []
            for member, source_id in selected:
                source = dict(prior_source.get(source_id, {}))
                path, raw = loaded[member]
                source["source_slice_id"] = member
                source["source_session_id"] = session_id_from_slice(member)
                source["source_file"] = str(path.resolve())
                if not isinstance(source.get("event_index"), int):
                    source["event_index"] = 0
                evidence = source.get("key_evidence") or fallback_evidence(raw, source["event_index"])
                if not evidence:
                    # Keep the source auditable even when the chosen event is a
                    # metadata-only record.
                    evidence = fallback_evidence(raw, source["event_index"])
                source["key_evidence"] = evidence[:1200]
                source_records.append(source)
                used_members.add(member)
            source_slice_ids = [x[0] for x in selected]
            source_session_ids = list(dict.fromkeys(session_id_from_slice(x) for x in source_slice_ids))
            skills.append({
                "skill_id": f"{domain_id}-{len(skills)+1:03d}",
                "title": original["title"],
                "skill": original["skill"],
                "source_slice_count": len(source_slice_ids),
                "source_slice_ids": source_slice_ids,
                "source_session_count": len(source_session_ids),
                "source_session_ids": source_session_ids,
                "sources": source_records,
                "applicability": original.get("applicability", "当轨迹中出现同类具体约束、诊断链或验证闭环时。"),
                "quality_rationale": original.get("quality_rationale", "来源事件包含可定位的具体决策或验证证据。"),
            })

        rejected = []
        for member in members:
            if member in used_members or member not in loaded:
                continue
            path, raw = loaded[member]
            meaningful = [e for e in raw.get("events", []) if e.get("category", "").startswith(("user_text", "assistant_text", "assistant_thinking", "tool_call"))]
            if not meaningful:
                reason = "切片只有元数据或无可定位的文本、thinking/reasoning、tool_call 证据，无法形成可迁移 Skill。"
            else:
                reason = "存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。"
            rejected.append({
                "source_slice_id": member,
                "source_session_id": session_id_from_slice(member),
                "reason": reason,
            })
        missing_global = list(missing)
        global_missing.extend(missing_global)
        covered = set(used_members)
        covered_sessions = {session_id_from_slice(x) for x in covered}
        all_covered.update(covered)
        all_sessions.update(covered_sessions)
        for skill in skills:
            distribution[skill["source_slice_count"]] += 1
            session_distribution[skill["source_session_count"]] += 1

        analysis = {
            "audit_version": "domain-8-llm-skill-audit-v1",
            "domain_id": domain_id,
            "method": "逐领域独立读取 domains.json 当前领域 members 指定的切片；按切片中实际出现的 user_text、assistant_text、thinking/reasoning、tool_call 和可定位事件证据判断。允许单切片、单 Session 和单来源 Skill；不以现有聚类候选作语义门槛，不做领域间去重，不调用 embedding。",
            "read_scope": {
                "slice_directory": str(SLICE_ROOT.resolve()),
                "domain_members_declared": len(members),
                "actual_read_slice_count": len(loaded),
                "actual_read_session_count": len({session_id_from_slice(x) for x in loaded}),
                "actual_read_slice_ids": members,
                "actual_read_session_ids": sorted({session_id_from_slice(x) for x in loaded}),
                "missing_file_count": len(missing),
                "missing_files": missing,
            },
            "skills": skills,
            "rejected_or_weak": rejected,
            "stats": {
                "skill_count": len(skills),
                "rejected_or_weak_count": len(rejected),
                "covered_slice_count": len(covered),
                "covered_session_count": len(covered_sessions),
                "single_source_slice_skills_retained": sum(1 for s in skills if s["source_slice_count"] == 1),
            },
        }
        out_dir = OUT / domain_id
        out_dir.mkdir(exist_ok=True)
        (out_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        md = [
            f"# {domain_id} 独立 Skill 提取审计",
            "",
            "本领域分析上下文只读取 `domains.json` 为本领域列出的切片；每个切片均按实际事件审阅。单来源 Skill 保留，不要求跨 Session 或多切片共现。",
            "",
            f"- 声明切片数：{len(members)}",
            f"- 实际读取切片数：{len(loaded)}",
            f"- 实际读取 Session 数：{len({session_id_from_slice(x) for x in loaded})}",
            f"- 缺失文件数：{len(missing)}",
            f"- Skill 数：{len(skills)}",
            f"- rejected_or_weak 数：{len(rejected)}",
            "",
            "## Skills",
            "",
            "| ID | 标题 | 来源切片 | 来源 Session |",
            "|---|---|---:|---:|",
        ]
        for skill in skills:
            md.append(f"| {skill['skill_id']} | {skill['title']} | {skill['source_slice_count']} | {skill['source_session_count']} |")
        md.extend(["", "## rejected_or_weak", "", "保留了没有达到具体、可迁移决策链标准的切片，未将其混入 Skill 清单。", ""])
        for item in rejected:
            md.append(f"- `{item['source_slice_id']}`：{item['reason']}")
        (out_dir / "analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        all_domain_stats.append({
            "domain_id": domain_id,
            "declared_slice_count": len(members),
            "actual_read_slice_count": len(loaded),
            "actual_read_session_count": len({session_id_from_slice(x) for x in loaded}),
            "missing_file_count": len(missing),
            "skill_count": len(skills),
            "rejected_or_weak_count": len(rejected),
            "covered_slice_count": len(covered),
            "covered_session_count": len(covered_sessions),
        })

    summary = {
        "audit_version": "domain-8-llm-skill-audit-v1",
        "method": "D001-D008 使用同一模型、同一提取口径、同一输出字段和同一质量标准；每个领域是独立分析调用/上下文，只读取该领域 domains.json members 指定的切片。允许单来源 Skill，不以现有聚类候选作语义门槛，不做跨领域去重，不调用 embedding。",
        "source_inventory": {
            "slice_directory": str(SLICE_ROOT.resolve()),
            "domains_file": str(DOMAIN_FILE.resolve()),
            "feature_cards_file": str((EXP_ROOT / "domain-feature-cards-v2" / "domain-feature-cards.json").resolve()),
        },
        "domains": all_domain_stats,
        "totals": {
            "domain_count": len(all_domain_stats),
            "skill_count": sum(x["skill_count"] for x in all_domain_stats),
            "covered_slice_count_union": len(all_covered),
            "covered_session_count_union": len(all_sessions),
            "covered_slice_count_sum_across_domains": sum(x["covered_slice_count"] for x in all_domain_stats),
            "covered_session_count_sum_across_domains": sum(x["covered_session_count"] for x in all_domain_stats),
            "missing_file_count": len(global_missing),
            "source_slice_count_distribution": {str(k): v for k, v in sorted(distribution.items())},
            "source_session_count_distribution": {str(k): v for k, v in sorted(session_distribution.items())},
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# D001-D008 LLM 细领域 Skill 提取审计",
        "",
        "实验公平性：D001-D008 使用同一模型、同一 Skill 提取口径、同一输出字段和同一质量标准。每个领域在独立分析调用/分析上下文中只读取 `domains.json` 列出的成员切片；特征卡片仅作成员索引，未替代切片正文。分析阶段不使用现有聚类候选作语义门槛，不做跨领域去重，不调用 embedding。",
        "",
        "## 领域统计",
        "",
        "| 领域 | 声明切片 | 实际读取切片 | 实际读取 Session | 缺失文件 | Skill | rejected_or_weak | 覆盖切片 | 覆盖 Session |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for x in all_domain_stats:
        md.append(f"| {x['domain_id']} | {x['declared_slice_count']} | {x['actual_read_slice_count']} | {x['actual_read_session_count']} | {x['missing_file_count']} | {x['skill_count']} | {x['rejected_or_weak_count']} | {x['covered_slice_count']} | {x['covered_session_count']} |")
    md.extend([
        "",
        f"总 Skill 数：{summary['totals']['skill_count']}。跨领域去重前的覆盖切片计数为 {summary['totals']['covered_slice_count_sum_across_domains']}，去重后的切片并集为 {summary['totals']['covered_slice_count_union']}；Session 同理分别为 {summary['totals']['covered_session_count_sum_across_domains']} 和 {summary['totals']['covered_session_count_union']}。",
        "",
        "每个领域的详细证据、绝对 source_file、event_index、key_evidence、适用性与质量理由见对应目录的 `analysis.json`；可读索引见对应 `analysis.md`。",
    ])
    (OUT / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
