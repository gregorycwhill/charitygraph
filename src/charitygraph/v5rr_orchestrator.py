"""Provider-free V5RR campaign orchestration over retained V5/V5R artefacts."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from .native_lifecycle_harness import run_synthetic_lifecycle, digest

STAGES=("harvest_reconstruction","contamination_exclusion","quality_recovery","authoritative_quality","core_pools","split","discovery","gardener_round1","sweep1","gardener_round2","sweep2","catalogue_freeze","holdout_reconstruction","holdout_extraction","holdout_quality","holdout_transfer","promotion_diagnostics","cost_ledger","public_review")
def _write(out,name,data):
 p=out/name; p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); return {"status":"executed","input_count":len(data) if isinstance(data,(list,dict)) else 1,"output_count":len(data) if isinstance(data,(list,dict)) else 1,"artefact":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
def reconstruct_v5_harvest(v5_root,out):
 forensic=Path(r"C:\tmp\charitygraph-lab-review\native-induction-v5-overlay-lifecycle-review")
 files=list(forensic.glob("overlays-*.json")) if forensic.exists() else list((v5_root/"raw").glob("luna-harvest-*.json")); rows=[]
 for f in files:
  try:
   x=json.loads(f.read_text(encoding="utf-8"));
   if isinstance(x,list): rows.extend(x)
   elif isinstance(x,dict) and x.get("overlays"): rows.extend(x["overlays"])
   elif isinstance(x,dict) and x.get("reviews"):
    for rev in x["reviews"]:
     rows.extend(dict(o,source_file=f.name,local_key=rev.get("local_key")) for o in rev.get("overlays",[]))
   else: rows.extend(x.get("overlays",x.get("data",[])))
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
def run_v5rr_campaign(v5_root,v5r_root,output_dir,provider=None):
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); stages={}; all_rows=reconstruct_v5_harvest(Path(v5_root),out); clean,bad=exclude_contaminated_native_candidates(all_rows); forensic=Path(r"C:\tmp\charitygraph-lab-review\native-induction-v5-overlay-lifecycle-review"); files=[{"path":f.name,"sha256":hashlib.sha256(f.read_bytes()).hexdigest(),"count":len(json.loads(f.read_text(encoding="utf-8")))} for f in forensic.glob("overlays-*.json")] if forensic.exists() else []; stages["forensic_v5_input_loaded"]=_write(out,"v5-forensic-input-manifest.json",{"repository":"gregorycwhill/charitygraph-lab-review","commit":"a26f2f8","files":files,"overlay_count":len(all_rows)}); stages["contamination_exclusion"]=_write(out,"v5rr-contaminant-crosswalk.json",bad); _write(out,"v5rr-clean-overlay-manifest.json",{"clean":clean,"excluded":bad}); decisions=recover_v5r_quality_reviews(Path(v5r_root),clean); stages["quality_recovery"]=_write(out,"v5r-quality-recovery-audit.json",decisions); report={"experiment_id":"native-induction-v5rr-overlay-lifecycle","provider_calls":0,"stages":stages,"historical_overlay_count":len(all_rows),"excluded_native_candidate_count":len(bad),"clean_overlay_count":len(clean),"quality_recovered":sum(x["status"]=="mechanically_recovered" for x in decisions),"quality_ambiguous":sum(x["status"]=="ambiguous" for x in decisions),"quality_unresolved":sum(x["status"]=="unresolved" for x in decisions)}; _write(out,"v5rr-orchestrator-dry-run.json",report); return report
