"""可恢复的真实embedding演练；所有消费、评分和错误归属均为沙箱模拟。"""

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from clustering import bisect, dot, unit
from feedback import import_records
from maintenance import apply_membership, propose_membership
from manager import load_config
from models import ValidationError
from nodes import NodeManager, create_layout
from shadow import calibrate, context_for, digest, evaluate
from signatures import SignatureMatcher, compare_channels
from storage import SnapshotStore

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprints(paths):
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def queries():
    family = ["skill:fix-windows-lnk1105-locked-output-exe", "skill:resolve-lnk1105-locked-output-on-windows",
              "skill:handle-locked-or-stale-test-binaries"]
    symptoms = [
        "LINK fatal error LNK1105: cannot close file app.exe; error code 1224.",
        "Windows linker LNK1105 error code 1224 occurs when rebuilding an existing executable.",
        "Rebuild cannot overwrite the executable because the old test process is still running.",
        "The linker cannot close file app.exe. How can I find the process locking the output?",
        "刚跑完测试，Windows 的 exe 还被进程占用，重新链接无法覆盖输出。",
        "Source edits are not reflected in tests: the running test exe is stale and holds the output file open.",
        "LNK1105 cannot close file after a background run: release the holder and relink.",
        "error code 1224 while linking the output exe; stop its process or use a fresh output filename.",
    ]
    contexts = ["This happens after running the test suite.", "The debugger still has the previous executable open.",
                "I am rebuilding from PowerShell on Windows.", "A background test runner was launched in this session."]
    result = [{"id": f"locked-{i}-{j}", "query": symptom + " " + context, "expected": family}
              for i, symptom in enumerate(symptoms) for j, context in enumerate(contexts)]
    extra = [
        ("stack", "Windows test exits -1073741571 0xC00000FD before printing tests; large local fixtures on the 1 MB stack.",
         ["fix-windows-0xc00000fd-stack-overflow", "fix-stack-overflow-large-test-fixtures", "fix-test-stack-overflow-large-fixtures", "fix-windows-stack-overflow-in-large-local-fixtures", "keep-large-test-fixtures-off-windows-stack"]),
        ("macro", "C++ TEST macro: redefinition of '_reg___LINE__', undeclared '_test_body_2', __COUNTER__ token pasting.",
         ["capture-counter-once-for-test-macros", "fix-test-macro-token-paste-counter", "fix-test-macro-token-pasting-ids", "fix-test-macro-unique-name-pasting"]),
        ("parser", "Prolog parser expected '.', got operator '.' after concatenating adjacent C++ string literals without a separator space.",
         ["fix-concatenated-clause-strings-missing-separator", "fix-lexer-dot-after-concatenated-literals", "fix-lexer-dot-followed-by-nonspace", "preserve-separator-space-in-concatenated-prolog-fixture-strings"]),
        ("type", "React 19 useRef<T>() TS2554 Expected 1 arguments, but got 0. How to initialize an optional timer ref?",
         ["fix-react19-useref-ts2554-no-default", "fix-ts2554-useref-tsc-batch", "fix-ts6133-unused-and-related-tsc-errors"]),
        ("router", "react-router dev EPERM scandir ENOTEMPTY rmdir .react-router/types/+types directories on Windows.",
         ["clear-locked-react-router-typegen-dirs", "unblock-react-router-typegen-enotempty"]),
        ("scaffold", "npm create solid stalls in a non-TTY shell; manually scaffold a minimal Vite SolidJS app.",
         ["scaffold-solidjs-vite-noninteractive", "scaffold-solidjs-vite-non-interactive", "verify-windows-hybrid-shell-commands"]),
        ("negative-sort", "Explain quicksort and its average time complexity.", []),
        ("negative-ref", "Explain the React useRef API conceptually. There is no compiler error in my project.", []),
    ]
    result.extend({"id": key, "query": query, "expected": ["skill:" + name for name in names]} for key, query, names in extra)
    return result


def prepare(run, config):
    run.mkdir(parents=True, exist_ok=False)
    source_store = SnapshotStore(config["data_dir"])
    source = source_store.read()
    generation = (config["data_dir"] / "CURRENT").read_text().strip()
    protected = [path for path in (config["data_dir"] / "snapshots" / generation).rglob("*") if path.is_file()]
    protected += [config["data_dir"] / "CURRENT", config["index_path"], config["embedding_cache"],
                  ROOT.parent / "dynamic-retrieval-test" / "retrieval_program.py"]
    protected += [Path(s["source_path"]) for s in source["state"]["skills"].values()]
    write_json(run / "protected.json", fingerprints(protected))
    write_json(run / "queries.json", queries())
    initial = copy.deepcopy(source)
    initial.pop("observations", None)
    initial.pop("ratings", None)
    initial["state"].pop("feedback", None)
    sandbox = SnapshotStore(run / "store")
    baseline = sandbox.publish(initial)
    write_json(run / "run.json", {"version": 1, "stage": "prepared", "baseline": baseline,
        "official_generation": generation, "queries_digest": digest(queries()),
        "snapshot_digest": digest(initial), "feedback_options": config["feedback"],
        "started_at": datetime.now(timezone.utc).isoformat(), "queries": len(queries())})


def embed_queries(run, plan):
    sys.path.insert(0, str(ROOT.parent / "dynamic-retrieval-test"))
    import retrieval_program as rp
    config = rp.developer_embedding_api_config()
    if config is None or config.model != "text-embedding-v4":
        raise ValidationError("真实embedding配置缺失或模型不一致")
    checkpoint = run / "embedding_checkpoint.json"
    state = read_json(checkpoint) if checkpoint.exists() else {"model": config.model, "queries_digest": plan["queries_digest"], "vectors": [], "calls": []}
    if state["model"] != config.model or state["queries_digest"] != plan["queries_digest"]:
        raise ValidationError("embedding检查点与运行不一致")
    items = read_json(run / "queries.json")
    client, new_calls = rp.EmbeddingApiClient(config), 0
    while len(state["vectors"]) < len(items):
        start = len(state["vectors"])
        batch = items[start:start + min(config.batch_size, 10)]
        started = perf_counter()
        vectors = client.embed([item["query"] for item in batch])
        if any(len(vector) != 1024 for vector in vectors):
            raise ValidationError("远程API未返回1024维向量")
        state["vectors"].extend(vectors)
        state["calls"].append({"start": start, "count": len(batch), "elapsed_ms": (perf_counter()-started)*1000})
        write_json(checkpoint, state)
        new_calls += 1
        print(json.dumps({"embedding_completed": len(state["vectors"]), "total": len(items)}, ensure_ascii=False), flush=True)
    return state, new_calls


def ranking(snapshot, vector, selected=None, top_k=3):
    nodes = snapshot["state"]["clustering"]["nodes"]
    selected = list(nodes) if selected is None else selected
    members = {skill for node in selected for skill in nodes[node]["members"]}
    scored = sorted(((dot(unit(vector), unit(snapshot["vectors"]["entries"][skill]["vector"])), skill)
                     for skill in members), key=lambda item: (-item[0], item[1]))
    return [{"skill_id": skill, "score": max(-1., min(1., score)), "rank": rank,
             "node_id": next(node for node in sorted(selected) if skill in nodes[node]["members"])}
            for rank, (score, skill) in enumerate(scored[:top_k], 1)]


def route(snapshot, vector, tau, m):
    nodes = snapshot["state"]["clustering"]["nodes"]
    scores = {node: dot(unit(vector), value["centroid"]) for node, value in nodes.items()}
    ordered = sorted(scores, key=lambda node: (-scores[node], node))
    fallback = max(scores.values()) < tau
    selected = ordered if fallback else sorted(set(ordered[:m]) | {node for node, score in scores.items() if score >= tau})
    return selected, fallback


def observation(snapshot, item, vector, hits, selected, tau, m, fallback, purpose, event_id, signature=None):
    record = {"event_id": event_id, "query": item["query"], "query_vector": vector,
        "model": "text-embedding-v4", "baseline_top1": ranking(snapshot, vector, top_k=1)[0]["skill_id"],
        "selected_nodes": selected, "hits": hits, "parameters": {"k": len(snapshot["state"]["clustering"]["nodes"]), "tau": tau, "m": m},
        "ts": datetime.now(timezone.utc).isoformat(), "sample_kind": "synthetic", "mode": "regular",
        "purpose": purpose, "global_fallback": fallback, "context": context_for(snapshot)}
    if signature is not None:
        record["signature"] = signature
    return record


def exercise(run, plan, embedding):
    store = SnapshotStore(run / "store")
    # 始终从保留的基线重建演练，崩溃重跑不会在上次计数上叠加。
    baseline = store._read_generation(run / "store" / "snapshots" / plan["baseline"])
    if digest(baseline) != plan["snapshot_digest"]:
        raise ValidationError("沙箱基线已改变")
    items, vectors = read_json(run / "queries.json"), embedding["vectors"]
    matcher = SignatureMatcher(baseline["state"]["skills"])
    channel_events, timings = [], []
    for item, vector in zip(items, vectors, strict=True):
        started = perf_counter()
        signature = matcher.scan(item["query"])
        signature_ms = (perf_counter()-started)*1000
        started = perf_counter()
        hits = ranking(baseline, vector)
        timings.append({"query_id": item["id"], "signature_ms": signature_ms, "cosine_ms": (perf_counter()-started)*1000,
                        "embedding_top1": hits[0]["skill_id"], "expected": item["expected"]})
        all_nodes = list(baseline["state"]["clustering"]["nodes"])
        channel_events.append(observation(baseline, item, vector, hits, all_nodes, .5, len(all_nodes), True, "evaluation", "channels:"+item["id"], signature))
    normalized, _ = import_records(baseline, channel_events, "observations", plan["feedback_options"])
    channel_report = compare_channels(normalized["observations"])
    write_json(run / "channel_comparison.json", channel_report)
    write_json(run / "timings.json", timings)

    parameter_events = []
    for k in (4, 8):
        variant = copy.deepcopy(baseline)
        raw_vectors = {key: unit(value["vector"]) for key, value in sorted(variant["vectors"]["entries"].items())}
        fit = bisect(list(raw_vectors.values()), k, seed=42)
        variant["state"]["clustering"] = create_layout(raw_vectors, fit, .15)
        for tau in (.5, .8):
            for m in (1, 2):
                for item, vector in zip(items, vectors, strict=True):
                    selected, fallback = route(variant, vector, tau, m)
                    hits = ranking(variant, vector, selected)
                    parameter_events.append(observation(variant, item, vector, hits, selected, tau, m, fallback, "evaluation", f"grid:{k}:{tau}:{m}:"+item["id"]))
    evaluated, _ = import_records(normalized, parameter_events, "observations", plan["feedback_options"])
    write_json(run / "parameter_report.json", calibrate(evaluated["observations"], .95))
    write_json(run / "route_report.json", evaluate(evaluated["observations"]))

    # 选实际被召回最多的文件锁skill，而不是指定期望top1或伪造命中。
    counts = {}
    for item, vector in zip(items, vectors, strict=True):
        if item["id"].startswith("locked-"):
            for hit in ranking(baseline, vector):
                if hit["skill_id"] in item["expected"]:
                    counts[hit["skill_id"]] = counts.get(hit["skill_id"], 0) + 1
    target = min(counts, key=lambda skill: (-counts[skill], skill))
    manager = NodeManager(evaluated["state"]["clustering"], {key: value["vector"] for key, value in evaluated["vectors"]["entries"].items()})
    original = list(manager.layout["assignments"][target])
    target_vector = unit(evaluated["vectors"]["entries"][target]["vector"])
    wrong = min((node for node in manager.layout["nodes"] if node not in original),
                key=lambda node: dot(target_vector, manager.layout["nodes"][node]["centroid"]))
    manager.assign(target, [wrong])
    evaluated["state"]["clustering"] = manager.layout
    store.publish(evaluated)
    consumption = []
    for item, vector in zip(items, vectors, strict=True):
        nodes = list(manager.layout["nodes"])
        consumption.append(observation(evaluated, item, vector, ranking(evaluated, vector), nodes, .5, len(nodes), True, "consumption", "consume:"+item["id"]))
    consumed, _ = import_records(evaluated, consumption, "observations", plan["feedback_options"])
    before_count = len(consumed["observations"])
    duplicate, duplicate_counts = import_records(consumed, consumption, "observations", plan["feedback_options"])
    assert duplicate == consumed and len(duplicate["observations"]) == before_count
    expected_by_id = {"consume:"+item["id"]: item["expected"] for item in items}
    ratings = [{"rating_id": event["event_id"]+":"+str(hit["rank"]), "event_id": event["event_id"],
        "skill_id": hit["skill_id"], "rank": hit["rank"], "value": "good" if hit["skill_id"] in expected_by_id[event["event_id"]] else "bad",
        "ts": event["ts"]} for event in consumption for hit in event["hits"]]
    rated, _ = import_records(consumed, ratings, "ratings", plan["feedback_options"])
    rated_again, rating_duplicates = import_records(rated, ratings, "ratings", plan["feedback_options"])
    assert rated_again == rated
    cohort_id = next(iter(rated["state"]["feedback"]["cohorts"]))
    assert propose_membership(rated, cohort_id) == []  # 合成反馈默认禁止自动迁移。
    proposals = propose_membership(rated, cohort_id, allow_simulation=True)
    selected_proposal = next((row for row in proposals if row["action"] == "move" and row["skill_id"] == target), None)
    if selected_proposal:
        apply_membership(rated, selected_proposal)
    final_generation = store.publish(rated)
    assert store.read() == rated
    stat = rated["state"]["feedback"]["cohorts"][cohort_id]["skills"][target]
    write_json(run / "feedback_result.json", {"target": target, "original_nodes": original, "injected_wrong_node": wrong,
        "after_nodes": rated["state"]["clustering"]["assignments"][target], "proposal": selected_proposal,
        "all_proposals": proposals, "R": stat["R"], "G": stat["G"], "B": stat["B"],
        "duplicate_observations": duplicate_counts, "duplicate_ratings": rating_duplicates,
        "restored_original_membership": rated["state"]["clustering"]["assignments"][target] == original,
        "sandbox_generation": final_generation, "feedback_source": "declared_synthetic_expected_skill_sets"})
    return {"queries": len(items), "parameter_observations": len(parameter_events), "ratings": len(ratings),
            "target": target, "membership_recovered": bool(selected_proposal) and rated["state"]["clustering"]["assignments"][target] == original,
            "channel_totals": channel_report["totals"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--stop-after", choices=["embeddings"])
    parser.add_argument("--restore-sandbox", action="store_true", help="恢复沙箱初始状态，保留全部证据与旧快照")
    parser.add_argument("--probe-dual", action="store_true", help="额外一次API调用，验证同一查询的两个通道并发执行")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    config = load_config(ROOT / "config.json")
    if not run.exists():
        prepare(run, config)
    plan = read_json(run / "run.json")
    if digest(read_json(run / "queries.json")) != plan["queries_digest"]:
        raise ValidationError("测试查询清单已改变")
    protected = read_json(run / "protected.json")
    if fingerprints(map(Path, protected)) != protected:
        raise ValidationError("受保护的正式数据已发生变化，停止恢复运行")
    if args.restore_sandbox:
        store = SnapshotStore(run / "store")
        initial = store._read_generation(run / "store" / "snapshots" / plan["baseline"])
        generation = store.publish(initial)
        result = {"status": "PASS", "sandbox_restored": store.read() == initial,
                  "official_data_unchanged": fingerprints(map(Path, protected)) == protected,
                  "restored_generation": generation, "evidence_preserved": True}
        write_json(run / "restoration.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.probe_dual:
        sys.path.insert(0, str(ROOT.parent / "dynamic-retrieval-test"))
        import retrieval_program as rp
        client = rp.EmbeddingApiClient(rp.developer_embedding_api_config())
        snapshot = SnapshotStore(run / "store").read()
        matcher = SignatureMatcher(snapshot["state"]["skills"])
        item = read_json(run / "queries.json")[0]
        request_started = Event()
        open_request = client._opener.open
        def signal_open(*arguments, **keywords):
            request_started.set()
            return open_request(*arguments, **keywords)
        client._opener.open = signal_open
        def timed(callback):
            started = perf_counter()
            result = callback()
            return {"started": started, "ended": perf_counter(), "result": result}
        def timed_signature():
            if not request_started.wait(timeout=30):
                raise ValidationError("embedding请求未启动")
            return timed(lambda: matcher.scan(item["query"]))
        with ThreadPoolExecutor(max_workers=2) as pool:
            embedding_job = pool.submit(timed, lambda: client.embed([item["query"]]))
            signature_job = pool.submit(timed_signature)
            embedding, signature = embedding_job.result(), signature_job.result()
        result = {"status": "PASS", "api_calls": 1, "query": item["query"], "embedding_model": client.config.model,
                  "embedding_vector": embedding["result"][0], "signature": signature["result"],
                  "embedding_ms": (embedding["ended"]-embedding["started"])*1000,
                  "signature_ms": (signature["ended"]-signature["started"])*1000,
                  "overlap_ms": max(0., min(embedding["ended"], signature["ended"])-max(embedding["started"], signature["started"]))*1000,
                  "official_data_unchanged": fingerprints(map(Path, protected)) == protected}
        probe = run / "concurrency_probe.json"
        if probe.exists():
            index = len(list(run.glob("concurrency_probe_attempt*.json"))) + 1
            write_json(run / f"concurrency_probe_attempt{index}.json", read_json(probe))
        write_json(probe, result)
        print(json.dumps({key:value for key,value in result.items() if key not in ("embedding_vector", "signature")}, ensure_ascii=False, indent=2))
        return
    embedding, new_calls = embed_queries(run, plan)
    plan["stage"] = "embeddings_checkpointed"
    write_json(run / "run.json", plan)
    if args.stop_after:
        print(json.dumps({"status": "CHECKPOINTED", "new_api_calls": new_calls, "resume": str(run)}, ensure_ascii=False))
        return
    result = exercise(run, plan, embedding)
    unchanged = fingerprints(map(Path, protected)) == protected
    result.update({"official_data_unchanged": unchanged, "new_api_calls_this_resume": new_calls,
                   "total_api_calls": len(embedding["calls"]), "status": "PASS" if unchanged and result["membership_recovered"] else "INCOMPLETE"})
    write_json(run / "result.json", result)
    plan["stage"] = "completed"
    write_json(run / "run.json", plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
