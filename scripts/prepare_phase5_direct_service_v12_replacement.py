"""Provider-free V1.2 zero-crossing replacement preparation and certification."""
from __future__ import annotations

import argparse, hashlib, json, sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_execution_mandate import manifest_hash, proposed_phase5_standard_luna_v1_2_amendment4_manifest
from charitygraph.phase5_pre_send_certification import certify_standard_execution_row
from charitygraph.runtime import SQLiteCatalog

ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")
DB = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
MANDATE3 = "mandate:phase5-build-standard-luna-v1-amendment-3"
MANDATE4 = "mandate:phase5-build-standard-luna-v1-amendment-4"
RUN = "run:phase5-direct-service-v1.2-cutover"
JOB4 = "deliveryjob:phase5-direct-service-v1.2-standard-amendment-4"

def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def canon(value: object) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, default=ROOT); ap.add_argument("--catalogue", type=Path, default=DB); ap.add_argument("--release-failed-reservation", action="store_true"); args = ap.parse_args()
    prep_raw = (args.root / "preparation.json").read_bytes(); prep = json.loads(prep_raw)
    if sha(prep_raw) != "69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26" or len(prep["request_items"]) != 18: raise RuntimeError("V1.2 preparation identity mismatch")
    catalog = SQLiteCatalog(args.catalogue, authorization_path=args.catalogue).open()
    catalog.migrate()
    durable = {row["provider_request_item_id"]: row for row in catalog.list_provider_request_items(RUN)}
    if len(durable) != 18: raise RuntimeError(f"expected 18 durable V1.2 items, found {len(durable)}")
    failed = [row for row in durable.values() if row["status"] == "failed"]
    prepared = [row for row in durable.values() if row["status"] == "prepared"]
    if len(failed) != 1 or len(prepared) != 17: raise RuntimeError("current V1.2 state is not exactly one failed plus seventeen prepared")
    failed_item = failed[0]; failed_attempt = catalog.list_provider_request_attempts(provider_request_item_id=failed_item["provider_request_item_id"])[0]
    old_physical = catalog.get_physical_attempt(failed_item["physical_attempt_id"])
    if failed_attempt["failure_class"] != "pre_send_validation" or failed_attempt["provider_request_id"] or failed_attempt["provider_receipt_id"] or old_physical["send_started_at"] or failed_item["provider_request_id"]: raise RuntimeError("failed canary is not a proven zero-crossing failure")
    if args.release_failed_reservation:
        pos = catalog.reservation_position(old_physical["reservation_id"])
        if pos["outstanding"] > 0: catalog.release_cost(old_physical["reservation_id"], {"amount": str(pos["outstanding"]), "currency": "AUD"}, now=datetime.now(timezone.utc).isoformat(), entry_key="release:v12-zero-crossing-canary")
        catalog.settle_execution_mandate_reservation(mandate_id=MANDATE3, reservation_id=old_physical["reservation_id"], actual_aud="0", ambiguous=False, now=datetime.now(timezone.utc).isoformat())
    proposal = proposed_phase5_standard_luna_v1_2_amendment4_manifest(); proposal_raw = canon(proposal)
    proposal_path = args.root / "proposals" / "phase5-direct-service-v1.2-amendment-4.json"; proposal_path.parent.mkdir(parents=True, exist_ok=True); proposal_path.write_bytes(proposal_raw)
    repaired = []
    by_id = {row["provider_request_item_id"]: row for row in prep["request_items"]}
    for item_id, durable_row in sorted(durable.items()):
        item = by_id[item_id]; replacement = item_id == failed_item["provider_request_item_id"]
        repaired.append({"provider_request_item_id": item_id, "subject_id": item["subject_id"], "logical_task_id": item["logical_task_id"], "request_body_sha256": item["request_body_sha256"], "wire_fingerprint": item["wire_fingerprint"], "hard_max_aud": item["hard_max_aud"], "provider_material_sha256": item["request_body_sha256"], "status": "zero_crossing_replacement_pending_amendment_4" if replacement else "prepared_pending_amendment_4", "old_physical_attempt_id": failed_item["physical_attempt_id"] if replacement else None, "new_physical_attempt_id": deterministic_id("taskrun:", {"kind":"direct_service_v1_2_zero_crossing_replacement", "request":item_id}) if replacement else None, "new_delivery_attempt_id": "deliveryattempt:" + sha(canon({"kind":"zero_crossing_replacement", "request":item_id})) if replacement else None})
    repaired_value = {"campaign":"phase5-direct-service-v1.2-cutover-v1", "run_id":RUN, "delivery_job_id":JOB4, "mandate_id_required":MANDATE4, "preparation_manifest_sha256":sha(prep_raw), "request_items":repaired, "provider_operations":0, "source_acquisition":0, "governed_promotions":0, "replacement_count":1, "standard_count":18, "aggregate_hard_max_aud":prep["aggregate"]["hard_max_aud"], "status":"18/18_PREPARED_PENDING_AMENDMENT_4_AUTHORITY"}
    repaired_raw = canon(repaired_value); repaired_path = args.root / "repaired-continuation-amendment-4.json"; repaired_path.write_bytes(repaired_raw); (args.root / "repaired-continuation-amendment-4.sha256").write_text(sha(repaired_raw)+"\n", encoding="ascii")
    report = {"status":"PHASE5_DIRECT_SERVICE_V1_2_REPLACEMENT_READY", "failed_zero_crossing_canary":failed_item["provider_request_item_id"], "prepared_count":len(prepared), "failed_count":len(failed), "failed_reservation_released":bool(args.release_failed_reservation), "amendment4_proposal":{"path":str(proposal_path),"sha256":sha(proposal_raw),"bytes":len(proposal_raw),"manifest_hash":manifest_hash(proposal)}, "repaired_campaign":{"path":str(repaired_path),"sha256":sha(repaired_raw),"bytes":len(repaired_raw)}, "provider_operations":0}
    report_raw=canon(report)+b"\n"; (args.root/"replacement-preparation-report.json").write_bytes(report_raw); (args.root/"replacement-preparation-report.sha256").write_text(sha(report_raw)+"\n",encoding="ascii")
    print(json.dumps(report,sort_keys=True)); return 0

if __name__ == "__main__": raise SystemExit(main())
