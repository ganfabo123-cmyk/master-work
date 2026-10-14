# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detail_traces import load_events
fp = r"D:\PycharmProjects\CodeHarness\master_work\agent-traces\sessions\claude_code\a20a4070-6246-4e9e-adf6-f38b0c1dc3fa.jsonl"
events = load_events(fp)
for e in events[-6:]:
    ln=e['line']
    if e['kind']=='tool_call':
        import json as J
        print(f"L{ln} CALL {e['tool']} {J.dumps(e.get('inp'), ensure_ascii=False)[:200]}")
    elif e['kind']=='tool_result':
        print(f"L{ln}   {'ERR' if e.get('is_error') else 'res'}: {(e.get('text') or '')[:300]}")
    elif e['kind']=='text':
        print(f"L{ln} {e['role'].upper()}: {(e.get('text') or '')[:400]}")
