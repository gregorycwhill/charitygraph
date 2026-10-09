"""Freeze provider-free packet views and independent reference after central capture."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

def canon(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
def sha(v): return hashlib.sha256(canon(v)).hexdigest()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--cohort',type=Path,required=True); p.add_argument('--retained',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    cohort=json.loads(a.cohort.read_text(encoding='utf8')); acquisition=json.loads((a.retained/'source-attempt-manifest.json').read_text(encoding='utf8'))
    attempts={x['case_id']:x for x in acquisition['attempts']}; packets=[]
    for case in cohort['cases']:
        source=attempts[case['case_id']]
        evidence=[] if source['status']!='captured' else [{k:source[k] for k in ('evidence_fragment_id','raw_blob_id','raw_sha256','representation_id','representation_sha256','fragment_locator','fragment_sha256','source_family','source_role','resolved_locator','retrieved_at','subject_binding')}]
        for section in (15,17):
            material={'case_id':case['case_id'],'subject_id':case['subject_id'],'section':section,'selection_version':f'empirical-{section}-selection-v1','evidence':evidence}
            packets.append({**material,'packet_id':'packet:'+sha(material),'packet_hash':sha(material),'coverage_state':'supportable_regulatory_only' if evidence else 'coverage_gap'})
    corpus={'corpus_id':'empirical-ethos-notability-v1','version':'1.0.0','frozen_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'cohort_sha256':sha(cohort),'source_attempt_manifest_sha256':acquisition['manifest_sha256'],'packet_selection_versions':{'15':'empirical-15-selection-v1','17':'empirical-17-selection-v1'},'packets':packets,'provider_calls':0,'candidate_outputs_present':False}
    corpus['corpus_sha256']=sha(corpus); a.out.mkdir(parents=True,exist_ok=True); (a.out/'frozen-corpus.json').write_bytes(canon(corpus))
    # Deliberately conservative independent reference: regulatory identity alone
    # supports neither a §15 semantic observation nor a §17 notable event.
    reference={'reference_id':'empirical-ethos-notability-v1-independent-reference','label':'independent reference adjudication','created_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'corpus_sha256':corpus['corpus_sha256'],'created_before_candidate_output':True,'human_gold':False,'provider_calls':0,'items':[{'case_id':c['case_id'],'section':s,'disposition':'NOT_EVALUABLE','reason':'frozen retained material is regulatory identity only; no semantic inference permitted','supporting_evidence_ids':[attempts[c['case_id']]['evidence_fragment_id']] if attempts[c['case_id']]['status']=='captured' else [],'forbidden_inferences':['do not infer ethos from beneficiary/community/network identity','do not infer notability from registration or source absence']} for c in cohort['cases'] for s in (15,17)]}
    reference['reference_sha256']=sha(reference); (a.out/'independent-reference-adjudication.json').write_bytes(canon(reference)); print(json.dumps({'corpus_sha256':corpus['corpus_sha256'],'reference_sha256':reference['reference_sha256'],'packets':len(packets)},indent=2))
if __name__=='__main__': main()
