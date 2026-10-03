from __future__ import annotations
import argparse,json,time,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from charitygraph.openai_client import responses_create,estimate_response_cost

CORE=('operational_activity','participation','fundraising_mode')
ALL=('operational_activity','participation','fundraising_mode','governance_practice','capability_access','ethos_conduct','evaluation_method')
QUALITY_PROMPT='''Review supplied Luna Native overlay instances against the facet quality contract. Return exactly one review for every local overlay key. Disposition is accept, reframe, move_facet or reject_native. Preserve the underlying canonical object; do not create canonical objects. Return concise rationale, facet_after (existing facet or null), reviewed statement/dimension/boundaries, qualification and uncertainty. Do not infer beyond supplied material.'''
def quality_schema():
 d={'type':'string','enum':['accept','reframe','move_facet','reject_native']}; item={'type':'object','additionalProperties':False,'required':['local_key','disposition','rationale','facet_after','reviewed_overlay_statement','reviewed_analytic_dimension','reviewed_inclusion_boundary','reviewed_exclusion_boundary','qualification','uncertainty'],'properties':{'local_key':{'type':'string'},'disposition':d,'rationale':{'type':'string'},'facet_after':{'type':['string','null'],'enum':list(ALL)+[None]},'reviewed_overlay_statement':{'type':['string','null']},'reviewed_analytic_dimension':{'type':['string','null']},'reviewed_inclusion_boundary':{'type':'string'},'reviewed_exclusion_boundary':{'type':'string'},'qualification':{'type':'string'},'uncertainty':{'type':['string','null']}}}; return {'type':'object','additionalProperties':False,'required':['reviews'],'properties':{'reviews':{'type':'array','items':item}}}
def generic_schema(keys=('items',)):
 return {'type':'object','additionalProperties':False,'required':list(keys),'properties':{k:{'type':'array','items':{'type':'object','additionalProperties':False,'required':['local_key'],'properties':{'local_key':{'type':'string'}}}} for k in keys}}
def call(root,model,prompt,name,schema,reason='none',maxout=5000):
 t=time.time(); r=responses_create(model=model,input_text=prompt,text_format={'type':'json_schema','name':name.replace('-','_'),'schema':schema},max_output_tokens=maxout,max_attempts=1,timeout_seconds=300,reasoning={'effort':reason}); (root/'raw'/f'{name}.json').write_text(r.output_text,encoding='utf-8'); return r,time.time()-t
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--runtime',default=r'C:\CharityGraph-runtime\native-induction-v5r-overlay-quality-lifecycle'); ap.add_argument('--review',default=r'C:\tmp\charitygraph-lab-review\native-induction-v5-overlay-lifecycle-review'); a=ap.parse_args(); root=Path(a.runtime); (root/'raw').mkdir(parents=True,exist_ok=True)
 overlays=[]
 for p in Path(a.review).glob('overlays-*.json'): overlays.extend(json.loads(p.read_text(encoding='utf-8')))
 clean=[x for x in overlays if x.get('representation_family')!='native_candidate']; excluded=[x for x in overlays if x.get('representation_family')=='native_candidate']; (root/'excluded-v4r-native-candidate-overlays.json').write_text(json.dumps(excluded,ensure_ascii=False,indent=2),encoding='utf-8')
 total=0; usage=[]; quality=[]
 for i in range(0,len(clean),10):
  batch=clean[i:i+10]; prompt=QUALITY_PROMPT+'\nFACET CONTRACTS: operational activity excludes ordinary finance/admin/relationships; participation is how actors participate, not who is served; fundraising mode is an active mobilisation mechanism, not income.\n'+json.dumps(batch,ensure_ascii=False)
  r,lat=call(root,'gpt-5.6-terra',prompt,f'quality-{i//10+1:02d}',quality_schema(),'high',5000); c=estimate_response_cost(r.model,r.usage) or 0; total+=float(c); usage.append({'stage':'quality','label':f'quality-{i//10+1:02d}','model':r.model,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(c),'latency_seconds':round(lat,2),'status':'completed'}); 
  try: d=json.loads(r.output_text); quality.extend(d.get('reviews',[]))
  except Exception: pass
 qby={x.get('local_key'):x for x in quality}; pools=defaultdict(list)
 for x in clean:
  key=x.get('local_key'); q=qby.get(key,{}); f=q.get('facet_after') if q.get('disposition')=='move_facet' else x.get('facet');
  if q.get('disposition') in ('accept','reframe') or (q.get('disposition')=='move_facet' and f in CORE): pools[f].append({'overlay_id':'v5r:'+hashlib.sha256(key.encode()).hexdigest()[:24],'original':x,'review':q,'facet':f})
 (root/'quality-reviews.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8'); (root/'reviewed-core-pools.json').write_text(json.dumps({k:v for k,v in pools.items() if k in CORE},ensure_ascii=False,indent=2),encoding='utf-8')
 for facet in CORE:
  pool=pools.get(facet,[])
  if len(pool)<6 or len({x['original']['organisation'] for x in pool})<2: continue
  disc=pool[:max(1,int(len(pool)*.75))]; val=pool[len(disc):]
  catalogue=[]; stages=[]
  for n in (1,2):
   r,lat=call(root,'gpt-5.6-luna','Induce reusable concepts for facet '+facet+'. Return concepts with local_key, preferred_label, definition, inclusion_boundary, exclusion_boundary, support_keys, parent_key, uncertainty.\n'+json.dumps(disc[(n-1)*40:n*40],ensure_ascii=False)+"\nCATALOGUE="+json.dumps(catalogue,ensure_ascii=False),f'{facet}-discovery-{n}',generic_schema(),'none',5000); c=estimate_response_cost(r.model,r.usage) or 0; total+=float(c); stages.append({'stage':'discovery','facet':facet,'call':n,'model':r.model,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(c)}); 
   try: catalogue.extend(json.loads(r.output_text).get('items',[]))
   except Exception: pass
  for roundno in (1,2):
   r,lat=call(root,'gpt-5.6-terra','Apply lifecycle operations to this single facet catalogue. Return operations with local_key and action.\nFACET='+facet+'\nCATALOGUE='+json.dumps(catalogue,ensure_ascii=False),f'{facet}-gardener-{roundno}',generic_schema(),'high',4000); c=estimate_response_cost(r.model,r.usage) or 0; total+=float(c); stages.append({'stage':'gardener','facet':facet,'round':roundno,'model':r.model,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(c)})
  for sweep in (1,2):
   r,lat=call(root,'gpt-5.6-luna','Attach validation overlays to this frozen catalogue; return local_key only per item and zero/one/multiple concept IDs. No mutation.\nFACET='+facet+'\nOVERLAYS='+json.dumps(val,ensure_ascii=False)+'\nCATALOGUE='+json.dumps(catalogue,ensure_ascii=False),f'{facet}-sweep-{sweep}',generic_schema(),'none',5000); c=estimate_response_cost(r.model,r.usage) or 0; total+=float(c); stages.append({'stage':'sweep','facet':facet,'round':sweep,'model':r.model,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(c)})
  (root/f'{facet}-lifecycle.json').write_text(json.dumps({'pool':len(pool),'catalogue':catalogue,'stages':stages},ensure_ascii=False,indent=2),encoding='utf-8'); usage.extend(stages)
 # holdout extraction after catalogues are frozen
 split=json.loads((Path(r'C:\CharityGraph-runtime\native-induction-v5-overlay-lifecycle')/'v5-organisation-split.json').read_text(encoding='utf-8')); hold=set(x['organisation'] for x in split['organisations'] if x['role']=='holdout'); allobj=[]; rows=json.loads(Path(r'C:\CharityGraph-runtime\native-induction-v4r-faceted-disposition-repair\stage-a-dispositions.json').read_text(encoding='utf-8'))
 for row in rows:
  if row['subject'] in hold:
   for i,o in enumerate(row.get('objects',[])): allobj.append({'local_key':f'H{i+1:03d}','organisation':row['subject'],'statement':o['statement'],'representation_family':o.get('representation_family')})
 for i in range(0,len(allobj),10):
  r,lat=call(root,'gpt-5.6-luna','Extract optional overlays only from unseen objects; return local_key and zero or more complete overlays.\n'+json.dumps(allobj[i:i+10],ensure_ascii=False),f'holdout-extraction-{i//10+1:02d}',generic_schema(),'none',5000); c=estimate_response_cost(r.model,r.usage) or 0; total+=float(c); usage.append({'stage':'holdout_extraction','call':i//10+1,'model':r.model,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(c)})
 s={'experiment_id':'native-induction-v5r-overlay-quality-lifecycle','v5_overlays':len(overlays),'excluded_native_candidate_overlays':len(excluded),'clean_overlays':len(clean),'quality_reviews':len(quality),'quality_usage':usage,'total_cost_usd':f'{total:.6f}','holdout_objects':len(allobj),'provider_calls':len(usage)}; (root/'experiment-summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(s,indent=2))
if __name__=='__main__': main()
