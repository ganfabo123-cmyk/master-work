# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detail_traces import load_events
fp = r"D:\PycharmProjects\CodeHarness\master_work\agent-traces\sessions\claude_code\860618e1-0cf6-43c6-81cf-fe67123082ba.jsonl"
events = load_events(fp)
# find the PDF failures area
out = []
for e in events:
    if e['kind'] == 'tool_result' and 'password-protected' in (e.get('text') or ''):
        out.append(e['line'])
print("pdf_fail_lines:", out)
lo, hi = min(out)-14, max(out)+6
for e in events:
    if lo <= e['line'] <= hi:
        ln = e['line']
        if e['kind']=='tool_call':
            import json as J
            print(f"L{ln} CALL {e['tool']} {J.dumps(e.get('inp'), ensure_ascii=False)[:170]}")
        elif e['kind']=='tool_result':
            print(f"L{ln}   {'ERR' if e.get('is_error') else 'res'}: {(e.get('text') or '')[:150]}")
        elif e['kind']=='text':
            print(f"L{ln} {e['role'].upper()}: {(e.get('text') or '')[:220]}")
