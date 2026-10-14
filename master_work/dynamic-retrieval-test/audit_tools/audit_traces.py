# -*- coding: utf-8 -*-
# Read-only analyzer for agent-traces sessions. Prints per-session stats.
import json, os, sys, re
from collections import Counter, defaultdict

ROOT = r"D:\PycharmProjects\CodeHarness\master_work\agent-traces\sessions"

def iter_sessions():
    for d in sorted(os.listdir(ROOT)):
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp): continue
        for f in sorted(os.listdir(dp)):
            if f == '.gitkeep': continue
            fp = os.path.join(dp, f)
            yield d, f, fp

def norm_input(inp):
    if not isinstance(inp, dict): return json.dumps(inp, sort_keys=True, ensure_ascii=False)
    out = {}
    for k, v in inp.items():
        if isinstance(v, str):
            v = re.sub(r'\s+', ' ', v).strip()
            if len(v) > 160: v = v[:160]
        out[k] = v
    return json.dumps(out, sort_keys=True, ensure_ascii=False)

def analyze_claude(fp):
    """returns list of events: dicts with role, kind, tool name, input, result, text, error"""
    events = []
    nlines = 0
    with open(fp, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            nlines += 1
            line = line.strip()
            if not line: continue
            try: j = json.loads(line)
            except Exception: events.append({'kind':'parse_error','line':nlines}); continue
            t = j.get('type')
            if t in ('queue-operation','summary','file-history-snapshot','system'): 
                events.append({'kind':'meta','type':t,'line':nlines})
                continue
            if t not in ('user','assistant'):
                events.append({'kind':'meta','type':str(t),'line':nlines}); continue
            msg = j.get('message') or {}
            content = msg.get('content')
            is_sidechain = j.get('isSidechain', False)
            ts = j.get('timestamp')
            if isinstance(content, str):
                events.append({'kind':'text','role':t,'text':content,'line':nlines,'ts':ts,'side':is_sidechain})
                continue
            for item in content or []:
                it = item.get('type')
                if it == 'text':
                    events.append({'kind':'text','role':t,'text':item.get('text',''),'line':nlines,'ts':ts,'side':is_sidechain})
                elif it == 'thinking':
                    events.append({'kind':'thinking','role':t,'text':item.get('thinking',''),'line':nlines,'ts':ts,'side':is_sidechain})
                elif it == 'tool_use':
                    events.append({'kind':'tool_call','role':t,'tool':item.get('name'),'id':item.get('id'),
                                   'inp':item.get('input'),'line':nlines,'ts':ts,'side':is_sidechain})
                elif it == 'tool_result':
                    c = item.get('content')
                    txt = ''
                    if isinstance(c, str): txt = c
                    elif isinstance(c, list):
                        txt = ' '.join(x.get('text','') for x in c if isinstance(x, dict) and x.get('type')=='text')
                    is_err = bool(item.get('is_error'))
                    events.append({'kind':'tool_result','role':t,'for_id':item.get('tool_use_id'),
                                   'text':txt,'is_error':is_err,'line':nlines,'ts':ts,'side':is_sidechain})
                else:
                    events.append({'kind':'other_content','it':str(it),'line':nlines,'ts':ts,'side':is_sidechain})
    return events, nlines

def analyze_cursor(fp):
    events = []; nlines = 0
    with open(fp, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            nlines += 1
            line = line.strip()
            if not line: continue
            try: j = json.loads(line)
            except Exception: events.append({'kind':'parse_error','line':nlines}); continue
            role = j.get('role'); msg = j.get('message') or {}
            for item in msg.get('content') or []:
                it = item.get('type')
                if it == 'text':
                    events.append({'kind':'text','role':role,'text':item.get('text',''),'line':nlines})
                elif it == 'tool_use':
                    events.append({'kind':'tool_call','role':role,'tool':item.get('name'),'id':item.get('id'),
                                   'inp':item.get('input'),'line':nlines})
                elif it == 'tool_result':
                    c = item.get('content'); txt=''
                    if isinstance(c,str): txt=c
                    elif isinstance(c,list):
                        txt=' '.join(x.get('text','') for x in c if isinstance(x,dict) and x.get('type')=='text')
                    events.append({'kind':'tool_result','role':role,'for_id':item.get('tool_use_id'),'text':txt,
                                   'is_error':bool(item.get('is_error')),'line':nlines})
                else:
                    events.append({'kind':'other_content','it':str(it),'line':nlines})
    return events, nlines

def analyze_opencode(fp):
    with open(fp, encoding='utf-8', errors='replace') as fh:
        j = json.load(fh)
    events = []; n = 0
    for m in j.get('messages', []):
        n += 1
        info = m.get('info') or {}
        role = info.get('role')
        for p in m.get('parts') or []:
            pt = p.get('type')
            if pt == 'text':
                events.append({'kind':'text','role':role,'text':p.get('text',''),'line':n})
            elif pt == 'tool':
                st = p.get('state') or {}
                events.append({'kind':'tool_call','role':role,'tool':p.get('tool'),
                               'inp':st.get('input'),'id':p.get('callID'),
                               'text': (st.get('output') or '')[:4000] if st.get('status')!='pending' else '',
                               'is_error': st.get('status')=='error','line':n})
            elif pt == 'reasoning':
                events.append({'kind':'thinking','role':role,'text':p.get('text',''),'line':n})
            else:
                events.append({'kind':'other_content','it':str(pt),'line':n})
    return events, n

def main():
    for d, f, fp in iter_sessions():
        fmt = None
        if d == 'claude_code': fmt='claude'; events, nlines = analyze_claude(fp)
        elif d == 'cursor': fmt='cursor'; events, nlines = analyze_cursor(fp)
        elif d == 'opencode': fmt='opencode'; events, nlines = analyze_opencode(fp)
        else: continue
        # stats
        calls = [e for e in events if e['kind']=='tool_call' and not e.get('side')]
        results = [e for e in events if e['kind']=='tool_result']
        texts = [e for e in events if e['kind']=='text' and e.get('role')=='assistant' and not e.get('side')]
        toolcnt = Counter(c['tool'] for c in calls)
        # repeated identical tool calls
        sig_count = Counter((c['tool'], norm_input(c.get('inp'))) for c in calls)
        repeats = [(s,n) for s,n in sig_count.most_common(8) if n >= 3]
        # errors
        err_results = [r for r in results if r.get('is_error') or re.search(r'\b(Error|error|Traceback|exit code [1-9]|FAILED)\b', (r.get('text') or '')[:400])]
        # repeated tool-name n-grams (consecutive calls, window 4) - loopiness
        seq = [c['tool'] for c in calls]
        ngram4 = Counter(tuple(seq[i:i+4]) for i in range(len(seq)-3))
        top4 = ngram4.most_common(3)
        side = sum(1 for e in events if e.get('side'))
        print("="*100)
        print(f"SESSION {d}/{f}  fmt={fmt} lines={nlines} events={len(events)} sidechain={side}")
        print(f"  tool_calls={len(calls)} assistant_texts={len(texts)} tool_results={len(results)} err_results={len(err_results)}")
        print(f"  tools: {dict(toolcnt.most_common(12))}")
        if repeats: print(f"  REPEAT_SIGS(>=3): " + " | ".join(f"{n}x {s[0]}:{s[1][:110]}" for s,n in repeats[:6]))
        if top4: print(f"  top4grams: {[(c, '>'.join(g)) for g,c in top4]}")

if __name__ == '__main__':
    main()
