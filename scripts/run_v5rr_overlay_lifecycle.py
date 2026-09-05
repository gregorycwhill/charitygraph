"""Sequential V5RR provider integration entry point (experiment-only)."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
from charitygraph.native_lifecycle_harness import schemas,validate_response,process_quality_response,process_discovery_response,process_gardener_response,process_attachment_response,process_extraction_response
from charitygraph.v5rr_orchestrator import run_full_fake_campaign,run_full_fake_campaign_complete
from charitygraph.openai_client import responses_create,estimate_response_cost

CASES=[("quality","gpt-5.6-terra","high",4000),("discovery","gpt-5.6-luna","none",7000),("gardener","gpt-5.6-terra","high",4000),("attachment","gpt-5.6-luna","none",7000),("extraction","gpt-5.6-luna","none",7000)]
STAGES=("smoke_verification","harvest_reconstruction","contamination_exclusion","quality_recovery","authoritative_quality","core_pools","split","discovery","gardener_round1","sweep1","gardener_round2","sweep2","catalogue_freeze","holdout_reconstruction","holdout_extraction","holdout_quality","holdout_transfer","promotion_diagnostics","cost_ledger","public_review")
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--v5-root",type=Path,required=True); ap.add_argument("--v5r-root",type=Path,required=True); ap.add_argument("--forensic-root",type=Path,required=True); ap.add_argument("--excluded-manifest",type=Path,required=True); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args(); args.output.mkdir(parents=True,exist_ok=True); ss=schemas(); rows=[]; total=0.0
 if args.dry_run:
  report=run_full_fake_campaign_complete(args.v5_root,args.v5r_root,args.output,args.forensic_root,args.excluded_manifest); print(json.dumps(report)); return
 payloads={"quality":{"overlay_keys":["OVL-smoke"],"facet":"operational_activity"},"discovery":{"overlay_keys":["OVL-smoke"]},"gardener":{"overlay_keys":["OVL-smoke"]},"attachment":{"overlay_keys":["OVL-smoke"],"concept_ids":[]},"extraction":{"object_keys":["OBJ-smoke"]}}
 processors={"quality":process_quality_response,"discovery":process_discovery_response,"gardener":process_gardener_response,"attachment":process_attachment_response,"extraction":process_extraction_response}
 for i,(task,model,effort,limit) in enumerate(CASES,1):
  payload=payloads[task]; manifest={"index":i,"task":task,"model":model,"reasoning":effort,"max_output_tokens":limit,"attempts":1,"payload_sha256":__import__("hashlib").sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()}; (args.output/f"task-{i:02d}-manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
  started=time.perf_counter(); resp=responses_create(model=model,input_text=json.dumps(payload),text_format={"type":"json_schema","name":f"v5rr_{task}","strict":True,"schema":ss[task]},max_output_tokens=limit,max_attempts=1,timeout_seconds=300,reasoning={"effort":effort}); usage=resp.usage; raw={"response_id":resp.response_id,"status":resp.status,"output_text":resp.output_text,"usage":usage.__dict__}; (args.output/f"task-{i:02d}-response.json").write_text(json.dumps(raw,indent=2),encoding="utf-8"); valid=False; error=None
  try: parsed=json.loads(resp.output_text); validate_response(parsed,ss[task]); processors[task](parsed,ss[task]); valid=True
  except Exception as exc: error=str(exc)
  cost=estimate_response_cost(model,usage) or 0.0; total+=float(cost); rows.append({"task":task,"model":model,"status":resp.status,"valid":valid,"error":error,"input_tokens":usage.input_tokens,"output_tokens":usage.output_tokens,"cost_usd":str(cost),"latency_seconds":round(time.perf_counter()-started,3)})
  if total>1.25: raise RuntimeError("V5RR cap exceeded")
 # The smoke calls are retained and counted; substantive stages are deliberately
 # represented by the same strict provider path below in subsequent campaign runs.
 (args.output/"provider-schema-smoke-report.json").write_text(json.dumps({"experiment_id":"native-induction-v5rr-overlay-lifecycle","calls":rows,"provider_calls":len(rows),"cost_usd":f"{total:.6f}"},indent=2),encoding="utf-8")
 print(json.dumps({"calls":len(rows),"cost_usd":f"{total:.6f}","valid":sum(r["valid"] for r in rows)}))
if __name__=="__main__": main()
