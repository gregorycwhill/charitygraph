"""Sequential, private Native-induction v2 workshop (Lab only)."""
from __future__ import annotations
import hashlib,json,time
from collections import Counter,defaultdict
from pathlib import Path
from charitygraph.openai_client import responses_create, estimate_response_cost
from run_native_induction_v1 import load_observations

ROOT=Path(r"C:\CharityGraph-runtime\native-induction-v2-workshop"); MAX_OUTPUT=6000; MODEL="gpt-5.6-luna"
V1=Path(r"C:\CharityGraph-runtime\native-induction-v1\analysis.json")

def _arr(item): return {"type":"array","items":item}
DISC_SCHEMA={"type":"object","additionalProperties":False,"required":["concepts","attachments","recommendations","missing_concept_suggestions"],"properties":{"concepts":_arr({"type":"object","additionalProperties":False,"required":["concept_id","preferred_label","definition","inclusion_boundary","exclusion_boundary","supporting_observation_ids","organisations","parent_concept_candidate","uncertainty"],"properties":{"concept_id":{"type":"string"},"preferred_label":{"type":"string"},"definition":{"type":"string"},"inclusion_boundary":{"type":"string"},"exclusion_boundary":{"type":"string"},"supporting_observation_ids":_arr({"type":"string"}),"organisations":_arr({"type":"string"}),"parent_concept_candidate":{"type":["string","null"]},"uncertainty":{"type":"string"}}}),"attachments":_arr({"type":"string"}),"recommendations":_arr({"type":"string"}),"missing_concept_suggestions":_arr({"type":"string"})}}
TEND_SCHEMA={"type":"object","additionalProperties":False,"required":["concepts","attachments","recommendations","missing_concept_suggestions"],"properties":{"concepts":_arr({"type":"string"}),"attachments":_arr({"type":"string"}),"recommendations":_arr({"type":"object","additionalProperties":False,"required":["action","predecessor_ids","successor_ids","rationale"],"properties":{"action":{"type":"string"},"predecessor_ids":_arr({"type":"string"}),"successor_ids":_arr({"type":"string"}),"rationale":{"type":"string"}}}),"missing_concept_suggestions":_arr({"type":"string"})}}
ATTACH_SCHEMA={"type":"object","additionalProperties":False,"required":["concepts","attachments","recommendations","missing_concept_suggestions"],"properties":{"concepts":_arr({"type":"string"}),"attachments":_arr({"type":"object","additionalProperties":False,"required":["observation_id","concept_ids","support_rationale","missing_concept_suggestion","ambiguity_note"],"properties":{"observation_id":{"type":"string"},"concept_ids":_arr({"type":"string"}),"support_rationale":{"type":"string"},"missing_concept_suggestion":{"type":["string","null"]},"ambiguity_note":{"type":["string","null"]}}}),"recommendations":_arr({"type":"string"}),"missing_concept_suggestions":_arr({"type":"string"})}}
DISC_PROMPT="""Private CharityGraph Native induction workshop. Use only the taxonomy-blind governed observations and current provisional catalogue supplied. Attach observations only when directly supported; leave others unassigned. Propose reusable provisional native concepts for recurring semantic objects, with concept_id, preferred_label, definition, inclusion_boundary, exclusion_boundary, supporting_observation_ids, organisations, parent_concept_candidate and uncertainty. Do not use or reproduce ACNC, CLASSIE, SDG or any external taxonomy or outside knowledge. Preserve activity/output/outcome/impact, operator/deliverer/funder/sponsor/partner/auspice/network, fundraising/expenditure, purpose/activity, ethos/conduct and commitment/implementation distinctions. Return the required JSON shape."""
ATTACH_PROMPT="""Private CharityGraph Native attachment pass. Using only the frozen provisional catalogue and supplied observations, return one attachment item per observation with observation_id, concept_ids (possibly empty), short rationale, missing_concept_suggestion (possibly null) and ambiguity_note (possibly null). Do not modify concepts or use external taxonomies."""
TEND_PROMPT="""Private CharityGraph Native catalogue tending. Review the provisional concepts and evidence supplied. Return explicit recommendations only: retain, rename, redefine, merge, split, reparent or deprecate, with predecessor/successor concept IDs and rationale. Do not silently mutate concepts and do not use external taxonomies."""

def projection(r): return {k:r.get(k) for k in ("observation_id","subject","section_id","scope","proposition","epistemic_status","temporal_scope","evidence","qualifications")}
def call(label,prompt,payload):
    text=prompt+"\nINPUT:\n"+json.dumps(payload,ensure_ascii=False,separators=(",",":")); started=time.perf_counter()
    try:
        schema=ATTACH_SCHEMA if ('attach' in label or 'residual' in label) else (TEND_SCHEMA if 'tending' in label or 'boundary' in label else DISC_SCHEMA)
        resp=responses_create(model=MODEL,input_text=text,text_format={"type":"json_schema","name":"native_v2_workshop","strict":True,"schema":schema},max_output_tokens=MAX_OUTPUT,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none"})
        meta={"label":label,"response_id":resp.response_id,"status":resp.status,"input_tokens":resp.usage.input_tokens,"output_tokens":resp.usage.output_tokens,"cost_usd":str(estimate_response_cost(MODEL,resp.usage) or 0),"latency_seconds":round(time.perf_counter()-started,3)}
        out=json.loads(resp.output_text); valid=True
    except Exception as e:
        meta={"label":label,"status":"mechanical_failure","error_class":type(e).__name__,"error":str(e)[:300],"input_tokens":None,"output_tokens":None,"cost_usd":"0","latency_seconds":round(time.perf_counter()-started,3)}; out={"concepts":[],"attachments":[],"recommendations":[],"missing_concept_suggestions":[]}; valid=False
    (ROOT/f"{label}.json").write_text(json.dumps({"metadata":meta,"valid_json":valid,"output":out},ensure_ascii=False,indent=2),encoding="utf-8"); return out,meta
def main():
    ROOT.mkdir(parents=True,exist_ok=True); obs=load_observations(); by=defaultdict(list)
    for o in obs: by[o['subject']].append(o)
    salt="native-v2-workshop-20260904"; hold=[]; work=[]
    for o in obs:
        h=int(hashlib.sha256((salt+o['observation_id']).encode()).hexdigest(),16)%10
        (hold if h<2 else work).append(o)
    if not hold: raise SystemExit('empty holdout')
    (ROOT/'partition.json').write_text(json.dumps({'salt':salt,'rule':'sha256(salt + observation_id) mod 10 < 2 => final holdout','eligible':len(obs),'workshop':len(work),'holdout':len(hold),'organisations':sorted(by),'workshop_by_org':dict(Counter(o['subject'] for o in work)),'holdout_by_org':dict(Counter(o['subject'] for o in hold))},indent=2),encoding='utf-8')
    v1=json.loads(V1.read_text(encoding='utf-8')); catalogue=[dict(c, lineage=['inherited_v1_seed']) for c in v1['concepts']]; snapshots=[]; metas=[]; recs=[]
    batches=[work[i::7] for i in range(7)]
    for i,batch in enumerate(batches,1):
        out,meta=call(f'discovery-{i:02d}',DISC_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in batch]}); metas.append(meta)
        for c in out.get('concepts',[]):
            if isinstance(c,dict) and c.get('concept_id') and c.get('preferred_label') and not any(x.get('concept_id')==c.get('concept_id') for x in catalogue): catalogue.append(dict(c,lineage=['newly_induced',f'discovery-{i:02d}']))
        recs.extend(out.get('recommendations',[])); snapshots.append({'stage':f'discovery-{i:02d}','concept_count':len(catalogue)})
        if i==3:
            out,meta=call('tending-A',TEND_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in work],'boundary_tensions':out.get('recommendations',[])}); metas.append(meta); recs.extend(out.get('recommendations',[])); snapshots.append({'stage':'tending-A','concept_count':len(catalogue)})
    out,meta=call('tending-B',TEND_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in work]}); metas.append(meta); recs.extend(out.get('recommendations',[])); snapshots.append({'stage':'tending-B','concept_count':len(catalogue)})
    # frozen workshop attachment sweep in six sequential batches
    attachments=[]; missing=[]
    for i,batch in enumerate([work[i::6] for i in range(6)],1):
        out,meta=call(f'workshop-attach-{i:02d}',ATTACH_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in batch]}); metas.append(meta); attachments.extend(out.get('attachments',[])); missing.extend(out.get('missing_concept_suggestions',[])); snapshots.append({'stage':f'workshop-attach-{i:02d}','concept_count':len(catalogue)})
    uncovered=[o for o in work if not any(a.get('observation_id')==o['observation_id'] and a.get('concept_ids') for a in attachments)]
    for i in range(min(2,max(1,(len(uncovered)+39)//40))):
        out,meta=call(f'residual-gap-{i+1:02d}',DISC_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in uncovered[i*40:(i+1)*40]]}); metas.append(meta); missing.extend(out.get('missing_concept_suggestions',[])); snapshots.append({'stage':f'residual-gap-{i+1:02d}','concept_count':len(catalogue)})
    out,meta=call('boundary-tending',TEND_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in work[:100]]}); metas.append(meta); recs.extend(out.get('recommendations',[])); snapshots.append({'stage':'boundary-tending','concept_count':len(catalogue)})
    # final frozen holdout evaluation in two sequential calls
    hold_att=[]
    for i,batch in enumerate([hold[0::2],hold[1::2]],1):
        out,meta=call(f'holdout-attach-{i:02d}',ATTACH_PROMPT,{'catalogue':catalogue,'observations':[projection(o) for o in batch]}); metas.append(meta); hold_att.extend(out.get('attachments',[]))
    def counts(rows): return {'observations':len(rows),'zero':sum(not a.get('concept_ids') for a in rows),'one':sum(len(a.get('concept_ids',[]))==1 for a in rows),'multi':sum(len(a.get('concept_ids',[]))>1 for a in rows)}
    summary={'experiment_id':'native-induction-v2-workshop','eligible_observations':len(obs),'workshop_observations':len(work),'holdout_observations':len(hold),'provider_transmissions':len(metas),'completed_calls':sum(m.get('status')=='completed' for m in metas),'mechanically_rejected_or_failed':sum(m.get('status')!='completed' for m in metas),'input_tokens':sum(int(m.get('input_tokens') or 0) for m in metas),'output_tokens':sum(int(m.get('output_tokens') or 0) for m in metas),'actual_cost_usd':f"{sum(float(m.get('cost_usd') or 0) for m in metas):.6f}",'v1_seed_concepts':len(v1['concepts']),'concepts_after_discovery':len(catalogue),'concepts_after_tending_A':snapshots[3]['concept_count'] if len(snapshots)>3 else len(catalogue),'concepts_after_tending_B':len(catalogue),'final_catalogue_concepts':len(catalogue),'lineage_counts':{'inherited_v1_seed':len(v1['concepts']),'newly_induced':sum('newly_induced' in c.get('lineage',[]) for c in catalogue),'renamed':0,'redefined':0,'merged':0,'split':0,'reparented':0,'deprecated':0},'final_concepts_2plus_orgs':sum(len(set(c.get('organisations',[])))>=2 for c in catalogue),'final_concepts_3plus_orgs':sum(len(set(c.get('organisations',[])))>=3 for c in catalogue),'workshop_attachment_counts':counts(attachments),'final_holdout_attachment_counts':counts(hold_att),'final_holdout_missing_concept_suggestions':sum(bool(a.get('missing_concept_suggestion')) for a in hold_att),'provider_config':{'model':MODEL,'reasoning':'none','max_output_tokens':MAX_OUTPUT,'retries':0},'production_persistence':False}
    (ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); (ROOT/'catalogue.json').write_text(json.dumps(catalogue,ensure_ascii=False,indent=2),encoding='utf-8'); (ROOT/'lineage.json').write_text(json.dumps({'snapshots':snapshots,'recommendations':recs},ensure_ascii=False,indent=2),encoding='utf-8'); (ROOT/'attachments.json').write_text(json.dumps({'workshop':attachments,'holdout':hold_att},ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
