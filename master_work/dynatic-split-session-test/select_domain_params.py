"""Select domain graph parameters by scanning data-derived threshold candidates."""
from __future__ import annotations
import argparse, json, math, tempfile
from pathlib import Path
from unsupervised_domain_graph import discover

def main():
    p=argparse.ArgumentParser(); p.add_argument('--slice-dir',type=Path,required=True); p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    candidates=[0.45,0.50,0.55,0.60,0.65]
    rows=[]
    with tempfile.TemporaryDirectory() as temp:
        for threshold in candidates:
            out=Path(temp)/f't{threshold:.2f}'
            summary=discover(args.slice_dir,out,300,threshold,3,0.03)
            domain_rows=json.loads((out/'domains.json').read_text(encoding='utf-8'))
            sizes=[d['support'] for d in domain_rows]
            max_share=max(sizes,default=0)/summary['slice_count']
            assigned=summary['slice_count']-summary['unassigned_slice_count']
            avg_cov=sum(d['average_information_coverage'] for d in domain_rows)/len(domain_rows) if domain_rows else 0
            # Reward several non-dominant, information-complete domains and
            # penalize a giant component or total abstention.
            score=(math.log1p(len(domain_rows))*0.35 + avg_cov*4.0
                   + (assigned/summary['slice_count'])*0.25 - max_share*0.5)
            rows.append({'threshold':threshold,'domain_count':len(domain_rows),'assigned':assigned,'unassigned':summary['unassigned_slice_count'],'max_cluster_share':round(max_share,6),'average_coverage':round(avg_cov,6),'score':round(score,6)})
    chosen=max(rows,key=lambda row:row['score'])
    args.output.mkdir(parents=True,exist_ok=True)
    result={'algorithm_version':'domain-parameter-selection-v1','candidates':rows,'selected':chosen,'selection_rule':'scan thresholds and score domain count, coverage, assignment, and giant-cluster penalty'}
    (args.output/'selection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
