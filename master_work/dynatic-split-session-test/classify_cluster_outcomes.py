"""Split domain clusters by terminal success/failure evidence."""
from __future__ import annotations

import argparse, json, re
from collections import Counter
from pathlib import Path

FAIL = re.compile(r"\b(error|failed|failure|exception|traceback|fatal|unable|cannot|couldn't|doesn't work|not working|broken|missing|regression)\b", re.I)
PASS = re.compile(r"\b(passed|pass|success|successful|fixed|works|working|done|completed|resolved|implemented|verified|all tests pass|build succeeded|green)\b", re.I)


def text_for_event(event: dict) -> str:
    pieces = []
    if isinstance(event.get("text"), str): pieces.append(event["text"])
    args = event.get("arguments")
    if isinstance(args, dict):
        category = str(event.get("category", ""))
        # Do not scan source code or replacement payloads for outcome words.
        allowed = {"command", "description", "query", "pattern"} if category.startswith("tool_call:") else set(args)
        for key, value in args.items():
            if key in allowed and isinstance(value, str): pieces.append(value)
    return " ".join(pieces)


def classify(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8")); rows = []
    for event in data.get("events", []):
        text = text_for_event(event)
        if text.strip(): rows.append({"category": event.get("category", "unknown"), "text": text})
    # Use the terminal window: intermediate errors may be repaired later.
    tail = rows[-20:]
    fail_hits = [(m.group(0), r["category"], r["text"][:260]) for r in tail for m in FAIL.finditer(r["text"])]
    pass_hits = [(m.group(0), r["category"], r["text"][:260]) for r in tail for m in PASS.finditer(r["text"])]
    # Explicit failure language is stronger than generic success words.
    fail_score = len(fail_hits) + sum(2 for word, *_ in fail_hits if word.lower() in {"failed", "failure", "fatal", "traceback", "exception", "not working", "broken"})
    pass_score = len(pass_hits) + sum(2 for word, *_ in pass_hits if word.lower() in {"passed", "success", "successful", "fixed", "resolved", "verified", "completed"})
    if fail_score > pass_score and fail_score > 0: label = "failure"
    elif pass_score > fail_score and pass_score > 0: label = "success"
    else: label = "unresolved"
    return {"label": label, "source_file": str(path), "tail_event_count": len(tail), "success_score": pass_score, "failure_score": fail_score, "success_evidence": pass_hits[:8], "failure_evidence": fail_hits[:8]}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--slices-dir", type=Path, required=True); ap.add_argument("--domains", type=Path, required=True); ap.add_argument("--output", type=Path, required=True); args = ap.parse_args()
    by_name = {p.parent.name + "__" + p.stem: p for p in args.slices_dir.rglob("segment-*.json")}
    domains = json.loads(args.domains.read_text(encoding="utf-8")); domains = domains.get("domains", domains) if isinstance(domains, dict) else domains
    args.output.mkdir(parents=True, exist_ok=True); summaries=[]
    for domain in domains:
        rows=[]
        raw_members = domain.get("members") or domain.get("member_slice_ids", [])
        for raw in raw_members:
            sid=raw.removeprefix("segments__"); path=by_name.get(sid)
            if path:
                result=classify(path); result["slice_id"]=sid; rows.append(result)
        counts=Counter(x["label"] for x in rows)
        result={"domain_id":domain["domain_id"],"domain_terms":domain.get("terms",[]),"input_slice_count":len(rows),"outcome_counts":dict(counts),"success_slices":[x for x in rows if x["label"]=="success"],"failure_slices":[x for x in rows if x["label"]=="failure"],"unresolved_slices":[x for x in rows if x["label"]=="unresolved"],"rule":"terminal 20 text-bearing events; compare generic success/failure evidence scores; intermediate errors can be outweighed by later repair evidence"}
        (args.output/(domain["domain_id"]+".json")).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); summaries.append({"domain_id":domain["domain_id"],"input_slice_count":len(rows),"outcome_counts":dict(counts)})
    (args.output/"summary.json").write_text(json.dumps({"algorithm_version":"cluster-outcome-classification-v1","domains":summaries,"note":"unresolved is retained when the slice has no decisive terminal evidence; it is not silently forced into success or failure"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(args.output),"domains":len(summaries)},ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
