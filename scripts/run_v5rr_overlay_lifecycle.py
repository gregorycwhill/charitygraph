"""Sequential V5RR provider integration entry point (experiment-only)."""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
from charitygraph.native_lifecycle_harness import schemas,validate_response,process_quality_response,process_discovery_response,process_gardener_response,process_attachment_response,process_extraction_response
from charitygraph.v5rr_orchestrator import run_full_fake_campaign,run_full_fake_campaign_complete,OpenAIProvider

CASES=[("quality","gpt-5.6-terra","high",4000),("discovery","gpt-5.6-luna","none",7000),("gardener","gpt-5.6-terra","high",4000),("attachment","gpt-5.6-luna","none",7000),("extraction","gpt-5.6-luna","none",7000)]
STAGES=("smoke_verification","harvest_reconstruction","contamination_exclusion","quality_recovery","authoritative_quality","core_pools","split","discovery","gardener_round1","sweep1","gardener_round2","sweep2","catalogue_freeze","holdout_reconstruction","holdout_extraction","holdout_quality","holdout_transfer","promotion_diagnostics","cost_ledger","public_review")
def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--v5-root",type=Path,required=True); ap.add_argument("--v5r-root",type=Path,required=True); ap.add_argument("--forensic-root",type=Path,required=True); ap.add_argument("--excluded-manifest",type=Path,required=True); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args(); args.output.mkdir(parents=True,exist_ok=True); ss=schemas(); rows=[]; total=0.0
 if args.dry_run:
  report=run_full_fake_campaign_complete(args.v5_root,args.v5r_root,args.output,args.forensic_root,args.excluded_manifest); print(json.dumps(report)); return
 provider=OpenAIProvider(args.output); report=run_full_fake_campaign_complete(args.v5_root,args.v5r_root,args.output,args.forensic_root,args.excluded_manifest,provider=provider)
 report.update({"provider_calls":len(provider.invocations),"real_provider_calls":len(provider.invocations),"retained_smoke_cost_usd":"0.006449","new_cost_usd":str(provider.spent-provider.retained),"aggregate_cost_usd":str(provider.spent)})
 (args.output/"v5rr-real-campaign-summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
 print(json.dumps(report))
if __name__=="__main__": main()
