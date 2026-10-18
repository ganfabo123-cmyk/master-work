"""Apply a small LLM-produced domain normalization to preserve trace evidence."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--domains',type=Path,required=True); p.add_argument('--normalization',type=Path,required=True); p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    source=json.loads(args.domains.read_text(encoding='utf-8'))
    normalized=json.loads(args.normalization.read_text(encoding='utf-8'))
    by_id={d['domain_id']:d for d in source}
    result=[]
    for domain in normalized.get('domains',[]):
        members=[]; source_terms=[]; source_ids=[]
        for source_id in domain.get('source_clusters',[]):
            if source_id not in by_id: continue
            item=by_id[source_id]; source_ids.append(source_id)
            members.extend(item.get('members',[])); source_terms.extend(item.get('terms',[]))
        result.append({
            'domain_id':domain['domain_id'],
            'name':domain['name'],
            'source_clusters':source_ids,
            'core_terms':domain.get('core_terms',[]),
            'source_terms':sorted(set(source_terms)),
            'member_slice_ids':sorted(set(members)),
            'support':len(set(members)),
            'split_hint':domain.get('split_hint',''),
        })
    mixed=[]
    mixed_ids = list(normalized.get('discard_or_mixed', [])) + [item.get('cluster_id') for item in normalized.get('mixed_clusters', [])]
    for source_id in mixed_ids:
        if source_id in by_id:
            mixed.append({'source_cluster':source_id,'member_slice_ids':by_id[source_id].get('members',[]),'support':len(by_id[source_id].get('members',[]))})
    output={'algorithm_version':'llm-assisted-domain-normalization-v1','llm_fields_used':['name','source_clusters','core_terms','split_hint','discard_or_mixed'],'domains':result,'mixed_or_unresolved':mixed}
    assigned={slice_id for domain in result for slice_id in domain['member_slice_ids']}
    summary={'domain_count':len(result),'mixed_cluster_count':len(mixed),'assigned_slice_count':len(assigned),'overlap_count':sum(d['support'] for d in result)-len(assigned)}
    args.output.mkdir(parents=True,exist_ok=True); (args.output/'domains.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
