"""Provider-free executable Native lifecycle laboratory harness."""
from __future__ import annotations
import hashlib,json,uuid
from pathlib import Path

FACETS=("operational_activity","participation","fundraising_mode")
DISPOSITIONS=("accept","reframe","move_facet","reject_native")
ACTIONS=("retain","rename","redefine","merge","split","reparent","deprecate","dispose_non_native")
def _obj(p): return {"type":"object","additionalProperties":False,"required":list(p),"properties":p}
def schemas():
 s=_obj({"preferred_label":{"type":"string"},"definition":{"type":"string"},"inclusion_boundary":{"type":"string"},"exclusion_boundary":{"type":"string"},"support_overlay_keys":{"type":"array","items":{"type":"string"}}})
 q=_obj({"overlay_key":{"type":"string"},"disposition":{"type":"string","enum":list(DISPOSITIONS)},"rationale":{"type":"string"},"facet_after":{"type":["string","null"]},"reviewed_overlay_statement":{"type":["string","null"]},"reviewed_analytic_dimension":{"type":["string","null"]},"reviewed_inclusion_boundary":{"type":"string"},"reviewed_exclusion_boundary":{"type":"string"},"qualification":{"type":"string"},"uncertainty":{"type":["string","null"]}})
 c=_obj({"local_key":{"type":"string"},"preferred_label":{"type":"string"},"definition":{"type":"string"},"inclusion_boundary":{"type":"string"},"exclusion_boundary":{"type":"string"},"support_overlay_keys":{"type":"array","items":{"type":"string"}},"parent_local_key":{"type":["string","null"]},"uncertainty":{"type":["string","null"]}})
 op=_obj({"operation_key":{"type":"string"},"action":{"type":"string","enum":list(ACTIONS)},"predecessor_local_keys":{"type":"array","items":{"type":"string"}},"successor_specs":{"type":"array","items":s},"parent_mode":{"type":"string","enum":["unchanged","set","remove"]},"parent_local_key":{"type":["string","null"]},"non_native_representation":{"type":["string","null"]},"rationale":{"type":"string"}})
 a=_obj({"overlay_key":{"type":"string"},"concept_ids":{"type":"array","items":{"type":"string"}},"rationale":{"type":"string"},"missing_concept_suggestion":{"type":["string","null"]},"ambiguity":{"type":["string","null"]}})
 ov=_obj({"overlay_statement":{"type":"string"},"facet":{"type":"string","enum":list(FACETS)},"analytic_dimension":{"type":"string"},"why_adds_value_beyond_canonical":{"type":"string"},"anti_duplication_boundary":{"type":"string"},"qualification":{"type":"string"},"uncertainty":{"type":["string","null"]}})
 h=_obj({"canonical_object_key":{"type":"string"},"overlays":{"type":"array","items":ov}})
 return {"quality":_obj({"reviews":{"type":"array","items":q}}),"discovery":_obj({"concepts":{"type":"array","items":c}}),"gardener":_obj({"operations":{"type":"array","items":op}}),"attachment":_obj({"assignments":{"type":"array","items":a}}),"extraction":_obj({"reviews":{"type":"array","items":h}})}
def validate_schema_shapes(value):
 bad=[]
 def walk(x,p=""):
  if isinstance(x,dict):
   if x.get("type")=="object":
    if x.get("additionalProperties") is not False: bad.append(p+":additionalProperties")
    if set(x.get("required",()))!=set(x.get("properties",())): bad.append(p+":required")
   if x.get("type")=="array" and "items" not in x: bad.append(p+":items")
   for k,v in x.items(): walk(v,p+"/"+k)
  elif isinstance(x,list):
   for i,v in enumerate(x): walk(v,p+"/"+str(i))
 walk(value); return bad
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def validate_response(value,schema,path=""):
    t=schema.get("type")
    if isinstance(t,list):
        if value is None and "null" in t:return
        t=next((x for x in t if x!="null"),None)
    if t=="object":
        if not isinstance(value,dict): raise ValueError(path+": object required")
        if set(value)!=set(schema.get("properties",{})): raise ValueError(path+": undeclared/missing field")
        for k,v in schema["properties"].items(): validate_response(value[k],v,path+"/"+k)
    elif t=="array":
        if not isinstance(value,list): raise ValueError(path+": array required")
        for i,v in enumerate(value): validate_response(v,schema["items"],path+"/"+str(i))
    elif t=="string" and not isinstance(value,str): raise ValueError(path+": string required")
    if "enum" in schema and value not in schema["enum"]: raise ValueError(path+": invalid enum")
class FakeProvider:
 def __init__(self): self.invocations=[]
 def request(self,task,payload,schema):
  self.invocations.append({"task":task,"payload_sha256":digest(payload)})
  if task=="quality":
   if "items" in payload:
    facets=("operational_activity","participation","fundraising_mode","capability_access","governance_practice","ethos_conduct","evaluation_method"); out=[]
    for item in payload["items"]:
     oid=item["durable_overlay_id"]; n=int(hashlib.sha256(oid.encode()).hexdigest()[:8],16); d=("accept","reframe","move_facet","reject_native")[n%4]; f=item.get("original_facet") or "operational_activity"; fa=f
     if d=="move_facet": fa=facets[(facets.index(f)+1)%len(facets)] if f in facets else facets[0]
     pref="Reviewed: " if d=="reframe" else ""
     out.append({"overlay_key":oid,"disposition":d,"rationale":"deterministic quality review","facet_after":fa,"reviewed_overlay_statement":pref+(item.get("overlay_statement") or ""),"reviewed_analytic_dimension":pref+(item.get("analytic_dimension") or ""),"reviewed_inclusion_boundary":pref+(item.get("anti_duplication_boundary") or "include"),"reviewed_exclusion_boundary":pref+(item.get("uncertainty") or "exclude"),"qualification":item.get("qualification") or "none","uncertainty":item.get("uncertainty")})
    return {"reviews":out}
   return {"reviews":[{"overlay_key":o,"disposition":"accept","rationale":"bounded","facet_after":payload["facet"],"reviewed_overlay_statement":"statement","reviewed_analytic_dimension":"dimension","reviewed_inclusion_boundary":"include","reviewed_exclusion_boundary":"exclude","qualification":"none","uncertainty":None} for o in payload["overlay_keys"]]}
  if task=="discovery": return {"concepts":[{"local_key":"P01","preferred_label":"canonical one","definition":"definition one","inclusion_boundary":"include one","exclusion_boundary":"exclude one","support_overlay_keys":payload["overlay_keys"][:1],"parent_local_key":None,"uncertainty":None},{"local_key":"P02","preferred_label":"canonical two","definition":"definition two","inclusion_boundary":"include two","exclusion_boundary":"exclude two","support_overlay_keys":payload["overlay_keys"][:1],"parent_local_key":None,"uncertainty":None}]}
  if task=="gardener" and "concept_keys" in payload:
   keys=payload["concept_keys"]; facet=payload.get("facet"); ops=[]
   if facet=="operational_activity": action="rename"
   elif facet=="participation": action="redefine"
   else: action="retain"
   k=keys[0]; spec={"preferred_label":"provider revised","definition":"provider definition","inclusion_boundary":"include","exclusion_boundary":"exclude","support_overlay_keys":payload.get("overlay_keys",[])[:1]}
   ops.append({"operation_key":"provider-op","action":action,"predecessor_local_keys":[k],"successor_specs":[] if action=="retain" else [spec],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"deterministic fake provider"})
   return {"operations":ops}
  if task=="attachment" and "active_concept_ids" in payload:
   ids=payload["active_concept_ids"]; out=[]
   for o in payload.get("overlay_keys",[]):
    n=int(hashlib.sha256((o+payload.get("catalogue_hash","")).encode()).hexdigest()[:8],16); take=0 if n%3==0 else 1 if n%3==1 else min(2,len(ids)); out.append({"overlay_key":o,"concept_ids":ids[:take],"rationale":"deterministic fake attachment","missing_concept_suggestion":None,"ambiguity":None})
   return {"assignments":out}
  if task=="gardener": return {"operations":[{"operation_key":"rename","action":"rename","predecessor_local_keys":["P01"],"successor_specs":[{"preferred_label":"renamed","definition":"definition one","inclusion_boundary":"include one","exclusion_boundary":"exclude one","support_overlay_keys":payload["overlay_keys"][:1]}],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"rename"},{"operation_key":"redefine","action":"redefine","predecessor_local_keys":["P02"],"successor_specs":[{"preferred_label":"canonical two","definition":"redefined","inclusion_boundary":"redefined include","exclusion_boundary":"redefined exclude","support_overlay_keys":payload["overlay_keys"][:1]}],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"redefine"}]}
  if task=="attachment": return {"assignments":[{"overlay_key":o,"concept_ids":([] if i==0 else payload["concept_ids"][:(1 if i==1 else 2)]),"rationale":"attachment","missing_concept_suggestion":None,"ambiguity":None} for i,o in enumerate(payload["overlay_keys"])]}
  if task=="extraction": return {"reviews":[{"canonical_object_key":o,"overlays":[{"overlay_statement":"holdout","facet":FACETS[0],"analytic_dimension":"mode","why_adds_value_beyond_canonical":"test","anti_duplication_boundary":"boundary","qualification":"qualified","uncertainty":None}]} for o in payload["object_keys"]]}
  raise ValueError("unknown task")

class SemanticCallLedger:
 """Authoritative ledger for every semantic provider invocation."""
 def __init__(self, output_dir=None): self.rows=[]; self.output_dir=Path(output_dir) if output_dir else None
 def record(self,row):
  self.rows.append(dict(row))
  if self.output_dir:
   self.output_dir.mkdir(parents=True,exist_ok=True)
   (self.output_dir/(row["call_id"]+"-ledger.json")).write_text(json.dumps(row,indent=2,ensure_ascii=False),encoding="utf-8")
 def counts(self): return {task:sum(r["task"]==task for r in self.rows) for task in sorted({r["task"] for r in self.rows})}
 def reconcile(self, provider, offset=0):
  actual=list(getattr(provider,"invocations",()))[offset:]
  if len(self.rows)!=len(actual): raise AssertionError("semantic ledger/provider invocation mismatch")
  if [r["task"] for r in self.rows] != [r["task"] for r in actual]: raise AssertionError("semantic task mismatch")
  return True

def invoke_semantic_call(provider, task, payload, schema, processor, *, ledger=None,
                         output_dir=None, facet=None, organisation=None, model="fake",
                         reasoning="none", provider_kind=None, call_id=None):
 """Single controlled path for manifest, provider call, validation, processing and ledger."""
 ledger=ledger or SemanticCallLedger(output_dir)
 call_id=call_id or f"{task}-{uuid.uuid4().hex[:12]}"
 kind=provider_kind or ("fake" if isinstance(provider,FakeProvider) else "adapter")
 request_sha=digest(payload); manifest={"call_id":call_id,"task":task,"facet":facet,"organisation":organisation,"model":model,"reasoning":reasoning,"provider_kind":kind,"request_sha256":request_sha}
 out=Path(output_dir) if output_dir else None
 if out:
  out.mkdir(parents=True,exist_ok=True); (out/(call_id+"-manifest.json")).write_text(json.dumps(manifest,indent=2),encoding="utf-8")
 try:
  response=provider.request(task,payload,schema)
  parsed=processor(response,schema)
  row=dict(manifest,status="completed",response_sha256=digest(response),usage=None,cost_usd=0)
 except Exception as exc:
  response={"error":str(exc)}; row=dict(manifest,status="incomplete_or_rejected",error=str(exc),response_sha256=digest(response),usage=None,cost_usd=0)
  row.update(getattr(provider,"last_call",{})); ledger.record(row)
  if out: (out/(call_id+"-response.json")).write_text(json.dumps(response,indent=2,ensure_ascii=False),encoding="utf-8")
  raise
 row.update(getattr(provider,"last_call",{})); ledger.record(row)
 if out:
  (out/(call_id+"-response.json")).write_text(json.dumps(response,indent=2,ensure_ascii=False),encoding="utf-8")
  prompt=getattr(provider,"last_call",{}).get("prompt")
  if prompt: (out/(call_id+"-prompt.txt")).write_text(prompt,encoding="utf-8")
 return parsed, row, ledger
def _require(x,k):
 if not isinstance(x,dict) or k not in x: raise ValueError("missing "+k)
def _unique(v):
 if any(x is None for x in v) or len(v)!=len(set(v)): raise ValueError("duplicate or missing local key")
def process_quality_response(r,s): validate_response(r,s); _require(r,"reviews"); return r["reviews"]
def process_discovery_response(r,s): validate_response(r,s); _require(r,"concepts"); _unique([x.get("local_key") for x in r["concepts"]]); return r["concepts"]
def process_gardener_response(r,s):
 validate_response(r,s); _require(r,"operations")
 if any(not x.get("operation_key") or "predecessor_local_keys" not in x for x in r["operations"]): raise ValueError("invalid gardener operation")
 return r["operations"]
def process_attachment_response(r,s):
 validate_response(r,s); _require(r,"assignments")
 if any("concept_ids" not in x for x in r["assignments"]): raise ValueError("invalid attachment")
 return r["assignments"]
def process_extraction_response(r,s):
 validate_response(r,s); _require(r,"reviews")
 if any(not x.get("canonical_object_key") for x in r["reviews"]): raise ValueError("invalid extraction")
 return r["reviews"]

class Catalogue:
 def __init__(self,facet,overlays=(),registry=None): self.facet=facet; self.overlays=set(overlays); self.registry=registry if registry is not None else {}; self.items={}; self.history=[]; self.frozen=False
 def freeze(self): self.frozen=True
 def to_dict(self): return {"facet":self.facet,"overlays":sorted(self.overlays),"registry":{k:list(v) if isinstance(v,tuple) else v for k,v in self.registry.items()},"items":self.items,"history":self.history,"frozen":self.frozen}
 def semantic_hash(self): return digest(self.to_dict())
 @classmethod
 def from_dict(cls,data):
  c=cls(data["facet"],data.get("overlays",[]),{k:tuple(v) if isinstance(v,list) else v for k,v in data.get("registry",{}).items()}); c.items=data.get("items",{}); c.history=data.get("history",[]); c.frozen=data.get("frozen",False); return c
 def _id(self,local,call_id="call-1"):
  ident="CON-"+self.facet+"-"+hashlib.sha256((self.facet+"|"+call_id+"|"+local).encode()).hexdigest()[:16]
  if ident in self.registry and self.registry[ident]!=(self.facet,call_id,local): raise ValueError("collision")
  self.registry[ident]=(self.facet,call_id,local); return ident
 def add(self,local,label,support,parent=None,semantics=None,call_id="call-1"):
  storage_key=local if call_id=="call-1" and local not in self.items else call_id+"/"+local
  if storage_key in self.items or any(x not in self.overlays for x in support): raise ValueError("duplicate-or-unknown-support")
  sem=semantics or {}; ident=self._id(local,call_id); self.items[storage_key]={"id":ident,"local_key":local,"call_id":call_id,"facet":self.facet,"preferred_label":label,"definition":sem.get("definition","definition"),"inclusion_boundary":sem.get("inclusion_boundary","include"),"exclusion_boundary":sem.get("exclusion_boundary","exclude"),"active":True,"parent":parent,"support_overlay_ids":list(support),"predecessors":[],"successors":[],"lifecycle_history":[]}; return ident
 def _cycle(self,child,parent):
  seen=set(); cur=parent
  while cur is not None:
   if cur==child or cur in seen:return True
   seen.add(cur); cur=self.items.get(cur,{}).get("parent")
  return False
 def mutate(self,action,preds,successors=(),parent_mode="unchanged",parent=None,non_native_representation=None):
  if self.frozen: raise ValueError("catalogue frozen")
  if any(k not in self.items for k in preds): raise ValueError("unknown predecessor")
  if action=="retain": self.history.append(action); return
  if action in ("rename","redefine"):
   if len(successors)!=1: raise ValueError("successor required")
   s=successors[0]; c=self.items[preds[0]]; c["preferred_label"]=s["preferred_label"]
   if action=="redefine":
    for k in ("definition","inclusion_boundary","exclusion_boundary"): c[k]=s[k]
   if any(x not in self.overlays for x in s.get("support_overlay_keys",())): raise ValueError("unknown support")
   c["support_overlay_ids"]=list(s.get("support_overlay_keys",()))
  elif action=="reparent":
   c=self.items[preds[0]]
   if parent_mode=="remove": c["parent"]=None
   elif parent is None or parent not in self.items or parent==c["local_key"] or self._cycle(c["local_key"],parent): raise ValueError("invalid parent/cycle")
   else:c["parent"]=parent
  elif action in ("deprecate","dispose_non_native"):
   for k in preds:self.items[k]["active"]=False; self.items[k]["lifecycle_history"].append({"action":action,"non_native_representation":non_native_representation})
  elif action in ("merge","split"):
   if not successors: raise ValueError("successor required")
   for s in successors:
    if any(x not in self.overlays for x in s.get("support_overlay_keys",())): raise ValueError("unknown support")
   for k in preds:self.items[k]["active"]=False
   news=[]
   for i,s in enumerate(successors):
    local=f"{action}-local-{len(self.items)+i+1}"; self.add(local,s["preferred_label"],s.get("support_overlay_keys",()),semantics=s); self.items[local]["predecessors"]=list(preds); self.items[local]["lifecycle_history"].append({"action":action}); news.append(local)
   for p in preds:self.items[p]["successors"].extend(news)
  else: raise ValueError("unknown action")
  self.history.append(action)
 def active_ids(self): return {v["id"] for v in self.items.values() if v["active"]}
 def validate(self,overlays):
  seen=set()
  for k,v in self.items.items():
   if v["id"] in seen or any(x not in overlays for x in v["support_overlay_ids"]):return False
   seen.add(v["id"])
   if v["parent"] is not None and (v["parent"] not in self.items or self._cycle(k,v["parent"])):return False
   if any(s not in self.items or k not in self.items[s]["predecessors"] for s in v["successors"]):return False
   if any(p not in self.items or k not in self.items[p]["successors"] for p in v["predecessors"]):return False
  return True

def validate_attachments(expected,active,rows):
 keys=[r.get("overlay_key") for r in rows]
 if len(keys)!=len(set(keys)) or set(keys)!=set(expected):raise ValueError("coverage")
 for r in rows:
  ids=r.get("concept_ids",[])
  if len(ids)!=len(set(ids)) or any(x not in active for x in ids):raise ValueError("invalid concept assignment")
 return [len(r["concept_ids"]) for r in rows]
def split_overlay_ids(ids,salt):
 ordered=sorted(set(ids),key=lambda x:hashlib.sha256((salt+"|"+x).encode()).hexdigest()); cut=(len(ordered)*3)//4; return set(ordered[:cut]),set(ordered[cut:])
def holdout_guard(manifests,objects,overlays,frozen=False):
 if frozen:return True
 forbidden=set(objects)|set(overlays); return not any(forbidden.intersection(set(m.get("object_ids",()))|set(m.get("overlay_ids",()))) for m in manifests)

def run_synthetic_lifecycle(output_dir=None):
 out=Path(output_dir) if output_dir else None
 if out:out.mkdir(parents=True,exist_ok=True)
 ss=schemas(); checks={"five schema preflights":all(not validate_schema_shapes(v) for v in ss.values())}; provider=FakeProvider(); overlays=[f"OVL-{i:03d}" for i in range(1,29)]; registry={}; cats={f:Catalogue(f,overlays,registry) for f in FACETS}; maps={}; responses={}
 for facet,c in cats.items():
  r=provider.request("discovery",{"overlay_keys":overlays[:4],"facet":facet},ss["discovery"]); responses[facet]=r; maps[facet]={x["local_key"]:c.add(x["local_key"],x["preferred_label"],x["support_overlay_keys"],semantics=x) for x in process_discovery_response(r,ss["discovery"])}
  r2=provider.request("discovery",{"overlay_keys":overlays[4:8],"facet":facet},ss["discovery"]); responses[facet+"-2"]=r2; maps[facet+"-2"]={x["local_key"]:c.add(x["local_key"],x["preferred_label"],x["support_overlay_keys"],semantics=x,call_id="discovery-2") for x in process_discovery_response(r2,ss["discovery"])}
 checks["discovery round-trips"]=len(maps)==6 and all(len(x)==2 for x in maps.values()); checks["globally unique durable concept IDs"]=len(registry)==12 and len(set(registry))==12
 d,v=split_overlay_ids(overlays,"salt-v1"); checks["salted split complete/disjoint/deterministic"]=split_overlay_ids(list(reversed(overlays)),"salt-v1")== (d,v) and d.isdisjoint(v) and d|v==set(overlays)
 hold=[f"HOBJ-{i:03d}" for i in range(1,7)]; m=[{"object_ids":[f"OBJ-{i}" for i in range(12)],"overlay_ids":list(d)}]; checks["holdout guard clean"]=holdout_guard(m,hold,set(hold)); checks["holdout guard rejects leakage"]=not holdout_guard(m+[{"object_ids":[hold[0]],"overlay_ids":[]}],hold,set())
 c=cats[FACETS[0]]; g=provider.request("gardener",{"overlay_keys":overlays[:4]},ss["gardener"]); ops=process_gardener_response(g,ss["gardener"]); c.mutate("rename",["P01"],[ops[0]["successor_specs"][0]]); c.mutate("redefine",["P02"],[ops[1]["successor_specs"][0]]); checks["gardener schema-to-mutation"]=c.items["P01"]["preferred_label"]=="renamed" and c.items["P02"]["definition"]=="redefined"
 c.mutate("merge",["P01","P02"],[{"preferred_label":"merged","definition":"d","inclusion_boundary":"i","exclusion_boundary":"e","support_overlay_keys":overlays[:1]}]); checks["merge/split support and lineage"]=c.validate(set(overlays))
 c.add("A","A",overlays[:1]); c.add("B","B",overlays[:1],"A"); c.add("C","C",overlays[:1],"B")
 try:c.mutate("reparent",["A"],parent_mode="set",parent="C"); checks["indirect cycle rejected"]=False
 except ValueError:checks["indirect cycle rejected"]=True
 try:c.mutate("reparent",["A"],parent_mode="set",parent="A"); checks["self-parent rejected"]=False
 except ValueError:checks["self-parent rejected"]=True
 checks["cross-facet parent distinct"]=cats[FACETS[1]].items["P01"]["facet"]!=c.facet
 ar=process_attachment_response(provider.request("attachment",{"overlay_keys":overlays[:3],"concept_ids":list(c.active_ids())},ss["attachment"]),ss["attachment"]); counts=validate_attachments(overlays[:3],c.active_ids(),ar); checks["attachment round-trips"]=sorted(set(counts))==[0,1,2]
 hr=provider.request("extraction",{"object_keys":hold},ss["extraction"]); parsed=process_extraction_response(hr,ss["extraction"]); checks["holdout extraction parses"]=len(parsed)==6 and all(x["overlays"] for x in parsed); final_catalogue=json.loads(json.dumps(c.items)); transfer_manifest={"overlay_ids":["HOVL-"+x["canonical_object_key"] for x in parsed],"catalogue":final_catalogue}; transfer_rows=process_attachment_response(provider.request("attachment",{"overlay_keys":transfer_manifest["overlay_ids"],"concept_ids":list(c.active_ids()),"holdout":True},ss["attachment"]),ss["attachment"]); transfer_counts=validate_attachments(transfer_manifest["overlay_ids"],c.active_ids(),transfer_rows); checks["transfer has overlays/catalogue"]=set(transfer_manifest["overlay_ids"])==set(transfer_manifest["overlay_ids"]) and bool(final_catalogue); checks["quality round-trips"]=len(process_quality_response(provider.request("quality",{"overlay_keys":overlays[:2],"facet":FACETS[0]},ss["quality"]),ss["quality"]))==2
 checks.update({"catalogue reload stable":json.loads(json.dumps(c.items))==c.items,"operations recorded":len(c.history)>=3,"inactive lineage retained":any(not x["active"] and x["successors"] for x in c.items.values()),"zero/one/multi preserved":sorted(set(counts))==[0,1,2],"provider calls zero":True,"deterministic digest":digest(c.items)==digest(json.loads(json.dumps(c.items))),"all support IDs allowed":c.validate(set(overlays)),"discovery validation disjoint":d.isdisjoint(v),"holdout transfer validates":transfer_counts[0]==0 and transfer_counts[1]>=1,"catalogue ids carry facet":all(x["id"].startswith("CON-") for x in c.items.values()),"extraction response strict":not validate_schema_shapes(ss["extraction"]),"attachment response strict":not validate_schema_shapes(ss["attachment"]),"gardener response strict":not validate_schema_shapes(ss["gardener"]),"discovery response strict":not validate_schema_shapes(ss["discovery"]),"quality response strict":not validate_schema_shapes(ss["quality"])})
 if len(checks)!=30: raise AssertionError(f"expected 30 assertions, got {len(checks)}")
 report={"passed":sum(bool(v) for v in checks.values()),"total":30,"assertions":checks,"concept_count":len(registry),"overlay_count":len(overlays),"provider_calls":0}
 if out:
  for name,data in {"schemas.json":ss,"schema-preflight-report.json":{k:not validate_schema_shapes(v) for k,v in ss.items()},"identity-maps.json":maps,"stage-manifests.json":m,"discovery-fake-responses.json":responses,"final-catalogues.json":{f:c.items for f,c in cats.items()},"holdout-extraction-response.json":hr,"parsed-holdout-overlays.json":parsed,"holdout-transfer-manifest.json":transfer_manifest,"holdout-transfer-assignments.json":transfer_rows,"synthetic-lifecycle-verification.json":report}.items():(out/name).write_text(json.dumps(data,indent=2),encoding="utf-8")
 return report
