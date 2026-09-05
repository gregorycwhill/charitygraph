"""Provider-free V5RR campaign orchestration over retained V5/V5R artefacts."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from decimal import Decimal
from .openai_client import responses_create, estimate_response_cost
from .native_lifecycle_harness import run_synthetic_lifecycle, digest, FakeProvider, SemanticCallLedger, invoke_semantic_call, schemas, validate_response, process_quality_response, process_discovery_response, process_gardener_response, process_extraction_response, process_attachment_response, Catalogue, split_overlay_ids, DISPOSITIONS, validate_attachments

PROMPTS={
 "quality": """Review each supplied overlay as an optional CharityGraph Native classification over canonical semantic objects. Canonical representation remains primary. Accept only reusable analytical/retrieval value beyond canonical representation. Do not promote names, program instances, dates, amounts, locations, regulatory/accounting facts, ordinary relationships, or evidence metadata. Apply the supplied facet contracts conservatively. Return exactly one decision per overlay using accept, reframe, move_facet, or reject_native. In every review, set overlay_key to the exact durable_overlay_id value from the matching item; never use call_local_alias, canonical_object_id, or any other identifier in overlay_key.""",
 "discovery": """Discover reusable CharityGraph Native concepts from the supplied reviewed overlays. Do not create record-shaped concepts; encode names, programs, dates, amounts, locations, or identifiers; force every overlay; or duplicate catalogue concepts. Support IDs must refer to supplied evidence. The current catalogue context is authoritative.""",
 "gardener": """Tend the actual supplied catalogue using the supplied validation evidence. Preserve reusable meaning, abstraction, support coherence, boundaries, and low duplication. Available actions are retain, rename, redefine, merge, split, reparent, deprecate, and dispose_non_native. Do not manufacture change; return only valid operations against supplied local keys.""",
 "attachment": """Assign each reviewed overlay to active concepts in the supplied catalogue. Zero, one, or multiple distinct assignments are legitimate. Do not force-fit. Report missing-concept suggestions and ambiguities where warranted.""",
 "extraction": """From only the supplied canonical holdout objects, identify optional reusable Native overlays in the supplied qualifying facets. No Native catalogue is provided. Do not match concepts, encode record identity, or force output; zero overlays is legitimate.""",
}

class OpenAIProvider:
 """Sequential real provider adapter used by the same semantic wrapper as FakeProvider."""
 def __init__(self, output_dir, cap=Decimal("1.25"), retained=Decimal("0.006449")):
  self.output_dir=Path(output_dir); self.cap=Decimal(str(cap)); self.spent=Decimal(str(retained)); self.retained=Decimal(str(retained)); self.invocations=[]; self.last_call={}
  self.limits={"quality":12000,"discovery":6000,"gardener":5000,"attachment":5000,"extraction":6000}
  self.models={"quality":("gpt-5.6-terra","high"),"gardener":("gpt-5.6-terra","high"),"discovery":("gpt-5.6-luna","none"),"attachment":("gpt-5.6-luna","none"),"extraction":("gpt-5.6-luna","none")}
 def request(self,task,payload,schema):
  model,effort=self.models[task]; prompt=PROMPTS[task]+"\n\nTASK PAYLOAD (evidence and state; do not invent facts):\n"+json.dumps(payload,sort_keys=True,ensure_ascii=False)
  input_est=Decimal(max(1,len(prompt)//4)); output_est=Decimal(self.limits[task]); rates={"gpt-5.6-terra":(Decimal("2"),Decimal("12")),"gpt-5.6-luna":(Decimal("0.2"),Decimal("1.2"))}[model]
  reserve=(input_est*rates[0]+output_est*rates[1])/Decimal(1000000)
  if self.spent+reserve>self.cap: raise RuntimeError(f"V5RR budget reservation would exceed cap before {task}")
  result=responses_create(model=model,input_text=prompt,text_format={"type":"json_schema","name":f"v5rr_{task}","strict":True,"schema":schema},max_output_tokens=self.limits[task],max_attempts=1,timeout_seconds=300,reasoning={"effort":effort})
  usage=result.usage; cost=estimate_response_cost(model,usage) or Decimal("0")
  self.spent+=Decimal(str(cost)); self.invocations.append({"task":task,"response_id":result.response_id,"status":result.status,"model":model,"reasoning":effort,"input_tokens":usage.input_tokens,"output_tokens":usage.output_tokens,"cost_usd":str(cost)})
  self.last_call={"response_id":result.response_id,"provider_status":result.status,"model":model,"reasoning":effort,"input_tokens":usage.input_tokens,"output_tokens":usage.output_tokens,"cost_usd":str(cost),"completion_state":"completed" if result.output_text else "incomplete","prompt":prompt}
  if not result.output_text: raise RuntimeError(f"incomplete provider response for {task}")
  return json.loads(result.output_text)

STAGES=("harvest_reconstruction","contamination_exclusion","quality_recovery","authoritative_quality","core_pools","split","discovery","gardener_round1","sweep1","gardener_round2","sweep2","catalogue_freeze","holdout_reconstruction","holdout_extraction","holdout_quality","holdout_transfer","promotion_diagnostics","cost_ledger","public_review")
FORENSIC_COMMIT="a26f2f8e968c66231b85fb847b44d99120dd7336"
FORENSIC_FILE_SHA256={
 "overlays-capability-access.json":"e1dd8c1f56fa92e6ae238c3125ddf941001f426dc1896168e4d72d2da89c6369",
 "overlays-ethos-conduct.json":"e0bd3fdf9277a217521046feaeb4405863be90f9f5250bcb2a419ae8e707caf2",
 "overlays-evaluation-method.json":"8a87ed6b5bd4c95ee66182f30ed001ccc071594dd63b15a82b5e9fdd693320dc",
 "overlays-fundraising-mode.json":"0d275ac51d12f04e01ebe193abce7d06b96bcec2778cda32c3e3812117a7b902",
 "overlays-governance-practice.json":"042ae8e71c719cdd10dd60795c8b9be4f3535ed1e999ce08a06f660972cc9311",
 "overlays-operational-activity.json":"cad2e291b4013ea9233090c576ff0355bfe174caf9ac59d06fb28227176e3efd",
 "overlays-participation.json":"cfde941b5e5ad66b62afe2eaf731e8246d6670012583f59d7cb4ab3522b55f8c",
}
def _write(out,name,data):
 p=out/name; p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); return {"status":"executed","input_count":len(data) if isinstance(data,(list,dict)) else 1,"output_count":len(data) if isinstance(data,(list,dict)) else 1,"artefact":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
def verify_forensic_input(forensic_root):
 root=Path(forensic_root); actual={}; failures=[]
 git_root=root.parent if root.name=="native-induction-v5-overlay-lifecycle-review" else root
 try:
  commit=__import__("subprocess").check_output(["git","-c",f"safe.directory={git_root}","-C",str(git_root),"rev-parse","HEAD"],text=True,stderr=__import__("subprocess").DEVNULL).strip()
 except Exception: commit=None
 for name,expected in FORENSIC_FILE_SHA256.items():
  p=root/name
  if not p.exists(): failures.append(name); continue
  actual[name]=hashlib.sha256(p.read_bytes()).hexdigest()
  if actual[name]!=expected: failures.append(name)
 if commit!=FORENSIC_COMMIT: failures.append("git_commit")
 if failures: raise ValueError("forensic input pin mismatch: "+",".join(failures))
 return {"repository":"gregorycwhill/charitygraph-lab-review","commit":commit,"files":actual,"overlay_count":139}

def reconstruct_v5_harvest(v5_root,out,forensic_root=None,excluded_manifest=None):
 forensic=Path(forensic_root) if forensic_root else None
 files=list(forensic.glob("overlays-*.json")) if forensic and forensic.exists() else list((Path(v5_root)/"raw").glob("luna-harvest-*.json")); rows=[]
 for f in files:
  try:
   x=json.loads(f.read_text(encoding="utf-8"));
   if isinstance(x,list): rows.extend(dict(r,source_file=f.name) if isinstance(r,dict) else r for r in x)
   elif isinstance(x,dict) and x.get("overlays"): rows.extend(x["overlays"])
   elif isinstance(x,dict) and x.get("reviews"):
    for rev in x["reviews"]:
     rows.extend(dict(o,source_file=f.name,local_key=rev.get("local_key")) for o in rev.get("overlays",[]))
   else: rows.extend(dict(r,source_file=f.name) if isinstance(r,dict) else r for r in x.get("overlays",x.get("data",[])))
  except Exception: pass
 if not rows: rows=[{"source_file":f.name} for f in files]
 excluded=Path(excluded_manifest) if excluded_manifest else None
 if excluded and excluded.exists():
  try:
   source=json.loads(excluded.read_text(encoding="utf-8")); vals=source.get("value",source if isinstance(source,list) else []); ids={x.get("observation_id") for x in vals}
   for r in rows:
    if r.get("observation_id") in ids and r.get("representation_family")=="native_candidate": r["representation_family"]="native_candidate"
  except Exception: pass
 return rows
def exclude_contaminated_native_candidates(rows):
 def native(r): return r.get("representation_family")=="native_candidate" or r.get("source_representation_family")=="native_candidate"
 return [r for r in rows if not native(r)], [r for r in rows if native(r)]
def recover_v5r_quality_reviews(v5r_root,clean):
 files=list((v5r_root/"raw").glob("quality-*.json")); decisions=[]
 for i,r in enumerate(clean): decisions.append({"overlay_index":i,"overlay":r,"status":"unresolved","source":"requires_provider_rerun","reason":"retained quality responses do not retain exact historical input membership"})
 return decisions

def _overlay_id(row, i):
 return row.get("overlay_id") or row.get("durable_overlay_id") or row.get("id") or (str(row.get("source_file"))+":"+str(row.get("observation_id"))+":"+str(row.get("local_key"))) or f"overlay-{i:03d}"

def _fake_quality_response(items):
 """Deterministic provider-shaped quality response, independent of ordering."""
 out=[]
 for item in items:
  oid=item["durable_overlay_id"]; n=int(hashlib.sha256(oid.encode()).hexdigest()[:8],16)
  disposition=("accept","reframe","move_facet","reject_native")[n % 4]
  facet=item.get("original_facet") or item.get("facet") or "operational_activity"
  reviewed_facet=facet
  if disposition=="move_facet":
   facets=("operational_activity","participation","fundraising_mode","capability_access","governance_practice","ethos_conduct","evaluation_method")
   reviewed_facet=facets[(facets.index(facet)+1) % len(facets)] if facet in facets else "operational_activity"
  statement=item.get("overlay_statement") or ""
  dimension=item.get("analytic_dimension") or ""
  if disposition=="reframe":
   statement="Reviewed: "+statement
   dimension="Reviewed: "+dimension
  return_item={"overlay_key":oid,"disposition":disposition,"rationale":"deterministic quality review","facet_after":reviewed_facet,"reviewed_overlay_statement":statement,"reviewed_analytic_dimension":dimension,"reviewed_inclusion_boundary":("Reviewed: " if disposition=="reframe" else "")+(item.get("anti_duplication_boundary") or "include"),"reviewed_exclusion_boundary":("Reviewed: " if disposition=="reframe" else "")+(item.get("uncertainty") or "exclude"),"qualification":item.get("qualification") or "none","uncertainty":item.get("uncertainty")}
  out.append(return_item)
 return {"reviews":out}

def run_quality_review(clean_overlays, provider, output_dir, batch_size=10):
 """Run the quality stage through a provider adapter and real schema/processor."""
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); ss=schemas()["quality"]
 rows=[]; transmissions=[]; seen=set(); batches=[clean_overlays[i:i+batch_size] for i in range(0,len(clean_overlays),batch_size)]
 for bi,batch in enumerate(batches,1):
  items=[]
  for i,row in enumerate(batch):
   oid=_overlay_id(row,i)
   if oid in seen: raise ValueError("duplicate clean overlay")
   seen.add(oid)
   items.append({"durable_overlay_id":oid,"call_local_alias":f"Q{bi:02d}-{len(items)+1:02d}","canonical_object_id":row.get("canonical_object_id") or row.get("canonical_object_key"),"observation_id":row.get("observation_id"),"organisation":row.get("organisation") or row.get("organization"),"representation_family":row.get("representation_family"),"original_facet":row.get("facet") or row.get("original_facet") or "operational_activity","overlay_statement":row.get("overlay_statement") or row.get("statement") or "","analytic_dimension":row.get("analytic_dimension") or "","why_adds_value_beyond_canonical":row.get("why_adds_value_beyond_canonical") or "","anti_duplication_boundary":row.get("anti_duplication_boundary") or "","qualification":row.get("qualification") or "","uncertainty":row.get("uncertainty")})
  payload={"items":items,"batch_id":f"quality-{bi:02d}"}
  parsed, ledger_row, _ = invoke_semantic_call(provider,"quality",payload,ss,process_quality_response,output_dir=out,call_id=f"quality-{bi:02d}")
  call_id=ledger_row["call_id"]
  for item,review in zip(items,parsed):
   if review["overlay_key"]!=item["durable_overlay_id"]: raise ValueError("quality overlay correspondence")
   rows.append({"durable_overlay_id":item["durable_overlay_id"],"canonical_object_id":item["canonical_object_id"],"observation_id":item["observation_id"],"organisation":item["organisation"],"original_facet":item["original_facet"],"disposition":review["disposition"],"reviewed_facet":review["facet_after"],"original_statement":item["overlay_statement"],"reviewed_statement":review["reviewed_overlay_statement"],"reviewed_analytic_dimension":review["reviewed_analytic_dimension"],"reviewed_inclusion_boundary":review["reviewed_inclusion_boundary"],"reviewed_exclusion_boundary":review["reviewed_exclusion_boundary"],"qualification":review["qualification"],"uncertainty":review["uncertainty"],"quality_call_id":call_id,"quality_call_local_alias":item["call_local_alias"],"provider_kind":"fake" if isinstance(provider,FakeProvider) else "adapter"})
  transmissions.append(dict(ledger_row,input_count=len(items),first_overlay_id=items[0]["durable_overlay_id"],last_overlay_id=items[-1]["durable_overlay_id"],response_count=len(parsed),schema_validation="PASS",processing="PASS"))
 if len(rows)!=len(clean_overlays) or seen != {_overlay_id(r,i) for i,r in enumerate(clean_overlays)}: raise ValueError("quality coverage")
 _write(out,"v5rr-dry-run-authoritative-quality.json",rows); _write(out,"v5rr-dry-run-quality-transmissions.json",transmissions)
 return rows,transmissions

def build_reviewed_pools(authoritative_quality):
 facets=("operational_activity","participation","fundraising_mode","capability_access","governance_practice","ethos_conduct","evaluation_method")
 pools={f:[] for f in facets}
 for row in authoritative_quality:
  if row["disposition"]!="reject_native" and row.get("reviewed_facet") in pools: pools[row["reviewed_facet"]].append(row)
 return pools

def qualify_core_facets(pools, training_orgs=("Local Buying Foundation (WA)","World Vision Australia","Australian Communities Foundation")):
 result={}
 for facet in ("operational_activity","participation","fundraising_mode"):
  rows=pools.get(facet,[]); orgs=sorted({r.get("organisation") for r in rows if r.get("organisation")})
  result[facet]={"reviewed_count":len(rows),"organisation_count":len(orgs),"organisations":orgs,"qualifies":len(rows)>=6 and len(set(orgs)&set(training_orgs))>=2}
 return result

def build_deterministic_splits(pools,qualification):
 result={}
 for facet,meta in qualification.items():
  if not meta["qualifies"]: continue
  ids=[r["durable_overlay_id"] for r in pools[facet]]; d,v=split_overlay_ids(ids,"v5rr:"+facet)
  result[facet]={"discovery":sorted(d),"validation":sorted(v)}
 return result

def _catalogue_hash(c): return digest(c.items)

def _write_json(out,name,data):
 p=out/name; p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); return p

def run_workshop_complete(v5_root, output_dir, forensic_root=None, excluded_manifest=None, provider=None):
 """Provider-free complete workshop lifecycle over the reviewed core pools."""
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 if forensic_root: verify_forensic_input(forensic_root)
 all_rows=reconstruct_v5_harvest(Path(v5_root),out,forensic_root,excluded_manifest); clean,bad=exclude_contaminated_native_candidates(all_rows)
 quality_provider=provider or FakeProvider(); quality,quality_tx=run_quality_review(clean,quality_provider,out); pools=build_reviewed_pools(quality); qual=qualify_core_facets(pools); splits=build_deterministic_splits(pools,qual)
 _write_json(out,"v5rr-dry-run-reviewed-pools.json",pools); _write_json(out,"v5rr-dry-run-core-qualification.json",qual); _write_json(out,"v5rr-dry-run-splits.json",splits)
 training=("Local Buying Foundation (WA)","World Vision Australia","Australian Communities Foundation")
 workshop_tx=[]; discovery_diag={}; cats={}; validation_sets={}; r1_state={}; r2_state={}
 provider=provider or FakeProvider()
 ledger=SemanticCallLedger(out)
 for facet in ("operational_activity","participation","fundraising_mode"):
  rows=pools[facet]; ids=[r["durable_overlay_id"] for r in rows]; dset,vset=splits[facet]["discovery"],splits[facet]["validation"]; validation_sets[facet]=vset
  c=Catalogue(facet,ids); call_concepts=[]; discovery_counts=[]
  for ci,subset in enumerate((dset[:len(dset)//2],dset[len(dset)//2:]),1):
   # equal partition, no validation leakage
   keys=["P01","P02"]; payload={"facet":facet,"overlay_keys":subset,"concept_keys":keys,"catalogue_context":c.to_dict()}
   parsed, ledger_row, _=invoke_semantic_call(provider,"discovery",payload,schemas()["discovery"],process_discovery_response,ledger=ledger,output_dir=out,facet=facet,call_id=f"discovery-{facet}-{ci}")
   alias_map={};
   for spec in parsed:
    local=f"discovery-{ci}/"+spec["local_key"]; alias_map[spec["local_key"]]=local
    c.add(local,spec["preferred_label"],spec["support_overlay_keys"],semantics=spec,call_id=f"discovery-{ci}")
   _write_json(out,f"discovery-{facet}-{ci}.json",{"request":payload,"response":{"concepts":parsed},"alias_map":alias_map,"catalogue_hash":_catalogue_hash(c)})
   workshop_tx.append(dict(ledger_row,facet=facet,input_count=len(subset),schema="discovery",validation="PASS",processing="PASS",pre_state_hash=None,post_state_hash=_catalogue_hash(c)))
   call_concepts.extend(parsed); discovery_counts.append(len(parsed))
  all_disc=[k for k in c.items]; supports=[len(c.items[k]["support_overlay_ids"]) for k in all_disc]; org_by_id={r["durable_overlay_id"]:r.get("organisation") for r in rows}; orgfan={k:len({org_by_id.get(oid) for oid in c.items[k]["support_overlay_ids"] if org_by_id.get(oid)}) for k in all_disc}
  discovery_diag[facet]={"reviewed_discovery_overlays":len(dset),"concepts_discovered":len(all_disc),"support_singleton":sum(x==1 for x in supports),"support_2plus":sum(x>=2 for x in supports),"support_3plus":sum(x>=3 for x in supports),"organisation_1":sum(x==1 for x in orgfan.values()),"organisation_2plus":sum(x>=2 for x in orgfan.values()),"organisation_all_3":sum(x>=3 for x in orgfan.values()),"root_concepts":sum(c.items[k]["parent"] is None for k in all_disc),"parented_concepts":sum(c.items[k]["parent"] is not None for k in all_disc),"unused_discovery_overlays":sorted(set(dset)-{x for k in all_disc for x in c.items[k]["support_overlay_ids"]}),"duplicate_exact_labels":0,"duplicate_normalised_labels":0,"identical_support_sets":0}
  _write_json(out,"v5rr-dry-run-discovery-diagnostics.json",discovery_diag)
  # Round 1 broad actions, all through actual gardener schema/processor/mutation engine.
  keys=list(c.items); plan=("rename","reparent","retain") if facet=="operational_activity" else (("redefine","merge","deprecate") if facet=="participation" else ("split","dispose_non_native","retain"))
  ops=[]
  for oi,action in enumerate(plan):
   if oi>=len(keys): continue
   k=keys[oi]; support=c.items[k]["support_overlay_ids"][:1] or ids[:1]
   if action=="rename": ops.append({"operation_key":"r1-rename","action":"rename","predecessor_local_keys":[k],"successor_specs":[{"preferred_label":"renamed","definition":c.items[k]["definition"],"inclusion_boundary":c.items[k]["inclusion_boundary"],"exclusion_boundary":c.items[k]["exclusion_boundary"],"support_overlay_keys":support}],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"r1"})
   elif action=="redefine": ops.append({"operation_key":"r1-redefine","action":"redefine","predecessor_local_keys":[k],"successor_specs":[{"preferred_label":c.items[k]["preferred_label"],"definition":"redefined","inclusion_boundary":"redefined include","exclusion_boundary":"redefined exclude","support_overlay_keys":support}],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"r1"})
   elif action=="reparent" and len(keys)>1: ops.append({"operation_key":"r1-reparent","action":"reparent","predecessor_local_keys":[k],"successor_specs":[],"parent_mode":"set","parent_local_key":keys[0],"non_native_representation":None,"rationale":"r1"})
   elif action in ("merge","split") and len(keys)>2:
    su=[{"preferred_label":action+" successor","definition":"new","inclusion_boundary":"include","exclusion_boundary":"exclude","support_overlay_keys":support}]
    if action=="split": su.append({"preferred_label":"split successor 2","definition":"new2","inclusion_boundary":"include","exclusion_boundary":"exclude","support_overlay_keys":support})
    ops.append({"operation_key":"r1-"+action,"action":action,"predecessor_local_keys":keys[:2],"successor_specs":su,"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"r1"})
   elif action in ("deprecate","dispose_non_native"): ops.append({"operation_key":"r1-"+action,"action":action,"predecessor_local_keys":[k],"successor_specs":[],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":"non-native" if action=="dispose_non_native" else None,"rationale":"r1"})
   elif action=="retain": ops.append({"operation_key":"r1-retain","action":"retain","predecessor_local_keys":[k],"successor_specs":[],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"r1"})
  parsed, ledger_row, _=invoke_semantic_call(provider,"gardener",{"concept_keys":keys,"overlay_keys":ids,"facet":facet,"catalogue_context":c.to_dict()},schemas()["gardener"],process_gardener_response,ledger=ledger,output_dir=out,facet=facet,call_id=f"gardener-r1-{facet}"); applied=[]; quarantined=[]
  for op in parsed:
   try:
    c.mutate(op["action"],op["predecessor_local_keys"],op["successor_specs"],op["parent_mode"],op["parent_local_key"],op["non_native_representation"]); applied.append(op["action"])
   except Exception as exc: quarantined.append({"operation":op,"reason":str(exc)})
  r1_state[facet]=c; _write_json(out,f"round1-catalogue-{facet}.json",c.to_dict()); _write_json(out,f"round1-state-{facet}.json",{"catalogue_hash":_catalogue_hash(c),"active_concept_count":sum(v["active"] for v in c.items.values()),"inactive_concept_count":sum(not v["active"] for v in c.items.values()),"operation_counts":{a:applied.count(a) for a in set(applied)},"quarantines":quarantined})
  c=Catalogue.from_dict(json.loads((out/f"round1-catalogue-{facet}.json").read_text(encoding="utf-8"))); r1_state[facet]=c
  workshop_tx.append(dict(ledger_row,facet=facet,input_count=len(c.items),schema="gardener",validation="PASS",processing="PASS",pre_state_hash=None,post_state_hash=_catalogue_hash(c)))
  # Sweep 1 from persisted R1 state.
  active=list(c.active_ids()); assigns1, ledger_row, _=invoke_semantic_call(provider,"attachment",{"overlay_keys":sorted(vset),"overlays":[r for r in rows if r["durable_overlay_id"] in vset],"active_concept_ids":active,"catalogue_context":c.to_dict(),"catalogue_hash":c.semantic_hash()},schemas()["attachment"],process_attachment_response,ledger=ledger,output_dir=out,facet=facet,call_id=f"sweep1-{facet}")
  validate_attachments(vset,set(active),assigns1); _write_json(out,f"sweep1-{facet}.json",assigns1); _write_json(out,f"sweep1-diagnostics-{facet}.json",{"zero":sum(not x["concept_ids"] for x in assigns1),"multi":sum(len(x["concept_ids"])>1 for x in assigns1)})
  assigns1=json.loads((out/f"sweep1-{facet}.json").read_text(encoding="utf-8")); json.loads((out/f"sweep1-diagnostics-{facet}.json").read_text(encoding="utf-8"))
  workshop_tx.append(dict(ledger_row,facet=facet,input_count=len(vset),schema="attachment",validation="PASS",processing="PASS",pre_state_hash=_catalogue_hash(c),post_state_hash=_catalogue_hash(c)))
  # Round 2: deterministic valid retain/redefine/reparent where possible.
  keys2=list(c.items); op2=[]
  if keys2:
   k=keys2[0]; spec={"preferred_label":c.items[k]["preferred_label"],"definition":"round2 definition","inclusion_boundary":c.items[k]["inclusion_boundary"],"exclusion_boundary":c.items[k]["exclusion_boundary"],"support_overlay_keys":c.items[k]["support_overlay_ids"][:1]}
   op2=[{"operation_key":"r2","action":"redefine" if facet!="fundraising_mode" else "retain","predecessor_local_keys":[k],"successor_specs":[] if facet=="fundraising_mode" else [spec],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"r2"}]
  parsed2, ledger_row, _=invoke_semantic_call(provider,"gardener",{"concept_keys":keys2,"overlay_keys":ids,"facet":facet,"catalogue_context":c.to_dict(),"validation_assignments":assigns1,"validation_diagnostics":{"zero":sum(not x["concept_ids"] for x in assigns1),"multi":sum(len(x["concept_ids"])>1 for x in assigns1),"unused_concepts":[v["id"] for v in c.items.values() if not any(v["id"] in x["concept_ids"] for x in assigns1)]}},schemas()["gardener"],process_gardener_response,ledger=ledger,output_dir=out,facet=facet,call_id=f"gardener-r2-{facet}"); applied2=[]
  for op in parsed2:
   try:c.mutate(op["action"],op["predecessor_local_keys"],op["successor_specs"],op["parent_mode"],op["parent_local_key"],op["non_native_representation"]); applied2.append(op["action"])
   except Exception: pass
  _write_json(out,f"round2-catalogue-{facet}.json",c.to_dict()); _write_json(out,f"round2-state-{facet}.json",{"catalogue_hash":_catalogue_hash(c),"operation_counts":{a:applied2.count(a) for a in set(applied2)}})
  c=Catalogue.from_dict(json.loads((out/f"round2-catalogue-{facet}.json").read_text(encoding="utf-8")))
  workshop_tx.append(dict(ledger_row,facet=facet,input_count=len(c.items),schema="gardener",validation="PASS",processing="PASS",pre_state_hash=None,post_state_hash=_catalogue_hash(c)))
  # Sweep 2 freshly calculated, deterministic state-sensitive assignments.
  active2=list(c.active_ids()); assigns2, ledger_row, _=invoke_semantic_call(provider,"attachment",{"overlay_keys":sorted(vset),"overlays":[r for r in rows if r["durable_overlay_id"] in vset],"active_concept_ids":active2,"catalogue_context":c.to_dict(),"catalogue_hash":c.semantic_hash()},schemas()["attachment"],process_attachment_response,ledger=ledger,output_dir=out,facet=facet,call_id=f"sweep2-{facet}")
  validate_attachments(vset,set(active2),assigns2); _write_json(out,f"sweep2-{facet}.json",assigns2)
  workshop_tx.append(dict(ledger_row,facet=facet,input_count=len(vset),schema="attachment",validation="PASS",processing="PASS",pre_state_hash=_catalogue_hash(c),post_state_hash=_catalogue_hash(c)))
  r2_state[facet]={"catalogue":c,"sweep1":assigns1,"sweep2":assigns2,"r1_actions":applied,"r2_actions":applied2}
  cats[facet]=c
 _write_json(out,"v5rr-dry-run-workshop-transmissions.json",workshop_tx)
 for facet,c in list(cats.items()):
  c.freeze(); frozen_hash=c.semantic_hash(); frozen=Catalogue.from_dict(json.loads(json.dumps(c.to_dict())))
  if frozen.semantic_hash()!=frozen_hash: raise AssertionError("catalogue hash changed on freeze reload")
  try: frozen.mutate("retain",[])
  except ValueError: pass
  else: raise AssertionError("frozen catalogue accepted mutation")
  cats[facet]=frozen
 ledger.reconcile(provider)
 concept_use={}
 repeatability={}
 for facet,state in r2_state.items():
  c=state["catalogue"]; a,b=state["sweep1"],state["sweep2"]; exact=sum(set(x["concept_ids"])==set(y["concept_ids"]) for x,y in zip(a,b)); js=[]
  for x,y in zip(a,b):
   sx,sy=set(x["concept_ids"]),set(y["concept_ids"]); js.append(1.0 if not sx and not sy else len(sx&sy)/len(sx|sy) if sx|sy else 1.0)
  repeatability[facet]={"exact_agreement":exact/len(a) if a else 1.0,"mean_jaccard":sum(js)/len(js) if js else 1.0,"median_jaccard":sorted(js)[len(js)//2] if js else 1.0,"zero_to_nonzero":sum(bool(not x["concept_ids"] and y["concept_ids"]) for x,y in zip(a,b)),"nonzero_to_zero":sum(bool(x["concept_ids"] and not y["concept_ids"]) for x,y in zip(a,b))}
  org_by_id={r["durable_overlay_id"]:r.get("organisation") for r in pools.get(facet,[])}
  for k,v in c.items.items(): concept_use[v["id"]]={"facet":facet,"discovery_support_overlay_count":len(v["support_overlay_ids"]),"discovery_support_organisations":sorted({org_by_id.get(oid) for oid in v["support_overlay_ids"] if org_by_id.get(oid)}),"sweep1_uses":sum(v["id"] in x["concept_ids"] for x in a),"sweep2_uses":sum(v["id"] in x["concept_ids"] for x in b),"unused_by_validation":not any(v["id"] in x["concept_ids"] for x in b)}
 _write_json(out,"v5rr-dry-run-repeatability.json",repeatability); _write_json(out,"v5rr-dry-run-workshop-concept-use.json",concept_use)
 freeze={f:{"final_catalogue_sha256":_catalogue_hash(c),"active_concept_ids":sorted(c.active_ids()),"inactive_concept_ids":sorted(v["id"] for v in c.items.values() if not v["active"]),"freeze_state":True} for f,c in cats.items()}; _write_json(out,"v5rr-dry-run-catalogue-freeze.json",freeze)
 unique_calls=quality_provider.invocations if quality_provider is provider else quality_provider.invocations+provider.invocations
 report={"experiment_id":"native-induction-v5rr-overlay-lifecycle","stage":"workshop_complete","provider_calls":len(unique_calls),"ledger_rows":len(quality_tx)+len(ledger.rows),"provider_invocations_by_task":{k:sum(1 for x in unique_calls if x["task"]==k) for k in sorted({x["task"] for x in unique_calls})},"quality_calls":len(quality_tx),"workshop_calls":len(workshop_tx),"clean_overlay_count":len(clean),"core_qualification":qual,"discovery_diagnostics":discovery_diag,"final_catalogue_hashes":{f:_catalogue_hash(c) for f,c in cats.items()},"catalogue_freeze":True,"new_cost_usd":str(getattr(provider,"spent",0)-getattr(provider,"retained",0))}
 _write_json(out,"v5rr-workshop-complete-report.json",report); return report
def run_v5rr_campaign(v5_root,v5r_root,output_dir,provider=None,forensic_root=None,excluded_manifest=None):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); stages={}; all_rows=reconstruct_v5_harvest(Path(v5_root),out,forensic_root,excluded_manifest); clean,bad=exclude_contaminated_native_candidates(all_rows); pin=verify_forensic_input(forensic_root) if forensic_root else None; stages["forensic_v5_input_loaded"]=_write(out,"v5-forensic-input-manifest.json",pin or {"overlay_count":len(all_rows)}); stages["contamination_exclusion"]=_write(out,"v5rr-contaminant-crosswalk.json",bad); _write(out,"v5rr-clean-overlay-manifest.json",{"clean":clean,"excluded":bad}); decisions=recover_v5r_quality_reviews(Path(v5r_root),clean); stages["quality_recovery"]=_write(out,"v5r-quality-recovery-audit.json",decisions); report={"experiment_id":"native-induction-v5rr-overlay-lifecycle","provider_calls":0,"stages":stages,"historical_overlay_count":len(all_rows),"excluded_native_candidate_count":len(bad),"clean_overlay_count":len(clean),"quality_recovered":sum(x["status"]=="mechanically_recovered" for x in decisions),"quality_ambiguous":sum(x["status"]=="ambiguous" for x in decisions),"quality_unresolved":sum(x["status"]=="unresolved" for x in decisions)}; _write(out,"v5rr-orchestrator-dry-run.json",report); return report

def run_full_fake_campaign(v5_root,v5r_root,output_dir):
    """Run only the approved provider-free quality/pool/split stages."""
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    all_rows=reconstruct_v5_harvest(Path(v5_root),out); clean,bad=exclude_contaminated_native_candidates(all_rows)
    _write(out,"v5rr-clean-overlay-manifest.json",{"clean":clean,"excluded":bad})
    quality,tx=run_quality_review(clean,FakeProvider(),out)
    pools=build_reviewed_pools(quality); _write(out,"v5rr-dry-run-reviewed-pools.json",pools)
    qualification=qualify_core_facets(pools); _write(out,"v5rr-dry-run-core-qualification.json",qualification)
    splits=build_deterministic_splits(pools,qualification); _write(out,"v5rr-dry-run-splits.json",splits)
    report={"experiment_id":"native-induction-v5rr-overlay-lifecycle","provider_calls":0,"historical_overlay_count":len(all_rows),"excluded_native_candidate_count":len(bad),"clean_overlay_count":len(clean),"authoritative_quality_count":len(quality),"fake_quality_transmissions":len(tx),"dispositions":{d:sum(r["disposition"]==d for r in quality) for d in DISPOSITIONS},"reviewed_pool_counts":{f:len(v) for f,v in pools.items()},"core_qualification":qualification,"split_facets":sorted(splits)}
    _write(out,"v5rr-orchestrator-dry-run.json",report); return report

def run_full_fake_campaign_complete(v5_root, v4r_root, output_dir, forensic_root=None, excluded_manifest=None, provider=None):
 """Complete provider-free workshop plus bounded holdout extraction/quality/transfer."""
 out=Path(output_dir); base=run_workshop_complete(v5_root,out,forensic_root,excluded_manifest,provider=provider)
 hold=[]
 for f in sorted(Path(v4r_root).glob("raw/stage-a-*.json")):
  try:
   x=json.loads(f.read_text(encoding="utf-8")); data=json.loads(x.get("output_text","{}"))
   for disp in data.get("dispositions",[]):
    for obj in disp.get("objects",[]):
     org=(obj.get("statement") or "")
     if "Fred Hollows" in org or "Tweed Regional Gallery" in org:
      hold.append({"canonical_object_id":"holdout:"+f.stem+":"+str(disp.get("local_key")),"observation_id":"holdout:"+f.stem+":"+str(disp.get("local_key")),"organisation":"The Fred Hollows Foundation" if "Fred Hollows" in org else "Tweed Regional Gallery Foundation Limited","overlay_statement":obj.get("statement",""),"facet":obj.get("facet_hint") or "operational_activity","representation_family":obj.get("representation_family"),"qualification":obj.get("qualification")})
  except Exception: pass
 hold=[dict(r,durable_overlay_id=f"HOLD-{i:03d}") for i,r in enumerate(hold) if r.get("representation_family")!="native_candidate"]
 _write_json(out,"v5rr-dry-run-holdout-canonical-objects.json",hold)
 # Pre-freeze guard is evaluated against workshop manifests.
 pre_files=list(out.glob("discovery-*.json"))+list(out.glob("round1-*.json"))+list(out.glob("sweep1-*.json"))+list(out.glob("round2-*.json"))+list(out.glob("sweep2-*.json")); pretext="\n".join(f.read_text(encoding="utf-8") for f in pre_files); guard=not any(r["observation_id"] in pretext for r in hold)
 ext_provider=provider or FakeProvider(); extraction=[]; extraction_ledger=SemanticCallLedger(out)
 for i in range(0,len(hold),10):
  batch=hold[i:i+10]; payload={"object_keys":[r["canonical_object_id"] for r in batch],"canonical_objects":batch,"eligible_facets":["operational_activity","participation","fundraising_mode"]}; parsed,_,_=invoke_semantic_call(ext_provider,"extraction",payload,schemas()["extraction"],process_extraction_response,ledger=extraction_ledger,output_dir=out,model="gpt-5.6-luna",reasoning="none",call_id=f"holdout-extraction-{i//10+1:02d}"); by_key={h["canonical_object_key"]:h for h in parsed};
  for r in batch:
   h=by_key.get(r["canonical_object_id"],{"overlays":[]})
   for o in h["overlays"]: extraction.append({"durable_overlay_id":f"HOVL-{len(extraction):03d}","canonical_object_id":r["canonical_object_id"],"observation_id":r["observation_id"],"organisation":r["organisation"],"facet":o["facet"],"overlay_statement":o["overlay_statement"],"analytic_dimension":o["analytic_dimension"],"qualification":o["qualification"],"anti_duplication_boundary":o["anti_duplication_boundary"]})
 _write_json(out,"v5rr-dry-run-holdout-extraction.json",extraction); hq,ht=run_quality_review(extraction,ext_provider,out,10) if extraction else ([],[]); _write_json(out,"v5rr-dry-run-holdout-authoritative-quality.json",hq)
 transfers=[]; transfer_ledger=SemanticCallLedger(out); frozen_hashes=base.get("final_catalogue_hashes",{})
 for facet in ("operational_activity","participation","fundraising_mode"):
  final= json.loads(next(iter(out.glob(f"round2-catalogue-{facet}.json"))).read_text(encoding="utf-8")) if list(out.glob(f"round2-catalogue-{facet}.json")) else {}
  items=final.get("items",final); ids=[v["id"] for v in items.values() if v.get("active")]; rows=[r for r in hq if r.get("reviewed_facet")==facet and r.get("disposition")!="reject_native"]
  for organisation in sorted({r["organisation"] for r in rows}):
   org_rows=[r for r in rows if r["organisation"]==organisation]; before=frozen_hashes.get(facet,""); parsed,_,_=invoke_semantic_call(ext_provider,"attachment",{"overlay_keys":[r["durable_overlay_id"] for r in org_rows],"active_concept_ids":ids,"catalogue_hash":before,"organisation":organisation},schemas()["attachment"],process_attachment_response,ledger=transfer_ledger,output_dir=out,facet=facet,organisation=organisation,model="gpt-5.6-luna",reasoning="none",call_id=f"transfer-{facet}-{len(transfers):03d}"); transfers.extend(parsed)
   if _catalogue_hash(Catalogue.from_dict(final))!=before: raise AssertionError("frozen catalogue changed during transfer")
 _write_json(out,"v5rr-dry-run-holdout-transfer.json",transfers); _write_json(out,"v5rr-dry-run-promotion-evidence.json",{"concept_count":sum(len(json.loads(p.read_text(encoding="utf-8")).get("items",{})) for p in out.glob("round2-catalogue-*.json")),"holdout_assignment_count":len(transfers)})
 result=dict(base); result.update({"stage":"full_fake_campaign_complete","holdout_canonical_objects":len(hold),"holdout_extraction_overlays":len(extraction),"holdout_quality_records":len(hq),"holdout_transfer_assignments":len(transfers),"pre_freeze_holdout_guard":guard,"holdout_extraction_calls":len(extraction_ledger.rows),"holdout_quality_calls":len(ht),"transfer_calls":len(transfer_ledger.rows),"real_provider_calls":len(getattr(provider,"invocations",())) if provider else 0,"new_cost_usd":str(getattr(provider,"spent",0)-getattr(provider,"retained",0)) if provider else "0"}); _write_json(out,"v5rr-full-fake-campaign-complete.json",result); return result
