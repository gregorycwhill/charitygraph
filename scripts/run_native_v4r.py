"""V4R corrected Native faceted Semantic Lab runner (experiment only)."""
from __future__ import annotations
import hashlib, json, sys, time
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, r"C:\tmp\charitygraph-semantic-lab-docs\scripts")
from run_native_induction_v1 import load_observations
from charitygraph.openai_client import OpenAIRequestError, estimate_response_cost, responses_create

ROOT=Path(r"C:\CharityGraph-runtime\native-induction-v4r-faceted-disposition-repair")
LUNA="gpt-5.6-luna"; TERRA="gpt-5.6-terra"; CAP=Decimal("1.50"); spent=Decimal("0"); calls=[]
FAMILIES=["regulatory_source_fact","identity_attribute","program_service_structure","population_beneficiary","graph_relationship_instance","geography_location","finance_resource_flow","governance_role_or_structure","position_or_commitment_observation","outcome_or_evaluation_observation","temporal_history_event","evidence_coverage_metadata","external_scheme_assignment","native_candidate","other_governed_non_native"]
FACETS=["operational_activity","participation","fundraising_mode","relationship_role","governance_practice","capability_access","ethos_conduct","evaluation_method","other_native_residual"]
def write(name,obj): p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
def digest(v): return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def O(fields,req): return {"type":"object","additionalProperties":False,"properties":fields,"required":req}
def strict(s,path="$"):
 e=[]; typ=s.get("type"); ts=typ if isinstance(typ,list) else [typ]
 if "object" in ts:
  if s.get("additionalProperties") is not False:e.append(path)
  if not isinstance(s.get("properties"),dict) or set(s["properties"])!=set(s.get("required",[])):e.append(path+".required")
  for k,v in s.get("properties",{}).items():
   if isinstance(v,dict):e+=strict(v,path+"."+k)
 if "array" in ts and isinstance(s.get("items"),dict):e+=strict(s["items"],path+"[]")
 return e
OBJ=O({"statement":{"type":"string","minLength":1},"representation_family":{"type":"string","enum":FAMILIES},"facet_hint":{"type":["string","null"],"enum":FACETS+[None]},"rationale":{"type":"string","minLength":1},"qualification":{"type":"string","minLength":1}},["statement","representation_family","facet_hint","rationale","qualification"])
DISP=O({"local_key":{"type":"string","pattern":"^O[0-9]{2}$"},"objects":{"type":"array","items":OBJ,"minItems":1}},["local_key","objects"])
DISP_SCHEMA=O({"dispositions":{"type":"array","items":DISP}},["dispositions"])
AUD=O({"local_key":{"type":"string","pattern":"^O[0-9]{2}$"},"families":{"type":"array","items":{"type":"string","enum":FAMILIES}},"has_native":{"type":"boolean"},"facets":{"type":"array","items":{"type":"string","enum":FACETS}}},["local_key","families","has_native","facets"])
AUD_SCHEMA=O({"audits":{"type":"array","items":AUD}},["audits"])
CF={"preferred_label":{"type":"string","minLength":1},"definition":{"type":"string","minLength":1},"inclusion_boundary":{"type":"string","minLength":1},"exclusion_boundary":{"type":"string","minLength":1},"support_keys":{"type":"array","items":{"type":"string"}},"parent_key":{"type":["string","null"]},"uncertainty":{"type":"string","minLength":1}}
DISC_SCHEMA=O({"concepts":{"type":"array","items":O(CF,list(CF))}},["concepts"])
OPF={"action":{"type":"string","enum":["retain","rename","redefine","merge","split","reparent","deprecate","dispose_non_native"]},"concept_keys":{"type":"array","items":{"type":"string"}},"parent_mode":{"type":"string","enum":["unchanged","set","remove"]},"new_parent_key":{"type":["string","null"]},"successors":{"type":"array","items":O(CF,list(CF))},"representation_family":{"type":["string","null"],"enum":FAMILIES+[None]},"rationale":{"type":"string","minLength":1}}
OP_SCHEMA=O({"operations":{"type":"array","items":O(OPF,list(OPF))}},["operations"])
AT=O({"local_key":{"type":"string","pattern":"^O[0-9]{2}$"},"concept_keys":{"type":"array","items":{"type":"string"}},"ambiguity":{"type":["string","null"]}},["local_key","concept_keys","ambiguity"])
ATT_SCHEMA=O({"attachments":{"type":"array","items":AT}},["attachments"])
PROMPT="""CharityGraph Native V4R representation disposition. Use only the supplied governed observations. Return exactly one disposition for every supplied local key and at least one semantic object. Route each object to one explicit representation family. Use native_candidate only for a reusable CharityGraph-specific TYPE, MODE, ROLE, PRACTICE or distinction not adequately represented elsewhere; otherwise use the best non-Native family. A proposition may produce multiple distinct objects. Supply facet_hint only for native_candidate. Do not use prior Native concepts, external taxonomies, outside knowledge or semantic keyword rules."""
def projection(rows):
 return [{"local_key":f"O{i+1:02d}","subject":r["subject"],"section_id":r.get("section_id"),"scope":r.get("scope"),"proposition":r.get("proposition"),"epistemic_status":r.get("epistemic_status"),"temporal_scope":r.get("temporal_scope"),"evidence":r.get("evidence"),"qualifications":r.get("qualifications")} for i,r in enumerate(rows)]
def call(label,model,prompt,payload,schema,maxout=6000):
 global spent
 if strict(schema): raise RuntimeError("strict schema defect")
 text=prompt+"\nINPUT:\n"+json.dumps(payload,ensure_ascii=False,separators=(",",":"))
 est=estimate_response_cost(model,type("U",(),{"input_tokens":max(1,len(text)//4),"output_tokens":maxout})())
 est=Decimal(str(est or 0))
 if spent+est>CAP: raise RuntimeError(f"cap before {label}")
 started=time.perf_counter()
 try:
  r=responses_create(model=model,input_text=text,text_format={"type":"json_schema","name":"native_v4r","strict":True,"schema":schema},max_output_tokens=maxout,max_attempts=1,timeout_seconds=300,reasoning={"effort":"none" if model==LUNA else "high"})
  u=r.usage; actual=Decimal(str(estimate_response_cost(model,u) or 0));spent+=actual
  meta={"label":label,"model":model,"reasoning":"none" if model==LUNA else "high","max_output_tokens":maxout,"status":r.status,"response_id":r.response_id,"input_tokens":u.input_tokens,"output_tokens":u.output_tokens,"total_tokens":u.total_tokens,"cost_usd":str(actual),"latency_seconds":round(time.perf_counter()-started,3),"transport_attempts":getattr(r,"transport_requests",None)}
  out=r.output_text
 except OpenAIRequestError as ex:
  meta={"label":label,"model":model,"status":"error","error_class":type(ex).__name__,"error":str(ex)[:300],"cost_usd":"0","latency_seconds":round(time.perf_counter()-started,3)};out=""
 write("raw/"+label+".json",{"metadata":meta,"output_text":out});calls.append(meta)
 try:return {"metadata":meta,"output":json.loads(out)}
 except Exception:return {"metadata":meta,"output":None}
def main():
 ROOT.mkdir(parents=True,exist_ok=True); allrows=load_observations()
 # Phase 0 forensic audit of V4.
 old=Path(r"C:\CharityGraph-runtime\native-induction-v4-faceted-disposition"); oldraw=sorted((old/"raw").glob("stage-a-*.json"))
 forensic={"expected_stage_a_batches":10,"persisted_batches":len(oldraw),"lost_first_batch":not (old/"raw"/"stage-a-01.json").exists(),"known_defects":["first batch not persisted","no exact coverage validation","empty objects permitted","durable IDs model-facing","Terra saw Luna outputs","external set not unseen","paid same-cohort external call","operations not applied","arms not independent","round-2 state not chained","splits not guaranteed disjoint","attachments not held-out"]}
 write("v4-forensic-audit.json",forensic)
 by=defaultdict(list)
 for r in allrows:by[r["subject"]].append(r)
 workshop=allrows[:] ; batches=[workshop[i::18] for i in range(18)]
 disposition=[]; stats={"expected":len(workshop),"returned":0,"missing":0,"duplicates":0,"unknown":0,"zero":0,"one":0,"multi":0}
 for n,b in enumerate(batches,1):
  local=projection(b); expected={x["local_key"] for x in local}
  res=call(f"stage-a-{n:02d}",LUNA,PROMPT+f"\nFamilies: {FAMILIES}\nFacets: {FACETS}",{"observations":local},DISP_SCHEMA)
  arr=(res["output"] or {}).get("dispositions",[]); seen=[]
  for d in arr:
   k=d.get("local_key"); stats["returned"]+=1
   if k not in expected:stats["unknown"]+=1;continue
   if k in seen:stats["duplicates"]+=1;continue
   seen.append(k); objs=d.get("objects",[])
   if not objs:stats["zero"]+=1
   elif len(objs)==1:stats["one"]+=1
   else:stats["multi"]+=1
   if objs:disposition.append({"local_key":k,"source_observation_id":b[int(k[1:])-1]["observation_id"],"subject":b[int(k[1:])-1]["subject"],"objects":objs})
  stats["missing"]+=len(expected-set(seen))
 write("stage-a-diagnostics.json",stats);write("stage-a-dispositions.json",disposition)
 # independent Terra audit over original observations.
 sample=workshop[:90]; terra=[]
 for n in range(6):
  b=sample[n::6]; local=projection(b);res=call(f"terra-audit-{n+1:02d}",TERRA,"Independent Terra representation audit. Use ORIGINAL observations only; do not use Luna outputs.",{"observations":local},AUD_SCHEMA)
  terra.extend((res["output"] or {}).get("audits",[]))
 write("terra-audit.json",{"audits":terra,"calls":6})
 # Main Luna pools.
 native=[{"source_observation_id":d["source_observation_id"],"subject":d["subject"],**o} for d in disposition for o in d["objects"] if o.get("representation_family")=="native_candidate" and o.get("facet_hint")]
 pools=defaultdict(list)
 for x in native:pools[x["facet_hint"]].append(x)
 pool_summary={f:{"objects":len(v),"organisations":len({x["subject"] for x in v})} for f,v in pools.items()}
 qualifying=sorted([f for f,v in pool_summary.items() if v["objects"]>=6 and v["organisations"]>=2],key=lambda f:(-pool_summary[f]["objects"],-pool_summary[f]["organisations"],f))[:3]
 write("facet-pools.json",{"pool_summary":pool_summary,"native_objects":len(native),"qualifying_facets":qualifying})
 # Boundary pressure is mandatory when fewer than two facets qualify.
 boundary=[]
 if len(qualifying)<2:
  candidates=[x for d in disposition for x in d["objects"] if x.get("representation_family")!="native_candidate"][:90]
  for n in range(6):
   b=candidates[n::6];res=call(f"boundary-pressure-{n+1:02d}",TERRA,"Boundary pressure review. Preserve the original non-Native representation; identify only additional reusable Native residuals, if directly supported.",{"semantic_objects":b},DISC_SCHEMA)
   boundary.extend((res["output"] or {}).get("concepts",[]))
 write("boundary-pressure.json",{"objects_tested":sum(len([x for d in disposition for x in d["objects"] if x.get("representation_family")!="native_candidate"][:90][n::6]) for n in range(6)),"candidates":boundary,"calls":6})
 # No facet stages are fabricated unless qualifying facets exist.
 summary={"experiment_id":"native-induction-v4r-faceted-disposition-repair","workshop_observations":len(workshop),"stage_a":stats,"terra_audit_calls":6,"native_candidate_objects":len(native),"native_candidate_observations":len({x["source_observation_id"] for x in native}),"facet_pools":pool_summary,"qualifying_facets":qualifying,"boundary_pressure_ran":len(qualifying)<2,"boundary_pressure_candidates":len(boundary),"calls":calls,"provider_calls":len(calls),"actual_cost_usd":str(spent),"production_native_persistence":False}
 write("summary.json",summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
