"""Manifest-led V12 ten-charity raw-document Compact harvest."""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,"src")
from charitygraph.document_representation import represent_document
from charitygraph.compact_knowledge import CompactKnowledgeOutputV02,COMPACT_V02_SCHEMA
from charitygraph.scope_resolution_contract import ScopeResolutionOutput,SCOPE_RESOLUTION_SCHEMA
from charitygraph.openai_client import responses_create,estimate_response_cost

ROOT=Path(r"C:\CharityGraph-runtime\broad-compact-diagnostic-v12"); RAW=Path(r"C:\CharityGraph-runtime\prospective-replicates-20260828\evidence-freeze-v1\raw")
COHORT=Path(r"C:\CharityGraph-runtime\prospective-replicates-20260828\cohort-manifest.json")
COMPACT_PROMPT="""Extract all evidence-supported Compact Knowledge v0.2 atoms about the declared target from this bounded source packet. Scope fields are producer hints only. Use exact dates only when supported by cited text; preserve coarse periods in reporting_period. Cite exact packet-local evidence locators and preserve source-native attribution."""
RESOLVE_PROMPT="""Resolve scope independently using only the declared target, proposition and exact evidence excerpts. Do not use producer scope hints. Generic organisation facts/categories are subject; named_program_or_service requires one specifically named instance; other_named_scope requires one named subordinate thing; reporting_group requires formal evidence; otherwise uncertain. Return indexed evidence references."""
def names():
    try: return {str(x['abn']):x['charity_name'] for x in json.loads(COHORT.read_text(encoding='utf-8'))['selected']}
    except Exception: return {}
def main():
    nm=names(); files=[]; manifest=[]; failures=[]
    allowed=set(nm)
    for abn in sorted(allowed):
        d=RAW/abn
        if not d.exists(): continue
        for f in sorted(d.iterdir()):
            if f.suffix.lower() not in {'.html','.pdf','.txt'}: continue
            role='structured_registry' if any(x in f.name.lower() for x in ('abr','acnc-profile','register')) else ('annual_report' if 'annual' in f.name.lower() else 'first_party_program')
            if role=='structured_registry': manifest.append({'target':nm[abn],'abn':abn,'raw_path':str(f),'origin_kind':'existing_runtime_public','source_relation':'first_party','material_role':role,'route':'structured_route_not_transmitted'}); continue
            raw=f.read_bytes(); rep=represent_document(raw,content_type='application/pdf' if f.suffix.lower()=='.pdf' else 'text/html'); manifest.append({'target':nm[abn],'abn':abn,'raw_path':str(f),'origin_kind':'existing_runtime_public','source_relation':'first_party','material_role':role,'route':'compact' if rep.complete else 'representation_failure','raw_sha256':hashlib.sha256(raw).hexdigest(),'representation_sha256':rep.representation_sha256,'representation_method':rep.method,'representation_complete':rep.complete,'representation_gap':rep.gap,'units':len(rep.units)})
            if rep.complete and rep.text.strip(): files.append((nm[abn],abn,f,rep,role))
            elif not rep.complete: failures.append({'path':str(f),'reason':rep.gap})
    # deterministic bounded selection: up to 8 substantive artefacts per authorised subject
    chosen=[]; counts={}
    for item in files:
        if counts.get(item[1],0)>=8: continue
        counts[item[1]]=counts.get(item[1],0)+1; chosen.append(item)
    RUNTIME=ROOT; RUNTIME.mkdir(parents=True,exist_ok=True); (RUNTIME/'source-manifest.json').write_text(json.dumps({'subjects':sorted(nm.values()),'entries':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'campaign':'broad-compact-diagnostic-v12','authorised_subjects':sorted(nm.values()),'manifest_entries':len(manifest),'structured_route_exclusions':[x for x in manifest if x.get('route')=='structured_route_not_transmitted'],'representation_failures':failures,'packets':[],'atoms':[]}; total=0.0
    for idx,(target,abn,f,rep,role) in enumerate(chosen,1):
        text=rep.text; chunk=text[:24000]; lines=[x for x in chunk.splitlines() if x.strip()]; locs=[{'source':'S001','locator':f'L{i+1:04d}','text':x[:1000]} for i,x in enumerate(lines)]; packet={'target':{'name':target,'abn':abn},'source':{'publisher':target,'relation':'first_party','material_role':role,'original_url':None,'final_url':None,'raw_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'representation_sha256':rep.representation_sha,'parent_document':f.name,'chunk_identity':'01'},'evidence':locs}; pb=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); psha=hashlib.sha256(pb).hexdigest(); d=ROOT/f'{idx:03d}'; d.mkdir(exist_ok=True); (d/'packet.json').write_bytes(pb); (d/'prompt.txt').write_text(COMPACT_PROMPT,encoding='utf-8')
        resp=responses_create(model='gpt-5.6-luna',input_text=COMPACT_PROMPT+'\nDECLARED TARGET: '+target+'\nPACKET:\n'+pb.decode(),text_format={'type':'json_schema','name':'compact_knowledge_v02','strict':True,'schema':COMPACT_V02_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={'effort':'none'}); u=resp.usage; cost=estimate_response_cost('gpt-5.6-luna',u) or 0; total+=float(cost); (d/'compact-raw.json').write_text(json.dumps({'response_id':resp.response_id,'status':resp.status,'output_text':resp.output_text,'usage':u.__dict__},ensure_ascii=False,indent=2),encoding='utf-8')
        try: parsed=CompactKnowledgeOutputV02.model_validate(json.loads(resp.output_text)); valid=True
        except Exception: parsed=None; valid=False
        summary['packets'].append({'target':target,'raw_path':str(f),'raw_sha':packet['source']['raw_sha256'],'representation_sha':rep.representation_sha,'packet_sha':psha,'status':resp.status,'valid':valid,'input_tokens':u.input_tokens,'output_tokens':u.output_tokens,'cost_usd':str(cost)})
        if parsed is None: continue
        # one resolver call per packet, with indexed exact excerpts; producer hints are excluded
        resolver_input=[{'atom_index':i,'proposition':a.proposition,'evidence_items':[{'evidence_index':j,'canonical_ref':f'{e.source}:{e.locator}','exact_excerpt':next((x['text'] for x in locs if x['locator']==e.locator),'')} for j,e in enumerate(a.evidence)]} for i,a in enumerate(parsed.atoms)]
        rr=responses_create(model='gpt-5.6-luna',input_text=RESOLVE_PROMPT+'\nTARGET: '+target+'\nATOMS:\n'+json.dumps(resolver_input,ensure_ascii=False),text_format={'type':'json_schema','name':'scope_resolution_v1','strict':True,'schema':SCOPE_RESOLUTION_SCHEMA},max_output_tokens=7000,max_attempts=1,timeout_seconds=300,reasoning={'effort':'none'}); ru=rr.usage; rc=estimate_response_cost('gpt-5.6-luna',ru) or 0; total+=float(rc)
        try: decisions=ScopeResolutionOutput.model_validate(json.loads(rr.output_text)).decisions
        except Exception: decisions=()
        for i,a in enumerate(parsed.atoms):
            dec=next((x.model_dump(mode='json') for x in decisions if x.atom_index==i),{'status':'invalid'}); refs=[resolver_input[i]['evidence_items'][j]['canonical_ref'] for j in dec.get('supporting_evidence_indices',[]) if isinstance(j,int) and j<len(resolver_input[i]['evidence_items'])]; dec['canonical_evidence_refs']=refs
            summary['atoms'].append({'task_id':f'v12:{idx}','target':target,'target_binding_status':'manifest_bound','publisher':target,'source_relation':'first_party','material_role':role,'origin_kind':'existing_runtime_public','original_url':None,'local_raw_path':str(f),'final_url':None,'raw_sha':packet['source']['raw_sha256'],'representation_sha':rep.representation_sha,'parent_document':f.name,'chunk_identity':'01','packet_sha':psha,'raw_compact_atom':a.model_dump(mode='json'),'producer_scope_hint':{'kind':a.scope_kind,'label':a.scope_label},'resolver_evidence_items':resolver_input[i]['evidence_items'],'semantic_resolver':dec,'persistence_gate':'diagnostic_only'})
        summary['packets'][-1]['resolver_status']=rr.status; summary['packets'][-1]['resolver_cost_usd']=str(rc)
    summary['total_cost_usd']=str(round(total,6)); summary['compact_calls']=len(summary['packets']); summary['resolver_calls']=sum(1 for p in summary['packets'] if p.get('resolver_status')); (ROOT/'campaign-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); (ROOT/'aggregate-review.json').write_text(json.dumps({'atoms':summary['atoms']},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'compact_calls':summary['compact_calls'],'resolver_calls':summary['resolver_calls'],'atoms':len(summary['atoms']),'cost':summary['total_cost_usd']},indent=2))
if __name__=='__main__': main()
