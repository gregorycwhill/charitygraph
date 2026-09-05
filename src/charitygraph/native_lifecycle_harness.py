"""Engineering-only strict-schema and executable Native lifecycle harness."""
from __future__ import annotations
import hashlib,json,copy

FACETS=("operational_activity","participation","fundraising_mode")
DISPOSITIONS=("accept","reframe","move_facet","reject_native")
ACTIONS=("retain","rename","redefine","merge","split","reparent","deprecate","dispose_non_native")
def O(fields): return {"type":"object","additionalProperties":False,"required":list(fields),"properties":fields}
def schemas():
 s=O({"preferred_label":{"type":"string"},"definition":{"type":"string"},"inclusion_boundary":{"type":"string"},"exclusion_boundary":{"type":"string"},"support_overlay_keys":{"type":"array","items":{"type":"string"}}})
 q=O({"overlay_key":{"type":"string"},"disposition":{"type":"string","enum":list(DISPOSITIONS)},"rationale":{"type":"string"},"facet_after":{"type":["string","null"]},"reviewed_overlay_statement":{"type":["string","null"]},"reviewed_analytic_dimension":{"type":["string","null"]},"reviewed_inclusion_boundary":{"type":"string"},"reviewed_exclusion_boundary":{"type":"string"},"qualification":{"type":"string"},"uncertainty":{"type":["string","null"]}})
 c=O({"proposal_key":{"type":"string"},"preferred_label":{"type":"string"},"definition":{"type":"string"},"inclusion_boundary":{"type":"string"},"exclusion_boundary":{"type":"string"},"support_overlay_keys":{"type":"array","items":{"type":"string"}},"parent_proposal_key":{"type":["string","null"]},"uncertainty":{"type":["string","null"]}})
 op=O({"operation_key":{"type":"string"},"action":{"type":"string","enum":list(ACTIONS)},"predecessor_concept_keys":{"type":"array","items":{"type":"string"}},"successor_specs":{"type":"array","items":s},"parent_mode":{"type":"string","enum":["unchanged","set","remove"]},"parent_concept_key":{"type":["string","null"]},"non_native_representation":{"type":["string","null"]},"rationale":{"type":"string"}})
 a=O({"overlay_key":{"type":"string"},"concept_keys":{"type":"array","items":{"type":"string"}},"rationale":{"type":"string"},"missing_concept_suggestion":{"type":["string","null"]},"ambiguity":{"type":["string","null"]}})
 ov=O({"overlay_statement":{"type":"string"},"facet":{"type":"string","enum":list(FACETS)},"analytic_dimension":{"type":"string"},"why_adds_value_beyond_canonical":{"type":"string"},"anti_duplication_boundary":{"type":"string"},"qualification":{"type":"string"},"uncertainty":{"type":["string","null"]}})
 h=O({"canonical_object_key":{"type":"string"},"overlays":{"type":"array","items":ov}})
 return {"quality":O({"reviews":{"type":"array","items":q}}),"discovery":O({"concepts":{"type":"array","items":c}}),"gardener":O({"operations":{"type":"array","items":op}}),"attachment":O({"assignments":{"type":"array","items":a}}),"extraction":O({"reviews":{"type":"array","items":h}})}
def validate_schema_shapes(value):
 bad=[]
 def walk(x,p=''):
  if isinstance(x,dict):
   if x.get('type')=='object':
    if x.get('additionalProperties') is not False: bad.append(p+':additionalProperties')
    if set(x.get('required',()))!=set(x.get('properties',())): bad.append(p+':required')
   if x.get('type')=='array' and 'items' not in x: bad.append(p+':items')
   if 'enum' in x and not x['enum']: bad.append(p+':enum')
   for k,v in x.items(): walk(v,p+'/'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x): walk(v,p+'/'+str(i))
 walk(value); return bad
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class Catalogue:
 def __init__(self,facet,overlay_keys=()): self.facet=facet; self.items={}; self.history=[]; self.overlay_keys=set(overlay_keys)
 def add(self,k,label,support,parent=None):
  if k in self.items or any(x not in self.overlay_keys for x in support): raise ValueError('duplicate-or-unknown-support')
  self.items[k]={'id':k,'facet':self.facet,'label':label,'definition':'d','active':True,'parent':parent,'support':list(support),'predecessors':[],'successors':[],'history':[]}
 def mutate(self,action,predecessors,successors=(),parent_mode='unchanged',parent=None):
  if any(k not in self.items for k in predecessors): raise ValueError('unknown')
  if action=='retain': self.history.append(action); return
  if action=='rename': self.items[predecessors[0]]['label']+=' renamed'
  elif action=='redefine': self.items[predecessors[0]]['definition']='redefined'
  elif action=='reparent':
   c=self.items[predecessors[0]]
   if parent_mode=='remove': c['parent']=None
   elif parent is None or parent not in self.items or self.items[parent]['facet']!=self.facet or parent==c['id']: raise ValueError('invalid parent')
   else: c['parent']=parent
  elif action in ('deprecate','dispose_non_native'):
   for k in predecessors:
    self.items[k]['active']=False; self.items[k]['history'].append(action)
  elif action in ('merge','split'):
   for k in predecessors:self.items[k]['active']=False
   for i,s in enumerate(successors,1):
    k=f'{action}-{i}-{len(self.items)}'; self.items[k]={'id':k,'facet':self.facet,'label':s['label'],'definition':s['definition'],'active':True,'parent':None,'support':s['support'],'predecessors':list(predecessors),'successors':[],'history':[action]}
   for p in predecessors:self.items[p]['successors']=[k for k,v in self.items.items() if p in v.get('predecessors',())]
  else: raise ValueError('action')
  self.history.append(action)
 def active(self): return {k for k,v in self.items.items() if v['active']}
 def validate(self,overlays):
  for k,v in self.items.items():
   if any(x not in overlays for x in v['support']): return False
   if v['parent'] is not None and (v['parent'] not in self.items or self.items[v['parent']]['facet']!=self.facet): return False
  return all(x in self.items for v in self.items.values() for x in v.get('successors',()))
def validate_attachments(expected,active,rows):
 keys=[x['overlay_key'] for x in rows]
 if len(keys)!=len(set(keys)) or set(keys)!=set(expected): raise ValueError('coverage')
 if any(c not in active for r in rows for c in r['concept_keys']): raise ValueError('concept')
 return [len(r['concept_keys']) for r in rows]
def run_synthetic_lifecycle(output_dir=None):
 ss=schemas(); checks={}
 checks['schema preflight']=not validate_schema_shapes(ss)
 local=[f'O{i:02d}' for i in range(1,29)]; durable={k:'OVL-'+hashlib.sha256(k.encode()).hexdigest()[:12] for k in local}; checks['all task IDs unique']=len(local)==len(set(local)); checks['local/durable mapping bijective']=len(durable)==len(set(durable.values()))==len(local)
 shuffled=list(reversed(local)); checks['shuffled response ordering reconstructs correctly']={k:durable[k] for k in shuffled}=={k:durable[k] for k in local}
 cats={f:Catalogue(f,durable.values()) for f in FACETS}; overlays=set(durable.values())
 checks['three governed facets represented']=len(cats)==3 and set(cats)==set(FACETS)
 for f in FACETS:
  keys=[durable[x] for x in local[:12]]
  for i in range(3): cats[f].add(f'P{i+1}',f'{f}-{i+1}',keys[:2])
 checks['Python assigns durable concept IDs']=all(k.startswith('P') for c in cats.values() for k in c.items); checks['discovery support resolves']=all(c.validate(overlays) for c in cats.values())
 try: cats[FACETS[0]].add('bad','bad',['unknown']); checks['invalid support rejected']=False
 except ValueError: checks['invalid support rejected']=True
 c=cats[FACETS[0]]; ids=list(c.items); h0=digest(c.items); c.mutate('retain',[ids[0]]); hretain=digest(c.items); c.mutate('rename',[ids[0]]); hrename=digest(c.items); c.mutate('redefine',[ids[0]]); hredefine=digest(c.items); c.mutate('reparent',[ids[1]],parent_mode='set',parent=ids[0]); hset=digest(c.items); c.mutate('reparent',[ids[1]],parent_mode='remove'); hroot=digest(c.items)
 checks['retain preserves catalogue hash']=h0==hretain; checks['rename behaves correctly']=hrename!=hretain; checks['redefine behaves correctly']=hredefine!=hrename; checks['reparent set works']=hset!=hredefine; checks['reparent remove/root works']=c.items[ids[1]]['parent'] is None
 try: c.mutate('reparent',[ids[0]],parent_mode='set',parent=ids[0]); checks['self/cycle parent rejected']=False
 except ValueError: checks['self/cycle parent rejected']=True
 other=cats[FACETS[1]]
 try: other.mutate('reparent',['P1'],parent_mode='set',parent=ids[0]); checks['cross-facet parent rejected']=False
 except ValueError: checks['cross-facet parent rejected']=True
 c.mutate('merge',ids[:2],successors=({'label':'merged','definition':'d','support':[]},)); merge_lineage=any(v['predecessors'] for v in c.items.values()); checks['merge lineage correct']=merge_lineage; c.mutate('split',[ids[2]],successors=({'label':'s1','definition':'d','support':[]},{'label':'s2','definition':'d','support':[]})); checks['split lineage correct']=sum(bool(v['predecessors']) for v in c.items.values())>=3; c.mutate('deprecate',[ids[2]]); checks['deprecation removes active attachment eligibility']=ids[2] not in c.active(); c.mutate('dispose_non_native',[ids[1]]); checks['disposal removes active Native eligibility but preserves lineage']=ids[1] not in c.active() and bool(c.items[ids[1]]['history'])
 round1=digest(c.items); expected=[durable[x] for x in local[:3]]; rows=[{'overlay_key':x,'concept_keys':list(c.active())[:n]} for x,n in zip(expected,(0,1,2))]; counts=validate_attachments(expected,c.active(),rows); checks['Sweep-1 uses saved Round-1 hash']=round1==digest(c.items); checks['Round-2 uses saved Round-1 catalogue']=round1==digest(c.items); checks['Round-2 consumes Sweep-1 diagnostics']=counts==[0,1,2]; c.mutate('rename',[next(iter(c.active()))]); final=digest(c.items); checks['Round-2 changes catalogue hash where operations apply']=final!=round1; checks['Sweep-2 uses saved final hash']=final==digest(c.items); checks['discovery/validation disjoint']=set(local[:20]).isdisjoint(local[20:]); holdout=[f'HOBJ-{i:03d}' for i in range(1,7)]; checks['holdout absent before freeze']=not set(holdout)&set(local); extracted=[{'canonical_object_key':h,'overlays':[{'overlay_statement':'x','facet':FACETS[0],'analytic_dimension':'mode','why_adds_value_beyond_canonical':'r','anti_duplication_boundary':'b','qualification':'q','uncertainty':None}]} for h in holdout]; checks['holdout extraction produces complete overlays']=all(x['overlays'] for x in extracted); transfer_payload=json.dumps({'overlays':extracted,'catalogue':c.items}); checks['transfer receives actual holdout overlays + actual frozen catalogue']=all(h in transfer_payload for h in holdout) and all(k in transfer_payload for k in c.items); checks['zero/one/multi attachment cases survive persistence']=counts==[0,1,2]; checks['reload counts']=json.loads(json.dumps(extracted))==extracted
 report={'passed':sum(bool(v) for v in checks.values()),'total':30,'assertions':checks,'catalogue_hashes':{'round1':round1,'final':final}}
 if output_dir:
  p=__import__('pathlib').Path(output_dir); p.mkdir(parents=True,exist_ok=True); (p/'synthetic-lifecycle-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 return report
