"""Suggest parent domains conservatively without replacing leaf clusters."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path

def cosine(a, b):
    common = set(a) & set(b)
    dot = sum(a[x] * b[x] for x in common)
    na = math.sqrt(sum(v*v for v in a.values())); nb = math.sqrt(sum(v*v for v in b.values()))
    return dot/(na*nb) if na and nb else 0.0

def main():
    p=argparse.ArgumentParser(); p.add_argument('--cards',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--jaccard',type=float,default=.40); p.add_argument('--cosine',type=float,default=.25); args=p.parse_args()
    cards=json.loads(args.cards.read_text(encoding='utf-8')); candidates=[]
    for i,left in enumerate(cards):
        if left['support']>50: continue
        lv={k:float(v) for k,v in left.get('term_frequency_profile',{}).items() if k in set(left.get('core_terms',[]))}
        lm=set(left['member_slice_ids'])
        for right in cards[i+1:]:
            if right['support']>50: continue
            rv={k:float(v) for k,v in right.get('term_frequency_profile',{}).items() if k in set(right.get('core_terms',[]))}
            rm=set(right['member_slice_ids']); jac=len(lm&rm)/len(lm|rm) if lm|rm else 0
            sim=cosine(lv,rv)
            if jac>=args.jaccard or sim>=args.cosine:
                candidates.append({'left':left['domain_id'],'right':right['domain_id'],'member_jaccard':round(jac,4),'core_profile_cosine':round(sim,4),'reason':'parent_candidate_only'})
    out={'algorithm_version':'domain-parent-candidates-v1','leaf_clusters_preserved':True,'candidate_count':len(candidates),'candidates':candidates}
    args.output.mkdir(parents=True,exist_ok=True); (args.output/'parent-candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:v for k,v in out.items() if k!='candidates'},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
