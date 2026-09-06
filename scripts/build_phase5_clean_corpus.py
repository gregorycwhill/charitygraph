"""Offline construction of the governed clean Phase-5 corpus with explicit gaps."""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from charitygraph.baseline_corpus import AcquisitionState, BindingState, CorpusMember, DiscoveryState, MaterialOrigin, RepresentationReadiness, build_corpus_manifest

FAMILIES=("acnc_register","acnc_ais_bundle","ato_abr_dgr","official_website","annual_report","wikipedia_wikimedia","pfra")
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding='utf-8')
def gap(template,family,state,reason):
    return CorpusMember(source_family=family,source_definition_id=template.source_definition_id,discovery=DiscoveryState.RESOLVED,acquisition=AcquisitionState.UNAVAILABLE,subject_binding=BindingState.NONE,material_origin=MaterialOrigin.NONE,representation_readiness=RepresentationReadiness.NOT_ATTEMPTED,representation_gaps=(state,reason))
def main():
 root=Path(r'C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1'); clean=Path(r'C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean')
 inv={(x['abn'],x['source_family']):x for x in read(clean/'corrected-pre-run-source-inventory.json')['cells']}; web={x.get('abn'):x for x in read(clean/'blocked-run-website-admissibility-ledger.json')['website_events'] if x.get('abn')}
 rows=[]; hashes=[]
 for p in sorted((root/'corpora').glob('*.json')):
  old=read(p); abn=p.stem; members=[]; coverage={}
  for mraw in old['material_members']:
   m=CorpusMember.model_validate(mraw); f=m.source_family; prior=inv[(abn,f)]; keep=m.acquisition in {AcquisitionState.AVAILABLE,AcquisitionState.PARTIAL}
   state='acquired_available'
   if f in {'acnc_register','acnc_ais_bundle','ato_abr_dgr'} and prior['state']!='acquired_available' and f!='ato_abr_dgr': keep=False; state=prior['state']
   if f=='official_website':
    decision=web.get(abn); keep=prior['state']=='acquired_available' or bool(decision and decision['permitted_in_clean_corpus']); state='acquired_available' if keep else prior['state']
   if not keep: m=gap(m,f,state,'excluded_or_unresolved_clean_lineage')
   members.append(m); coverage[f]={'state':state if keep else state,'binding':m.subject_binding.value,'positive':keep}
  manifest=build_corpus_manifest(subject_id=old['subject_id'],profile_version='phase5-top100-baseline-corpus-v1-clean',members=members,cohort_id=old['cohort_id'],run_id='phase5-top100-baseline-corpus-v1-clean',retrieval_timestamps=(),builder_commit=None)
  write(clean/'corpora'/p.name,manifest.model_dump(mode='json')); rows += [dict(abn=abn,subject_id=old['subject_id'],source_family=f,**coverage[f]) for f in FAMILIES]; hashes.append({'abn':abn,'material_identity_hash':manifest.material_identity_hash,'provenance_hash':manifest.provenance_hash})
 write(clean/'clean-source-coverage-matrix.json',rows); write(clean/'clean-corpus-hash-index.json',hashes); write(clean/'clean-corpus-summary.json',{'manifests':len(hashes),'cells':len(rows),'coverage':Counter(x['state'] for x in rows),'network_calls':0,'provider_calls':0,'semantic_executions':0})
if __name__=='__main__': main()
