# -*- coding: utf-8 -*-
# Final sweep: consecutive identical tool results, long silent gaps, truncated endings.
import json, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detail_traces import load_events

ROOT = r"D:\PycharmProjects\CodeHarness\master_work\data\raw\agent-traces\sessions"

def iter_sessions():
    for d in sorted(os.listdir(ROOT)):
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp): continue
        for f in sorted(os.listdir(dp)):
            if f == '.gitkeep': continue
            yield d, f, os.path.join(dp, f)

for d, f, fp in iter_sessions():
    try:
        events = load_events(fp)
    except Exception as e:
        print(f"### {d}/{f}: LOAD FAIL {e}")
        continue
    # results in order (with is_error)
    results = [e for e in events if e['kind']=='tool_result']
    # consecutive identical result heads (>=3)
    run_head, run_len, run_start = None, 0, 0
    flagged = []
    def head(t): 
        t = re.sub(r'\s+',' ', t or '').strip()
        return t[:120]
    for i, r in enumerate(results):
        h = head(r.get('text',''))
        if h and h == run_head:
            run_len += 1
        else:
            if run_head and run_len >= 3:
                flagged.append((run_start, run_len, run_head))
            run_head, run_len, run_start = h, 1, i
    if run_head and run_len >= 3:
        flagged.append((run_start, run_len, run_head))
    # timestamps (claude only)
    ts = [e.get('ts') for e in events if e.get('ts')]
    gaps = []
    if ts:
        from datetime import datetime
        pts = [datetime.fromisoformat(t.replace('Z','+00:00')) for t in ts if t]
        for a, b in zip(pts, pts[1:]):
            g = (b-a).total_seconds()
            if g > 900:
                gaps.append((a.isoformat(), int(g)))
    # last event kind
    last = events[-1] if events else None
    lastkind = (last['kind'] + '/' + str(last.get('role'))) if last else 'none'
    # count user text messages
    nuser = sum(1 for e in events if e['kind']=='text' and e.get('role')=='user')
    line_s = f"{d}/{f}"
    print(f"### {line_s} | user_texts={nuser} | last={lastkind}")
    for start, ln, h in flagged:
        print(f"    CONSEC_SAME_RESULT x{ln} starting idx{start}: {h}")
    for t, g in gaps[:6]:
        print(f"    GAP {g}s at {t}")
