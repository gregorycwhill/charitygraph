"""Provider-free V5RR campaign orchestration over retained V5/V5R artefacts."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from .native_lifecycle_harness import run_synthetic_lifecycle, digest, FakeProvider, schemas, validate_response, process_quality_response, process_discovery_response, Catalogue, split_overlay_ids, DISPOSITIONS

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
