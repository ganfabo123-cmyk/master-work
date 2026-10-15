"""复用已保存的真实embedding观测，检验正式维护事务；模拟反馈仅在私有沙箱放行。"""

import copy
import json
from pathlib import Path
import argparse

from feedback import import_records
from live_trial import fingerprints, read_json, write_json
from maintenance import initialize_maintenance, create_maintenance_plan, apply_maintenance_plan
from manager import feedback_operation, load_config
from nodes import NodeManager
from storage import SnapshotStore


ROOT = Path(__file__).resolve().parent


def run_trial(directory):
    config = load_config(ROOT / "config.json")
    official = SnapshotStore(config["data_dir"])
    source = official.read()
    current = (config["data_dir"] / "CURRENT").read_text().strip()
    paths = [config["data_dir"] / "CURRENT"] + [p for p in (config["data_dir"] / "snapshots" / current).rglob("*") if p.is_file()]
    protected = fingerprints(paths)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "protected.json", protected)
    cached_run = ROOT / "runs" / "live-20261015-01"
    cached_result = read_json(cached_run / "feedback_result.json")
    cached = SnapshotStore(cached_run / "store")._read_generation(cached_run / "store" / "snapshots" / cached_result["sandbox_generation"])
    assert source["vectors"] == cached["vectors"]
    sandbox = copy.deepcopy(source)
    for key in ("observations", "ratings", "maintenance_queue", "maintenance_log"):
        sandbox.pop(key, None)
    sandbox["state"].pop("feedback", None)
    sandbox["state"].pop("maintenance", None)
    sandbox = import_records(sandbox, [], "observations", config["feedback"])[0]
    initialize_maintenance(sandbox, config["maintenance"])
    store = SnapshotStore(directory / "store")
    initial = store.publish(sandbox)
    config = dict(config, data_dir=directory / "store")
    try:
        target = cached_result["target"]
        original = list(sandbox["state"]["clustering"]["assignments"][target])
        manager = NodeManager(sandbox["state"]["clustering"], {k:v["vector"] for k,v in sandbox["vectors"]["entries"].items()})
        manager.assign(target, [cached_result["injected_wrong_node"]])
        sandbox["state"]["clustering"] = manager.layout
        store.publish(sandbox)
        observations = [copy.deepcopy(e) for e in cached["observations"] if e["purpose"] == "consumption"]
        assert all(e["sample_kind"] == "synthetic" for e in observations)
        feedback_operation(config, "observe", observations)
        feedback_operation(config, "rate", cached["ratings"])
        sandbox = store.read()
        formal_plan = create_maintenance_plan(sandbox)
        assert formal_plan["actions"] == []
        plan = create_maintenance_plan(sandbox, allow_simulation=True)
        write_json(directory / "plan.json", plan)
        assert any(action.get("skill_id") == target and action["action"] in ("move", "attach") for action in plan["actions"])
        store.publish(sandbox)
        sandbox, applied = apply_maintenance_plan(store.read(), plan["plan_id"], allow_simulation=True)
        generation = store.publish(sandbox)
        after = store.read()
        assert after == sandbox
        repeat, changed = apply_maintenance_plan(after, plan["plan_id"], allow_simulation=True)
        assert not changed and repeat == after
        destinations = after["state"]["clustering"]["assignments"][target]
        assert set(original) <= set(destinations) and cached_result["injected_wrong_node"] not in destinations
        result = {"status": "PASS", "source_run": "live-20261015-01", "new_api_calls": 0,
            "reused_remote_query_observations": len(observations), "simulated_ratings": len(cached["ratings"]),
            "formal_mode_ignores_simulated_feedback": True, "target": target, "original": original,
            "injected_wrong_node": cached_result["injected_wrong_node"], "after": destinations,
            "window_result": after["maintenance_queue"]["plans"][plan["plan_id"]]["result"],
            "execution_idempotent": True, "generation": generation}
        write_json(directory / "result.json", result)
    finally:
        store.publish(store._read_generation(directory / "store" / "snapshots" / initial))
        restoration = {"sandbox_restored": store.read() == store._read_generation(directory / "store" / "snapshots" / initial),
                       "official_data_unchanged": fingerprints(paths) == protected}
        write_json(directory / "restoration.json", restoration)
        assert all(restoration.values())
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    print(json.dumps(run_trial(parser.parse_args().run_dir.resolve()), ensure_ascii=False, indent=2))
