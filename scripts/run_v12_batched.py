"""V12 manifest-led broad harvest with one batched resolver call per packet."""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.document_representation import represent_document
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02,COMPACT_V02_SCHEMA
from charitygraph.scope_resolution_contract import ScopeResolutionOutput,SCOPE_RESOLUTION_SCHEMA
from charitygraph.openai_client import responses_create,estimate_response_cost
ROOT=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v12"); RAW=Path(r"C:\CharityGraph-runtime\prospective-replicates-20260828\evidence-freeze-v1\raw")
TARGETS={'28000030179':'The Smith Family','50169561394':'Australian Red Cross Society','67649417658':'Landscape Recovery Foundation Ltd.','45146631843':'Indigenous Literacy Foundation Ltd.','20077830347':'Australian Communities Foundation Limited','22007498482':'Australian Conservation Foundation Incorporated','15000002522':'Mission Australia','15101252171':'Life Without Barriers','28004778081':'World Vision Australia','46070556642':'The Fred Hollows Foundation'}
CP="Extract all evidence-supported Compact Knowledge v0.2 atoms about the declared target. Scope fields are producer hints only. Use exact dates only when supported; use reporting_period for coarse periods. Cite packet-local locators."
RP="Resolve scope independently using only the declared target, proposition and exact evidence excerpts. Do not use producer scope hints. Generic organisation facts/categories are subject; named_program_or_service requires one specifically named instance; other_named_scope requires one named subordinate thing; reporting_group requires formal evidence; otherwise uncertain. Return one indexed decision per atom."
def main():
 ROOT.mkdir(parents=True,exist_ok=True); manifest=[]; candidates=[]
 for abn,name in TARGETS.items():
  d=RAW/abn
  if not d.exists(): continue
  for f in sorted(d.iterdir()):
   if f.suffix.lower() not in {'.html','.pdf','.txt'} or any(x in f.name.lower() for x in ('abr','acnc-profile','register')): continue
   raw=f.read_bytes(); rep=represent_document(raw,content_type='application/pdf' if f.suffix.lower()=='.pdf' else 'text/html'); ent={'target':name,'abn':abn,'raw_path':str(f),'origin_kind':'existing_runtime_public','source_relation':'first_party','material_role':'annual_report' if 'annual' in f.name.lower() else 'first_party_program','raw_sha256':hashlib.sha256(raw).hexdigest(),'representation_sha256':rep.representation_sha256,'representation_method':rep.method,'complete':rep.complete,'gap':rep.gap,'units':len(rep.units)}; manifest.append(ent)
   if rep.complete: candidates.append((name,abn,f,rep,ent))
 (ROOT/'source-manifest.json').write_text(json.dumps({'authorised_subjects':TARGETS,'entries':manifest},ensure_ascii=False,indent=2),encoding='utf-8'); summary={'campaign':'broad-compact-diagnostic-v12','manifest_entries':len(manifest),'packets':[],'atoms':[],'structured_route_exclusions':[]}; total=0.0; seq=0
 for name,abn,f,rep,ent in candidates:
  lines=[x for x in rep.text.splitlines() if x.strip()]
  for start in range(0,len(lines),max(1, min(80, len(lines)//8 or 1))):
   if seq>=80: break
   seq+=1; chunk=lines[start:start+80]; locs=[{'source':'S001','locator':f'L{i+1:04d}','text':x[:1200]} for i,x in enumerate(chunk)]; packet={'target':{'name':name,'abn':abn},'source':{'publisher':name,'relation':ent['source_relation'],'material_role':ent['material_role'],'original_url':None,'raw_sha256':ent['raw_sha256'],'representation_sha256':ent['representation_sha256'],'parent_document':f.name,'chunk_identity':f'{start+1}-{start+len(chunk)}'},'evidence':locs}; pb=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); psha=hashlib.sha256(pb).hexdigest(); out=ROOT/f'{seq:03d}'; out.mkdir(exist_ok=True); (out/'packet.json').write_bytes(pb)
   r=responses_create(model='gpt-5.6-luna',input_text=CP+'\nDECLARED TARGET: '+name+'\nPACKET:\n'+pb.decode(),text_format={'type':'json_schema','name':'compact_knowledge_v02','strict':True,'schema':COMPACT_V02_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={'effort':'none'}); u=r.usage; c=estimate_response_cost('gpt-5.6-luna',u) or 0; total+=float(c); (out/'compact-raw.json').write_text(json.dumps({'response_id':r.response_id,'status':r.status,'output_text':r.output_text,'usage':u.__dict__},ensure_ascii=False),encoding='utf-8')
   try: parsed=CompactKnowledgeOutputV02.model_validate(json.loads(r.output_text)); valid=True
   except Exception: parsed=None; valid=False
   row={'target':name,'abn':abn,'packet_sha':psha,'raw_sha':ent['raw_sha256'],'representation_sha':ent['representation_sha256'],'status':r.status,'valid':valid,'input_tokens':u.input_tokens,'output_tokens':u.output_tokens,'cost_usd':str(c)}
   if parsed:
    rin=[{'atom_index':i,'proposition':a.proposition,'evidence_items':[{'evidence_index':j,'canonical_ref':f'{e.source}:{e.locator}','exact_excerpt':next((x['text'] for x in locs if x['locator']==e.locator),'')} for j,e in enumerate(a.evidence)]} for i,a in enumerate(parsed.atoms)]
    rr=responses_create(model='gpt-5.6-luna',input_text=RP+'\nTARGET: '+name+'\nATOMS:\n'+json.dumps(rin,ensure_ascii=False),text_format={'type':'json_schema','name':'scope_resolution_v1','strict':True,'schema':SCOPE_RESOLUTION_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={'effort':'none'}); ru=rr.usage; rc=estimate_response_cost('gpt-5.6-luna',ru) or 0; total+=float(rc); row.update({'resolver_status':rr.status,'resolver_input_tokens':ru.input_tokens,'resolver_output_tokens':ru.output_tokens,'resolver_cost_usd':str(rc)})
    summary['packets'].append(row)
    if parsed:
     try: decs=ScopeResolutionOutput.model_validate(json.loads(rr.output_text)).decisions
     except Exception: decs=()
     for i,a in enumerate(parsed.atoms):
      d=next((d.model_dump(mode='json') for d in decs if d.atom_index==i),{'status':'invalid'}); d['canonical_evidence_refs']=[rin[i]['evidence_items'][j]['canonical_ref'] for j in d.get('supporting_evidence_indices',[]) if isinstance(j,int) and j<len(rin[i]['evidence_items'])]; summary['atoms'].append({'task_id':f'v12:{seq}','target':name,'target_abn':abn,'publisher':name,'source_relation':ent['source_relation'],'material_role':ent['material_role'],'origin_kind':'existing_runtime_public','original_url':None,'local_raw_path':str(f),'final_url':None,'raw_sha':ent['raw_sha256'],'representation_sha':ent['representation_sha256'],'parent_document':f.name,'chunk_identity':packet['source']['chunk_identity'],'packet_sha':psha,'raw_compact_atom':a.model_dump(mode='json'),'producer_scope_hint':{'kind':a.scope_kind,'label':a.scope_label},'resolver_evidence_items':rin[i]['evidence_items'],'semantic_resolver':d,'persistence_gate':'diagnostic_only'})
  if seq>=80: break
 (ROOT/'campaign-summary.json').write_text(json.dumps({**summary,'compact_calls':len(summary['packets']),'resolver_calls':sum(1 for p in summary['packets'] if p.get('resolver_status')),'total_cost_usd':str(round(total,6))},ensure_ascii=False,indent=2),encoding='utf-8'); (ROOT/'aggregate-review.json').write_text(json.dumps({'atoms':summary['atoms']},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'compact_calls':len(summary['packets']),'resolver_calls':sum(1 for p in summary['packets'] if p.get('resolver_status')),'atoms':len(summary['atoms']),'cost':round(total,6)}))
if __name__=='__main__': main()
