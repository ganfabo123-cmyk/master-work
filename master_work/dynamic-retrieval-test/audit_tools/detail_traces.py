# -*- coding: utf-8 -*-
# Read-only detail viewer: python detail.py <session_file> [mode]
# mode=seq  : print compact event sequence (tool calls with short inputs, results with first 200 chars, texts with first 300 chars)
# mode=errs : print only error tool_results with 400 chars
# mode=sig  : print all occurrences of repeated identical calls with their results
import json, os, sys, re

def load_events(fp):
    d = os.path.basename(os.path.dirname(fp))
    events = []
    if d == 'claude_code':
        with open(fp, encoding='utf-8', errors='replace') as fh:
            for n, line in enumerate(fh, 1):
                line = line.strip()
                if not line: continue
                try: j = json.loads(line)
                except Exception: continue
                t = j.get('type')
                if t not in ('user','assistant'): continue
                msg = j.get('message') or {}
                ts = j.get('timestamp','')
                side = j.get('isSidechain', False)
                content = msg.get('content')
                if isinstance(content, str):
                    events.append({'kind':'text','role':t,'text':content,'line':n,'ts':ts,'side':side}); continue
                for item in content or []:
                    it = item.get('type')
                    if it == 'text':
                        events.append({'kind':'text','role':t,'text':item.get('text',''),'line':n,'ts':ts,'side':side})
                    elif it == 'thinking':
                        events.append({'kind':'thinking','role':t,'text':item.get('thinking',''),'line':n,'ts':ts,'side':side})
                    elif it == 'tool_use':
                        events.append({'kind':'tool_call','role':t,'tool':item.get('name'),'id':item.get('id'),
                                       'inp':item.get('input'),'line':n,'ts':ts,'side':side})
                    elif it == 'tool_result':
                        c = item.get('content'); txt=''
                        if isinstance(c,str): txt=c
                        elif isinstance(c,list):
                            txt=' '.join(x.get('text','') for x in c if isinstance(x,dict) and x.get('type')=='text')
                        events.append({'kind':'tool_result','role':t,'for_id':item.get('tool_use_id'),'text':txt,
                                       'is_error':bool(item.get('is_error')),'line':n,'ts':ts,'side':side})
    elif d == 'cursor':
        with open(fp, encoding='utf-8', errors='replace') as fh:
            for n, line in enumerate(fh, 1):
                line=line.strip()
                if not line: continue
                try: j=json.loads(line)
                except Exception: continue
                role=j.get('role')
                for item in (j.get('message') or {}).get('content') or []:
                    it=item.get('type')
                    if it=='text': events.append({'kind':'text','role':role,'text':item.get('text',''),'line':n})
                    elif it=='tool_use': events.append({'kind':'tool_call','role':role,'tool':item.get('name'),'id':item.get('id'),'inp':item.get('input'),'line':n})
                    elif it=='tool_result':
                        c=item.get('content'); txt=''
                        if isinstance(c,str): txt=c
                        elif isinstance(c,list): txt=' '.join(x.get('text','') for x in c if isinstance(x,dict) and x.get('type')=='text')
                        events.append({'kind':'tool_result','role':role,'for_id':item.get('tool_use_id'),'text':txt,'is_error':bool(item.get('is_error')),'line':n})
    elif d == 'opencode':
        with open(fp, encoding='utf-8', errors='replace') as fh:
            j=json.load(fh)
        n=0
        for m in j.get('messages', []):
            n+=1
            role=(m.get('info') or {}).get('role')
            for p in m.get('parts') or []:
                pt=p.get('type')
                if pt=='text': events.append({'kind':'text','role':role,'text':p.get('text',''),'line':n})
                elif pt=='tool':
                    st=p.get('state') or {}
                    out=st.get('output') or ''
                    events.append({'kind':'tool_call','role':role,'tool':p.get('tool'),'id':p.get('callID'),'inp':st.get('input'),'line':n})
                    if out: events.append({'kind':'tool_result','role':'user','text':out,'is_error':st.get('status')=='error','line':n})
                elif pt=='reasoning': events.append({'kind':'thinking','role':role,'text':p.get('text',''),'line':n})
    return events

def shorten(s, n=200):
    s = re.sub(r'\s+',' ', s or '').strip()
    return s[:n]

def main():
    fp = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv)>2 else 'seq'
    events = load_events(fp)
    # map id->result for claude format
    byid = {e['for_id']: e for e in events if e['kind']=='tool_result' and e.get('for_id')}
    if mode == 'seq':
        for e in events:
            ln = e['line']
            if e['kind']=='tool_call':
                inp = shorten(json.dumps(e.get('inp'), ensure_ascii=False), 150)
                print(f"L{ln} CALL {e['tool']} {inp}")
            elif e['kind']=='tool_result':
                flag = 'ERR' if e.get('is_error') else 'res'
                print(f"L{ln}   {flag}: {shorten(e.get('text',''),220)}")
            elif e['kind']=='text':
                print(f"L{ln} {e['role'].upper()} TXT: {shorten(e.get('text',''),350)}")
            elif e['kind']=='thinking':
                print(f"L{ln} {e['role'].upper()} THK: {shorten(e.get('text',''),200)}")
    elif mode == 'errs':
        for e in events:
            if e['kind']=='tool_result' and (e.get('is_error') or re.search(r'error|Error|ERROR|Traceback|FAILED|failed', (e.get('text') or '')[:300])):
                # find call
                call = byid.get(e.get('for_id'))
                ci = ''
                if call and 'tool' in call: ci = f"{call['tool']} {shorten(json.dumps(call.get('inp'),ensure_ascii=False),180)}"
                print(f"L{e['line']} [{ci}]")
                print(f"   => {shorten(e.get('text',''),500)}")
    elif mode == 'sig':
        from collections import Counter
        def norm(inp):
            if not isinstance(inp, dict): return json.dumps(inp, sort_keys=True, ensure_ascii=False)
            out={}
            for k,v in inp.items():
                if isinstance(v,str):
                    v=re.sub(r'\s+',' ',v).strip()
                    if len(v)>160: v=v[:160]
                out[k]=v
            return json.dumps(out, sort_keys=True, ensure_ascii=False)
        calls=[e for e in events if e['kind']=='tool_call' and not e.get('side')]
        cnt=Counter((c['tool'],norm(c.get('inp'))) for c in calls)
        for c in calls:
            key=(c['tool'],norm(c.get('inp')))
            if cnt[key]>=3:
                res=byid.get(c.get('id'))
                rtext=shorten(res.get('text',''),180) if res else '(no result)'
                rflag='ERR' if (res and res.get('is_error')) else 'ok '
                print(f"L{c['line']} {c['tool']} {key[1][:120]} => {rflag} {rtext}")

if __name__=='__main__':
    main()
