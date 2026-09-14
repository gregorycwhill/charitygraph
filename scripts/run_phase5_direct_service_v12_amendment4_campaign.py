"""Activate Amendment 4, rebind the repaired V1.2 set, then execute once."""
from __future__ import annotations

import argparse, hashlib, importlib, json, sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_execution_mandate import manifest_hash, proposed_phase5_standard_luna_v1_2_amendment4_manifest, evaluate_execution_against_mandate
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient, StandardCampaignCoordinator
from charitygraph.runtime import SQLiteCatalog

base = importlib.import_module("run_phase5_direct_service_v12_campaign")
MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-4"
OLD = "mandate:phase5-build-standard-luna-v1-amendment-3"
RUN = "run:phase5-direct-service-v1.2-cutover"
JOB = "deliveryjob:phase5-direct-service-v1.2-standard-amendment-4"
AUTH_HASH = "2c044f bbe9d642dce39d77174e511562248e13fe4a313e27d8b028b6d6f30365".replace(" ", "")

def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def canon(value: object) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def now() -> str: return datetime.now(timezone.utc).isoformat()

def activate_and_rebind(catalog: SQLiteCatalog, rows: list[dict], proposal: dict, timestamp: str) -> None:
    # Close the old mandate's still-active reservations without changing any
    # 17 prepared Builder budget reservations.
    for item in rows:
        durable = catalog.get_provider_request_item(item["provider_request_item_id"])
        physical = catalog.get_physical_attempt(durable["physical_attempt_id"])
        old_res = physical["reservation_id"]
        with catalog._authorization_connection() as conn:
            active = conn.execute("SELECT status FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?", (OLD, old_res)).fetchone()
        if active is not None and active["status"] == "active":
            catalog.settle_execution_mandate_reservation(mandate_id=OLD, reservation_id=old_res, actual_aud="0", ambiguous=False, now=timestamp)
    target = catalog.get_execution_mandate(MANDATE)
    if target is None:
        catalog.register_execution_mandate(mandate_id=MANDATE, manifest_hash=manifest_hash(proposal), authorization_text_hash=AUTH_HASH, scope=proposal, contract_allowlist=tuple(proposal["allowed_contracts"]), aggregate_hard_aud=proposal["aggregate_hard_aud"], per_request_hard_aud=proposal["per_request_hard_aud"], phase_scope=proposal["phase_scope"], supersedes_mandate_id=OLD, now=timestamp)
        target = catalog.get_execution_mandate(MANDATE)
    if target["status"] == "proposed":
        old = catalog.get_execution_mandate(OLD)
        if old is not None and old["status"] == "active": catalog.revoke_execution_mandate(mandate_id=OLD, now=timestamp, reason="superseded by explicitly authorized Amendment 4")
        catalog.activate_execution_mandate(mandate_id=MANDATE, authorization_text_hash=AUTH_HASH, authorized_by="Greg", now=timestamp)
    elif target["status"] != "active":
        raise RuntimeError("Amendment 4 is not proposed or active")
    target = catalog.get_execution_mandate(MANDATE)
    if Decimal(target["actual_spend_aud"]) == 0: catalog.carry_forward_execution_mandate_accounting(from_mandate_id=OLD, to_mandate_id=MANDATE, now=timestamp)
    catalog.create_delivery_job(delivery_job_id=JOB, run_id=RUN, provider_id="openai", model_route="gpt-5.6-luna", delivery_mode="standard", pricing_snapshot_id="pricing:phase5-openai-standard-v1", now=timestamp)
    for item in rows:
        durable = catalog.get_provider_request_item(item["provider_request_item_id"])
        old_physical = catalog.get_physical_attempt(durable["physical_attempt_id"])
        reservation = old_physical["reservation_id"]
        replacement = item["provider_request_item_id"] == rows[0]["provider_request_item_id"]
        if replacement:
            reservation = deterministic_id("reservation:", {"run": RUN, "request": item["provider_request_item_id"], "amendment": "4", "replacement": True})
            catalog.reserve_cost({"record_id": reservation, "cohort_id": old_physical["run_id"].replace("run:", "cohort:") if False else "cohort:phase5-direct-service-v1.2-cutover", "run_id": RUN, "reserved_aud": {"amount": item["hard_max_aud"], "currency": "AUD"}, "model_task_ids": (durable["model_task_id"],)}, now=timestamp)
        catalog.reserve_execution_mandate(mandate_id=MANDATE, reservation_id=reservation, amount_aud=item["hard_max_aud"], now=timestamp)
        new_phys = deterministic_id("taskrun:", {"kind": "direct_service_v1_2_amendment4_physical", "request": item["provider_request_item_id"]})
        new_attempt = "deliveryattempt:" + sha(canon({"kind": "direct_service_v1_2_amendment4", "request": item["provider_request_item_id"]}))
        replacement_id = "presendreplacement:" + sha(canon({"kind": "amendment4-rebind", "request": item["provider_request_item_id"]}))
        catalog.create_zero_crossing_pre_send_replacement(replacement_id=replacement_id, provider_request_item_id=item["provider_request_item_id"], new_physical_attempt_id=new_phys, new_delivery_attempt_id=new_attempt, new_delivery_job_id=JOB, new_reservation_id=reservation, authorization_id=MANDATE, provider_material_sha256=item["request_body_sha256"], expected_provider_material_sha256=item["request_body_sha256"], reason="Amendment 4 append-only pre-send rebind" if not replacement else "Amendment 4 authorized zero-crossing canary replacement", now=timestamp)

def build_rows(catalog: SQLiteCatalog, prep_rows: list[dict]) -> list[dict]:
    rows=[]
    for item in prep_rows:
        durable=catalog.get_provider_request_item(item["provider_request_item_id"]); attempts=catalog.list_provider_request_attempts(provider_request_item_id=item["provider_request_item_id"]); attempt=max(attempts,key=lambda x:x["attempt_ordinal"]); physical=catalog.get_physical_attempt(durable["physical_attempt_id"])
        row=dict(item, provider="openai", task_profile="direct_service_semantics", task_profile_version="2", catalog_model_task_id=durable["model_task_id"], reservation_id=physical["reservation_id"], mandate_reservation_id=physical["reservation_id"], physical_attempt_id=physical["physical_attempt_id"], delivery_attempt_id=attempt["delivery_attempt_id"], automatic_retries=0, semantic_retries=0, fallbacks=[], ambiguous_resend=False, scope_id=base.visible_scope(item["request_body"]))
        rows.append(row)
    return rows

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--execute",action="store_true"); ap.add_argument("--prepare-only",action="store_true"); ap.add_argument("--catalogue",type=Path,default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")); ap.add_argument("--root",type=Path,default=Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")); args=ap.parse_args()
    if not args.execute: raise SystemExit("--execute is required")
    manifest, prep_rows, _ = base.verify(args.root); proposal=proposed_phase5_standard_luna_v1_2_amendment4_manifest(); timestamp=now(); catalog=SQLiteCatalog(args.catalogue,authorization_path=args.catalogue).open(); catalog.migrate()
    activate_and_rebind(catalog, prep_rows, proposal, timestamp); rows=build_rows(catalog,prep_rows)
    certs=[base_cert(catalog,row) for row in rows]
    if len(certs)!=18: raise RuntimeError("not all 18 rows certified")
    if args.prepare_only:
        print(json.dumps({"status":"18/18_READY_TO_CROSS_PROVIDER_BOUNDARY_PENDING_PROVIDER_SEND","amendment4_active":True,"certified_count":len(certs),"provider_operations":0},sort_keys=True)); return 0
    base.MANDATE=MANDATE; base.OWNER="phase5-direct-service-v1-2-amendment4-worker"; base.COHORT="cohort:phase5-direct-service-v1.2-cutover"; base.RUN=RUN
    parsed={}
    mandate=lambda row: evaluate_execution_against_mandate(catalog,MANDATE,{**row,"provider":"openai"})
    validator=lambda body: base.DirectServiceWireOutput.model_validate_json(base.output_text(body))
    callback=lambda row,response,usage: base.reconcile(catalog,row,response,args.root,timestamp,parsed)
    provider=OpenAIHTTPStandardClient(); canary=StandardCampaignCoordinator(catalog=catalog,provider=provider,runtime_root=args.root,max_concurrency=1,now=timestamp,validator=validator,on_reconciled=callback,mandate_evaluator=mandate).run([rows[0]])
    if canary.get("stop_campaign") or not canary.get("results") or canary["results"][0]["status"]!="completed": raise RuntimeError("Amendment 4 canary did not complete; remainder held")
    remainder=StandardCampaignCoordinator(catalog=catalog,provider=provider,runtime_root=args.root,max_concurrency=4,now=timestamp,validator=validator,on_reconciled=callback,mandate_evaluator=mandate).run(rows[1:])
    report={"status":"PHASE5_DIRECT_SERVICE_V1_2_REMAINDER_COMPLETE","amendment4_active":True,"certified_count":len(certs),"canary":canary,"remainder":remainder,"candidate_results":parsed,"provider_operations":canary.get("provider_posts",0)+remainder.get("provider_posts",0),"source_acquisition":0,"governed_promotions":0,"automatic_retries":0,"semantic_retries":0,"fallbacks":[]}
    raw=canon(report)+b"\n"; (args.root/"amendment4-final-report.json").write_bytes(raw); (args.root/"amendment4-final-report.sha256").write_text(sha(raw)+"\n",encoding="ascii"); print(json.dumps({"report_sha256":sha(raw),"provider_operations":report["provider_operations"],"canary":canary,"remainder":remainder},sort_keys=True)); return 0

def base_cert(catalog,row):
    from charitygraph.phase5_pre_send_certification import certify_standard_execution_row
    return certify_standard_execution_row(catalog,row,mandate_id=MANDATE)

if __name__=="__main__": raise SystemExit(main())
