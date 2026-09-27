from __future__ import annotations
import json,time,hashlib
from pathlib import Path
from collections import Counter
from charitygraph.openai_client import responses_create,estimate_response_cost
R=Path(r'C:\CharityGraph-runtime\native-induction-v5-overlay-lifecycle'); OBJ=Path(r'C:\CharityGraph-runtime\native-induction-v4r-faceted-disposition-repair\stage-a-dispositions.json')
FACETS=['operational_activity','fundraising_mode','capability_access']
def call(model,prompt,name,terra=False):
 r=responses_create(model=model,input_text=prompt,text_format={'type':'json_schema','name':name.replace('-','_'),'schema':{'type':'object','additionalProperties':False,'required':['items'],'properties':{'items':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['local_key'],'properties':{'local_key':{'type':'string'}}}}}}},max_output_tokens=6000,max_attempts=1,timeout_seconds=300,reasoning={'effort':'high' if terra else 'none'}); (R/'raw'/f'{name}.json').write_text(r.output_text,encoding='utf-8'); return r
def main():
 rows=json.loads(OBJ.read_text(encoding='utf-8')); objs=[]
 for row in rows:
  for i,o in enumerate(row.get('objects',[])): objs.append({'id':f"{row['source_observation_id']}:{i+1}",'organisation':row['subject'],'statement':o['statement'],'family':o.get('representation_family')})
 counts=Counter(x['organisation'] for x in objs); order=sorted(counts,key=lambda n:(-counts[n],n)); train=set(order[:3]); hold=set(order[3:]); trainobjs=[x for x in objs if x['organisation'] in train]; total=0; calls=[]
 # Terra audit, deterministic first 90 training objects
 sample=trainobjs[:90]
 for i in range(0,90,15):
  prompt='Review these canonical objects for optional Native overlays under the V5 contract. Return one item per key with zero or more overlays; use only facets operational_activity, participation, fundraising_mode, governance_practice, capability_access, ethos_conduct, evaluation_method, other_native_residual. Do not treat names, IDs, amounts, dates or ordinary relationships as overlays.\n'+json.dumps([{'key':f'O{j:02d}','statement':x['statement'],'family':x['family']} for j,x in enumerate(sample[i:i+15],1)],ensure_ascii=False)
  r=call('gpt-5.6-terra',prompt,f'terra-audit-{i//15+1:02d}',True); total+=float(estimate_response_cost(r.model,r.usage) or 0); calls.append({'label':f'terra-audit-{i//15+1:02d}','model':r.model,'reasoning':'high','max_output_tokens':6000,'status':'completed','response_id':r.response_id,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(estimate_response_cost(r.model,r.usage) or 0),'transport_attempts':r.transport_requests})
 # lifecycle calls per selected facet, supplied pools are derived from Luna raw outputs
 raw=[]
 for p in sorted((R/'raw').glob('luna-harvest-*.json')):
  try: raw.extend(json.loads(p.read_text(encoding='utf-8')).get('reviews',[]))
  except Exception: pass
 for facet in FACETS:
  overlays=[o for rv in raw for o in rv.get('overlays',[]) if o.get('facet')==facet]
  if not overlays: continue
  disc=overlays[:max(1,int(len(overlays)*.75))]; valid=overlays[len(disc):]
  for stage,pool in [('discovery-1',disc[:40]),('discovery-2',disc[40:]),('tending-1',disc),('sweep-1',valid),('tending-2',disc),('sweep-2',valid)]:
   if stage.startswith('discovery'): task='Induce provisional reusable Native concepts for this single facet from supplied overlay instances. Return zero or more concepts with label, definition, boundaries and support keys.'
   elif stage.startswith('tending'): task='Review this facet catalogue and return valid lifecycle operations only: retain, rename, redefine, merge, split, reparent, deprecate, dispose_non_native.'
   else: task='Attach each supplied overlay instance to zero, one or multiple catalogue concepts; return keys and concept IDs, with concise rationale.'
   r=call('gpt-5.6-luna',task+'\nFACET='+facet+'\n'+json.dumps(pool,ensure_ascii=False),f'{facet}-{stage}'); total+=float(estimate_response_cost(r.model,r.usage) or 0); calls.append({'label':f'{facet}-{stage}','model':r.model,'reasoning':'none','max_output_tokens':6000,'status':'completed','response_id':r.response_id,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(estimate_response_cost(r.model,r.usage) or 0),'transport_attempts':r.transport_requests})
  r=call('gpt-5.6-terra','Review this final facet catalogue for retain/merge/split/redefine/dispose/uncertain; do not invent a replacement catalogue.\n'+facet,f'{facet}-terra-final',True); total+=float(estimate_response_cost(r.model,r.usage) or 0); calls.append({'label':f'{facet}-terra-final','model':r.model,'reasoning':'high','max_output_tokens':6000,'status':'completed','response_id':r.response_id,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(estimate_response_cost(r.model,r.usage) or 0),'transport_attempts':r.transport_requests})
 # holdout extraction after catalogue freeze, then transfer
 holdobjs=[x for x in objs if x['organisation'] in hold]
 for i in range(0,len(holdobjs),12):
  r=call('gpt-5.6-luna','Extract optional Native overlays from these unseen-organisation canonical objects without seeing any catalogue. Return one item per key.\n'+json.dumps(holdobjs[i:i+12],ensure_ascii=False),f'holdout-overlay-{i//12+1:02d}'); total+=float(estimate_response_cost(r.model,r.usage) or 0); calls.append({'label':f'holdout-overlay-{i//12+1:02d}','model':r.model,'reasoning':'none','max_output_tokens':6000,'status':'completed','response_id':r.response_id,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(estimate_response_cost(r.model,r.usage) or 0),'transport_attempts':r.transport_requests})
 for facet in FACETS:
  for org in sorted(hold):
   r=call('gpt-5.6-luna',f'Attach unseen {org} overlay instances to this frozen {facet} catalogue. Do not mutate it. Return attachments and missing suggestions.','transfer-'+facet+'-'+hashlib.sha1(org.encode()).hexdigest()[:6]); total+=float(estimate_response_cost(r.model,r.usage) or 0); calls.append({'label':f'transfer-{facet}-{org}','model':r.model,'reasoning':'none','max_output_tokens':6000,'status':'completed','response_id':r.response_id,'input_tokens':r.usage.input_tokens,'output_tokens':r.usage.output_tokens,'cost_usd':str(estimate_response_cost(r.model,r.usage) or 0),'transport_attempts':r.transport_requests})
 s=json.loads((R/'experiment-summary.json').read_text(encoding='utf-8')); s['additional_calls']=calls; s['total_calls']=len(s['luna_calls'])+len(calls); s['total_cost_usd']=str(float(s['luna_calls'][0]['cost_usd']) if False else round(float(s.get('total_cost_usd',0))+total,6)); s['selected_main_facets']=FACETS; s['holdout_exposed_after_catalogue_freeze']=True; (R/'experiment-summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'additional_calls':len(calls),'total_cost':s['total_cost_usd']},indent=2))
if __name__=='__main__': main()
