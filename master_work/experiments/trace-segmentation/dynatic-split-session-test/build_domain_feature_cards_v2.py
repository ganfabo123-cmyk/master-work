"""Build compact, contrastive domain cards for the LLM normalizer."""
from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def main():
    base=Path('master_work/experiments/trace-segmentation/dynatic-split-session-test'); seg=base/'token-frequency-banded-v3-exclusive-no-symbols/segments'
    domains=read(base/'unsupervised-domain-complete-v6/domains.json')
    openings={x['slice_file'].split('\\')[-1].removesuffix('.json'):x for x in read(base/'slice-opening-analysis/slice-opening-analysis.json')}
    tools={x['slice_id']:x for x in (json.loads(line) for line in (base/'tool-operation-signals/slice-tool-signals.jsonl').read_text(encoding='utf-8').splitlines())}
    term_df=Counter(); raw={}; member_sets={}; slice_count=0
    global_slice_df=Counter()
    for p in sorted(seg.glob('*.json')):
        slice_count += 1
        global_slice_df.update(read(p).get('token_frequencies',{}).keys())
    for d in domains:
        ids=[x.removeprefix('segments__') for x in d['members']]; member_sets[d['domain_id']]=set(ids); counts=Counter()
        for sid in ids:
            p=seg/f'{sid}.json'
            if p.exists(): counts.update(read(p).get('token_frequencies',{}))
        raw[d['domain_id']]=counts; term_df.update(counts.keys())
    cards=[]
    for d in domains:
        did=d['domain_id']; ids=sorted(member_sets[did]); counts=raw[did]
        # Rank terms with corpus-derived IDF. No manually maintained domain dictionary.
        def idf(term):
            return math.log((slice_count + 1) / (global_slice_df[term] + 1)) + 1.0
        ranked=sorted(counts, key=lambda t: counts[t] * idf(t), reverse=True)
        original_core=[t for t in d['terms'] if global_slice_df[t] <= max(1, math.ceil(slice_count * .5))]
        core_list=sorted(original_core, key=lambda t: counts[t] * idf(t), reverse=True)[:30]
        if len(core_list) < 3:
            core_list=sorted(d['terms'], key=lambda t: counts[t] * idf(t), reverse=True)[:10]
        core=set(core_list)
        generic=[t for t in ranked if global_slice_df[t] >= math.ceil(slice_count * .5)][:50]
        # Distinctive means supported by this domain and rare in the whole corpus.
        domain_slice_df=Counter()
        for sid in ids:
            p=seg/f'{sid}.json'
            if p.exists(): domain_slice_df.update(read(p).get('token_frequencies',{}).keys())
        distinct=[t for t in ranked if domain_slice_df[t] >= max(2, math.ceil(len(ids)*.1)) and global_slice_df[t] <= max(2, math.ceil(slice_count*.25))][:50]
        extended=[t for t in ranked if t not in core and t not in generic][:80]
        op=Counter(); targets=Counter(); types=Counter()
        for sid in ids:
            row=tools.get(sid,{})
            op.update(row.get('operation_events',{})); targets.update(row.get('target_events',{})); types.update(row.get('file_type_events',{}))
        evidence=[f'operation:{k}' for k,_ in op.most_common(8)] + [f'file:{k}' for k,_ in types.most_common(8)] + [f'target:{k}' for k,_ in targets.most_common(8)]
        reps=[]
        for sid in ids:
            p=seg/f'{sid}.json'; c=read(p).get('token_frequencies',{}) if p.exists() else {}; matched={t:int(c.get(t,0)) for t in core if int(c.get(t,0))>0}
            if sid in openings and openings[sid].get('first_sentence'): reps.append((sum(matched.values()),sid,matched))
        representatives=[]
        for _score,sid,matched in sorted(reps,reverse=True)[:5]: representatives.append({'slice_id':sid,'first_sentence':openings[sid]['first_sentence'][:300],'matched_core_terms':sorted(matched,key=matched.get,reverse=True)})
        overlaps=[]
        for other, members in member_sets.items():
            if other==did: continue
            j=len(member_sets[did]&members)/len(member_sets[did]|members) if member_sets[did]|members else 0
            overlaps.append((j,other))
        cards.append({'cluster_id':did,'support':len(ids),'session_count':len({x.rsplit('__segment-',1)[0] for x in ids}),'information_coverage':d['average_information_coverage'],'core_terms':core_list,'extended_terms':extended,'distinctive_terms':distinct,'generic_terms':generic,'file_tool_evidence':evidence[:20],'representative_inputs':representatives,'overlaps':[{'cluster_id':o,'member_jaccard':round(j,4)} for j,o in sorted(overlaps,reverse=True)[:3]],'member_slice_ids':ids})
    out=base/'domain-feature-cards-v2'; out.mkdir(parents=True,exist_ok=True)
    (out/'domain-feature-cards.json').write_text(json.dumps(cards,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'summary.json').write_text(json.dumps({'algorithm_version':'domain-feature-cards-v2-idf','cluster_count':len(cards),'fields':['core_terms','extended_terms','distinctive_terms','generic_terms','file_tool_evidence','representative_inputs','overlaps'],'term_weighting':'corpus-derived tf-idf; generic terms selected by corpus slice coverage'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cluster_count':len(cards),'output':str(out)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
