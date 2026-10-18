"""Recover successful Write/Edit operations up to the failing trace call.

This is an experiment preparation tool, outside the agent workspaces.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPECS = {
    'epilog': ('c99032e9-377b-4ae9-a9a9-ec7752b059cd', 'd:/Epilog/', 369),
    'iceberg': ('860618e1-0cf6-43c6-81cf-fe67123082ba', 'd:/IceBerg/', 81),
    'mydatabase': ('c84c0ad3-c368-40df-87b1-5ef9effe237a', 'c:/Users/USER/Documents/MyDatabase/', 239),
}

def blocks(row):
    content = row.get('message', {}).get('content', [])
    return content if isinstance(content, list) else []

def normalize(path):
    return re.sub('/+', '/', path.replace('\\', '/'))

def recover(name, tid, prefix, stop):
    rows = [json.loads(s) for s in (ROOT/'data/raw/agent-traces/sessions/claude_code'/f'{tid}.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    results = {b['tool_use_id']: b for r in rows for b in blocks(r) if b.get('type') == 'tool_result' and 'tool_use_id' in b}
    files = {}
    provenance = {}
    for index, row in enumerate(rows[:stop]):
        # The original trace moves these headers to include/ in row 93.
        if name == 'epilog' and index == 94:
            for filename in ('atoms.h', 'variables.h'):
                src = 'internals/include/'+filename
                files['include/'+filename] = files.pop(src)
                provenance['include/'+filename] = provenance.pop(src)
        for b in blocks(row):
            if b.get('type') != 'tool_use':
                continue
            a = b.get('input', {})
            path = normalize(a.get('file_path', ''))
            if not path.lower().startswith(prefix.lower()):
                continue
            rel = path[len(prefix):]
            result = results.get(b['id'], {})
            if result.get('is_error') or 'tool_use_error' in str(result.get('content', '')):
                continue
            operation = b.get('name')
            if operation == 'Write':
                files[rel] = a['content']
            elif operation == 'Edit':
                if rel not in files:
                    raise RuntimeError(f'{name}:{index}: edit without recovered base: {rel}')
                old = a['old_string']
                if old not in files[rel]:
                    raise RuntimeError(f'{name}:{index}: edit does not match: {rel}')
                files[rel] = files[rel].replace(old, a['new_string'], -1 if a.get('replace_all') else 1)
            elif operation == 'Read' and rel not in files:
                raw = result.get('content', '')
                if isinstance(raw, str) and raw.startswith('1\t'):
                    numbered = raw.splitlines()
                    if all(re.match(r'^\d+\t', line) for line in numbered):
                        files[rel] = '\n'.join(line.split('\t', 1)[1] for line in numbered)+'\n'
                    else:
                        continue
                else:
                    continue
            else:
                continue
            provenance.setdefault(rel, []).append({'row': index+1, 'tool': operation})
    # Configs read immediately after the failure, before any edits.
    for index in ([127, 129] if name == 'iceberg' else [242] if name == 'mydatabase' else []):
        for b in blocks(rows[index]):
            if b.get('name') == 'Read':
                path = normalize(b['input']['file_path'])
                rel = path[len(prefix):]
                raw = results[b['id']]['content']
                files[rel] = '\n'.join(line.split('\t',1)[1] for line in raw.splitlines())+'\n'
                provenance[rel] = [{'row': index+1, 'tool': 'Read'}]
    # Do not pass obsolete static page, agent directives or planning docs to workers.
    for rel in list(files):
        if rel.lower().endswith(('.md', '.sh', '.bat')) or (name == 'iceberg' and rel in ('index.html','style.css','main.js')):
            del files[rel]
    for arm in ('baseline', 'managed'):
        dest = ROOT/'experiments/retrieval-feasibility/fixtures'/name/arm
        for rel, content in files.items():
            out = dest/rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding='utf-8', newline='\n')
    (ROOT/'experiments/retrieval-feasibility/evidence'/f'{name}-sources.json').write_text(json.dumps({'trace_id':tid,'failure_row':stop+2,'files':{p:provenance[p] for p in files}},indent=2),encoding='utf-8')
    print(name, len(files), 'recovered files per arm')

if __name__ == '__main__':
    for name, spec in SPECS.items():
        recover(name, *spec)
