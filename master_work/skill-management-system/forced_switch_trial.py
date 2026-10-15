"""人为令两通道完全一致，验证实际切换；零远程请求，正式数据不写入。"""

import argparse
import copy
import json
from pathlib import Path

from feedback import import_records
from live_trial import fingerprints, observation, write_json
from manager import load_config
from signatures import SignatureMatcher, resolve_with_policy, update_channel_policy
from storage import SnapshotStore


ROOT = Path(__file__).resolve().parent


def run_trial(directory):
    config = load_config(ROOT / "config.json")
    official = SnapshotStore(config["data_dir"])
    source = official.read()
    current = (config["data_dir"] / "CURRENT").read_text().strip()
    paths = [config["data_dir"] / "CURRENT"] + [path for path in (config["data_dir"] / "snapshots" / current).rglob("*") if path.is_file()]
    protected = fingerprints(paths)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "protected.json", protected)
    store = SnapshotStore(directory / "store")
    snapshot = copy.deepcopy(source)
    snapshot.pop("observations", None)
    snapshot.pop("ratings", None)
    snapshot["state"].pop("feedback", None)
    snapshot["state"].pop("channel_policy", None)
    initial = store.publish(snapshot)
    matcher = SignatureMatcher(snapshot["state"]["skills"])
    choice = next((trigger, matcher.scan(trigger)["top1"])
                  for skill in snapshot["state"]["skills"].values() for trigger in skill["triggers"]
                  if matcher.scan(trigger)["status"] == "unique")
    trigger, target = choice
    other = next(key for key in snapshot["state"]["skills"] if key != target)
    vector = snapshot["vectors"]["entries"][target]["vector"]
    nodes = list(snapshot["state"]["clustering"]["nodes"])
    hit_node = snapshot["state"]["clustering"]["assignments"][target][0]
    events = []
    for i in range(22):
        query = f"{trigger} forced-agreement-case-{i}"
        signature = matcher.scan(query)
        assert signature["top1"] == target
        hits = [{"skill_id": target, "score": 1., "rank": 1, "node_id": hit_node}]
        record = observation(snapshot, {"query": query}, vector, hits, nodes, .5, len(nodes), True,
                             "evaluation", f"forced:{i}", signature)
        # 明确作弊：直接覆盖昂贵通道的结论；不是实际embedding的返回值。
        record["baseline_top1"] = target if i < 20 else other
        events.append(record)
    calls = {"embedding": 0}
    def counted_embedding(query):
        calls["embedding"] += 1
        return target
    def forbidden_embedding(query):
        raise AssertionError("签名优先仍调用了embedding")
    try:
        snapshot, _ = import_records(snapshot, events[:19], "observations", config["feedback"])
        update_channel_policy(snapshot, allow_simulation=True)
        assert snapshot["state"]["channel_policy"]["modes"][target] == "shadow"
        store.publish(snapshot)
        before = resolve_with_policy(store.read(), trigger, counted_embedding, allow_simulation=True)
        assert before["channel"] == "embedding" and calls["embedding"] == 1
        snapshot, _ = import_records(snapshot, events[19:20], "observations", config["feedback"])
        update_channel_policy(snapshot, allow_simulation=True)
        promoted = store.publish(snapshot)
        restarted = store.read()
        assert restarted["state"]["channel_policy"]["modes"][target] == "signature_first"
        after = resolve_with_policy(restarted, trigger, forbidden_embedding, allow_simulation=True)
        assert after == {"channel": "signature", "skill_id": target}
        assert calls["embedding"] == 1
        # 模拟策略必须显式放行，否则相同查询仍进入昂贵回调。
        assert resolve_with_policy(restarted, trigger, counted_embedding)["channel"] == "embedding"
        assert resolve_with_policy(restarted, "无任何报错的普通问候", counted_embedding, allow_simulation=True)["channel"] == "embedding"
        # 对真实签名歧义同样保留昂贵兜底。
        ambiguity = next((t for skill in snapshot["state"]["skills"].values() for t in skill["triggers"]
                          if matcher.scan(t)["status"] == "ambiguous"), None)
        assert ambiguity is not None
        assert resolve_with_policy(restarted, ambiguity, counted_embedding, allow_simulation=True)["channel"] == "embedding"
        snapshot, duplicates = import_records(snapshot, events[:20], "observations", config["feedback"])
        assert duplicates == {"added": 0, "duplicates": 20}
        snapshot, _ = import_records(snapshot, events[20:], "observations", config["feedback"])
        policy = update_channel_policy(snapshot, allow_simulation=True)
        rolled_back = store.publish(snapshot)
        assert policy["modes"][target] == "shadow"
        assert resolve_with_policy(store.read(), trigger, counted_embedding, allow_simulation=True)["channel"] == "embedding"
        result = {"status": "PASS", "evidence_origin": "forced_results_not_real_embedding", "sample_kind": "synthetic",
            "target": target, "trigger": trigger, "at_19": "shadow", "at_20": "signature_first",
            "after_restart": after, "embedding_calls_for_promoted_hit": 0,
            "simulation_guard": "PASS", "miss_fallback": "PASS", "ambiguity_fallback": "PASS",
            "duplicates": duplicates, "at_22_with_2_disagreements": "shadow", "agreement_at_rollback": 20/22,
            "policy_history": policy["history"], "promoted_generation": promoted, "rollback_generation": rolled_back,
            "real_api_calls": 0}
        write_json(directory / "result.json", result)
    finally:
        restored = store.publish(store._read_generation(directory / "store" / "snapshots" / initial))
        restoration = {"sandbox_restored": store.read() == store._read_generation(directory / "store" / "snapshots" / initial),
                       "official_data_unchanged": fingerprints(paths) == protected, "generation": restored}
        write_json(directory / "restoration.json", restoration)
        assert restoration["sandbox_restored"] and restoration["official_data_unchanged"]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    print(json.dumps(run_trial(parser.parse_args().run_dir.resolve()), ensure_ascii=False, indent=2))
