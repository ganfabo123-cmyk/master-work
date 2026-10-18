"""Replay the captured timed-out batch against an isolated snapshot and real embeddings."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3] / 'experiments' / 'skill-management' / 'skill-management-system'
sys.path.insert(0, str(ROOT))
from dsh_bridge import handle
from manager import load_config
from storage import SnapshotStore


def main():
    request_id = '39b730742b0449f8af87166bd683035d'
    rows = [json.loads(line) for line in (ROOT/'data/logs/runtime.jsonl').read_text(encoding='utf8').splitlines()]
    messages = [row['raw_trace'] for row in rows
                if row.get('request_id') == request_id and row['event'] == 'bridge_trace_received']
    assert len(messages) == 148, len(messages)
    output = Path(__file__).resolve().parent / f'bridge-timeout-replay-{time.time_ns()}'
    output.mkdir()
    config = load_config(ROOT/'config.json')
    snapshot = SnapshotStore(config['data_dir']).read()
    config['data_dir'] = output/'data'
    SnapshotStore(config['data_dir']).publish(snapshot)
    config_path = output/'config.json'
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    request = {'management_root': str(ROOT), 'config_path': str(config_path),
               'messages': messages, 'retrieval_options': {'top_k': 3, 'sample_kind': 'fixture'}}
    started = time.perf_counter()
    result = handle(request)
    elapsed = time.perf_counter() - started
    audit = [json.loads(line) for line in (output/'data/logs/runtime.jsonl').read_text(encoding='utf8').splitlines()]
    summary = {'source_request_id': request_id, 'input_count': len(messages), 'elapsed_seconds': elapsed,
               'status': result['status'], 'hit_count': len(result['items']),
               'hint_generated': len(result['messages']) > len(messages),
               'embedding_started': sum(r['event'] == 'embedding_started' for r in audit),
               'trace_completed': sum(r['event'] == 'trace_completed' for r in audit),
               'tool_results': sum(r['event'] == 'trigger_decision' and r.get('event_type') == 'tool_result' for r in audit),
               'bridge_completed': sum(r['event'] == 'bridge_completed' for r in audit)}
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'output': str(output), **summary}, ensure_ascii=False))


if __name__ == '__main__':
    main()
