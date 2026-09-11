"""Activate, prepare, and execute the explicitly authorized Direct Service V1.2 slice."""
from __future__ import annotations

import argparse, hashlib, json, re, subprocess, sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.direct_service_wire import DirectServiceWireOutput, wire_to_domain
from charitygraph.phase5_execution_mandate import manifest_hash, evaluate_execution_against_mandate, proposed_phase5_standard_luna_v1_2_amendment_manifest
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient, StandardCampaignCoordinator, StandardProviderResponse, body_sha256
from charitygraph.runtime import SQLiteCatalog

MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-3"
OLD_MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-2"
RUN = "run:phase5-direct-service-v1.2-cutover"
COHORT = "cohort:phase5-direct-service-v1.2-cutover"
JOB = "deliveryjob:phase5-direct-service-v1.2-standard"
OWNER = "phase5-direct-service-v1-2-worker"
AUTH_HASH = "1fb9efe0e64db8686cba87ab71dced e892ca616c147e871c431d43ea356dce13".replace(" ", "")
PREP_SHA = "69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26"
JSONL_SHA = "35e1ad5ecbca107566a00010d59d4566ece4be2198f49c42a3cb61e2dc2a3f0a"
PROP_SHA = "255ee36010083f78d8bd7a08eba684d053a35e34193da1c6ca80672b49c9f42e"
MODEL = "gpt-5.6-luna"


def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()
def canonical(value: object) -> bytes: return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
def now() -> str: return datetime.now(timezone.utc).isoformat()


def verify(root: Path) -> tuple[dict, list[dict], dict]:
    prep_raw = (root / "preparation.json").read_bytes(); jsonl_raw = (root / "requests.jsonl").read_bytes()
    ticket = json.loads((root / "future-execution-ticket.json").read_bytes())
    proposal_path = Path("proposals/phase5-direct-service-v1.2-amendment-3.json")
    proposal_raw = proposal_path.read_bytes(); proposal = json.loads(proposal_raw)
    if sha(prep_raw) != PREP_SHA or sha(jsonl_raw) != JSONL_SHA or sha(proposal_raw) != PROP_SHA:
        raise RuntimeError("authorized V1.2 immutable artefact hash mismatch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if ticket.get("builder_commit_required") != head or ticket.get("preparation_manifest_sha256") != PREP_SHA or ticket.get("jsonl_sha256") != JSONL_SHA:
        raise RuntimeError("future execution ticket is not pinned to the current reviewed builder and artefacts")
    manifest = json.loads(prep_raw)
    rows = manifest.get("request_items", [])
    if len(rows) != 18 or len({r["provider_request_item_id"] for r in rows}) != 18:
        raise RuntimeError("V1.2 campaign is not exactly the authorized 18-item set")
    if manifest.get("model") != MODEL or manifest.get("reasoning_effort") != "low" or manifest.get("delivery_mode") != "standard" or manifest.get("max_output_tokens") != 8000 or manifest.get("provider_service_tier") != "omitted":
        raise RuntimeError("V1.2 route drift")
    if manifest["aggregate"]["hard_max_aud"] != "1.334775" or manifest["aggregate"]["hard_max_usd"] != "0.878137":
        raise RuntimeError("V1.2 aggregate exposure drift")
    return manifest, rows, proposal


def activate(catalog: SQLiteCatalog, proposal: dict, timestamp: str) -> None:
    existing = catalog.get_execution_mandate(MANDATE)
    if existing is None:
        catalog.register_execution_mandate(mandate_id=MANDATE, manifest_hash=manifest_hash(proposal), authorization_text_hash=AUTH_HASH, scope=proposal, contract_allowlist=tuple(proposal["allowed_contracts"]), aggregate_hard_aud=proposal["aggregate_hard_aud"], per_request_hard_aud=proposal["per_request_hard_aud"], phase_scope=proposal["phase_scope"], supersedes_mandate_id=OLD_MANDATE, now=timestamp)
    elif existing["manifest_hash"] != manifest_hash(proposal) or existing["authorization_text_hash"] != AUTH_HASH:
        raise RuntimeError("amendment 3 durable identity conflicts with authorization")
    old = catalog.get_execution_mandate(OLD_MANDATE)
    target = catalog.get_execution_mandate(MANDATE)
    if target["status"] == "proposed":
        if old is not None and old["status"] == "active":
            catalog.revoke_execution_mandate(mandate_id=OLD_MANDATE, now=timestamp, reason="superseded by explicitly authorized Direct Service V1.2 cutover")
        catalog.activate_execution_mandate(mandate_id=MANDATE, authorization_text_hash=AUTH_HASH, authorized_by="Greg", now=timestamp)
    elif target["status"] != "active":
        raise RuntimeError("amendment 3 is not active or proposed")
    target = catalog.get_execution_mandate(MANDATE)
    if Decimal(target["actual_spend_aud"]) == 0 and Decimal(target["unresolved_reserved_aud"]) == 0:
        old = catalog.get_execution_mandate(OLD_MANDATE)
        if old is not None and old["status"] == "revoked" and (Decimal(old["actual_spend_aud"]) != 0 or Decimal(old["unresolved_reserved_aud"]) != 0):
            catalog.carry_forward_execution_mandate_accounting(from_mandate_id=OLD_MANDATE, to_mandate_id=MANDATE, now=timestamp)


def prepare(catalog: SQLiteCatalog, rows: list[dict], timestamp: str) -> list[dict]:
    ids = [r["logical_task_id"] for r in rows]
    cohort = {"record_id": COHORT, "cohort_code": "PHASE5-DIRECT-SERVICE-V1.2-CUTOVER", "definition_version": "1", "membership_hash": sha("|".join(ids).encode()), "budget_cap": {"amount": "30.00", "currency": "AUD"}, "created_at": timestamp}
    existing_cohort = catalog.get_cohort(COHORT)
    if existing_cohort is None: catalog.register_cohort(cohort)
    elif existing_cohort["membership_hash"] != cohort["membership_hash"] or existing_cohort["cohort_code"] != cohort["cohort_code"]: raise RuntimeError("V1.2 cohort identity conflicts")
    run = {"record_id": RUN, "cohort_id": COHORT, "run_kind": "phase5_direct_service_v1_2_standard", "status": "planned", "configuration_hash": sha(canonical([r["provider_request_item_id"] for r in rows])), "created_at": timestamp}
    existing_run = catalog.get_run(RUN)
    if existing_run is None: catalog.register_run(run)
    elif existing_run["cohort_id"] != COHORT or existing_run["configuration_hash"] != run["configuration_hash"]: raise RuntimeError("V1.2 run identity conflicts")
    catalog.create_delivery_job(delivery_job_id=JOB, run_id=RUN, provider_id="openai", model_route=MODEL, delivery_mode="standard", pricing_snapshot_id="pricing:phase5-openai-standard-v1", now=timestamp)
    out = []
    for item in rows:
        rid = item["provider_request_item_id"]
        task_id = deterministic_id("semtask:", {"run": RUN, "logical_task_id": rid and item["logical_task_id"], "contract_version": "1.2"})
        reservation = deterministic_id("reservation:", {"run": RUN, "request": rid})
        physical = deterministic_id("taskrun:", {"kind": "direct_service_v1_2_physical", "run": RUN, "request": rid})
        attempt = "deliveryattempt:" + sha(canonical({"run": RUN, "request": rid, "ordinal": 1}))
        catalog.register_task({"record_id": task_id, "subject_id": item["subject_id"], "cohort_id": COHORT, "task_type": "direct_service_semantics", "task_schema": {"schema_id": "urn:charitygraph:builder:schema:direct-service-task:1.0"}, "cache_key": sha((item["request_body_sha256"] + item["logical_task_id"]).encode()), "provider_id": "openai", "model_snapshot": MODEL}, run_id=RUN, now=timestamp)
        catalog.reserve_cost({"record_id": reservation, "cohort_id": COHORT, "run_id": RUN, "reserved_aud": {"amount": item["hard_max_aud"], "currency": "AUD"}, "model_task_ids": (task_id,)}, now=timestamp)
        catalog.reserve_execution_mandate(mandate_id=MANDATE, reservation_id=reservation, amount_aud=item["hard_max_aud"], now=timestamp)
        catalog.prepare_physical_attempt(physical_attempt_id=physical, run_id=RUN, subject_id=item["subject_id"], delivery_mode="standard", provider_request_id=rid, model_task_ids=(task_id,), reservation_id=reservation, now=timestamp)
        catalog.create_provider_request_item(provider_request_item_id=rid, run_id=RUN, model_task_id=task_id, provider_id="openai", model_route=MODEL, requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=JOB, physical_attempt_id=physical, now=timestamp)
        catalog.create_provider_request_attempt(delivery_attempt_id=attempt, provider_request_item_id=rid, physical_attempt_id=physical, delivery_job_id=JOB, attempt_ordinal=1, authorization_id=MANDATE, attempt_class="initial", predecessor_attempt_id=None, now=timestamp)
        out.append(dict(item, provider="openai", task_profile="direct_service_semantics", task_profile_version="2", catalog_model_task_id=task_id, reservation_id=reservation, mandate_reservation_id=reservation, physical_attempt_id=physical, delivery_attempt_id=attempt, automatic_retries=0, semantic_retries=0, fallbacks=[], ambiguous_resend=False))
    return out


def output_text(body: dict) -> str:
    if isinstance(body.get("output_text"), str): return body["output_text"]
    chunks = [c["text"] for o in body.get("output", []) if isinstance(o, dict) for c in o.get("content", []) if isinstance(c, dict) and c.get("type") == "output_text" and isinstance(c.get("text"), str)]
    if not chunks: raise ValueError("provider Responses body contains no output text")
    return "".join(chunks)


def visible_scope(request_body: dict) -> str:
    prompt = request_body["input"][0]["content"][0]["text"]
    match = re.search(r"(?m)^\s*(scope:[^ |]+)\s*\|", prompt)
    if not match:
        raise ValueError("pinned request has no visible scope")
    return match.group(1)


def reconcile(catalog: SQLiteCatalog, row: dict, response: StandardProviderResponse, root: Path, timestamp: str, parsed: dict) -> None:
    usage = response.body.get("usage") or {}; raw_text = output_text(response.body); result_id = "modelresult:" + sha((row["physical_attempt_id"] + response.body["id"] + sha(raw_text.encode())).encode())
    valid = True; error = None; proposals = 0
    try:
        wire = DirectServiceWireOutput.model_validate_json(raw_text)
        domain = wire_to_domain(wire, allowed_scope_ids={visible_scope(row["request_body"])}, evidence_locators={x["evidence_id"] for x in json.loads(row["request_body"]["input"][1]["content"][0]["text"])["evidence_bindings"]})
        proposals = len(domain.propositions)
    except Exception as exc:
        valid = False; error = str(exc)[:500]
    inp = Decimal(str(usage.get("input_tokens", 0))); out = Decimal(str(usage.get("output_tokens", 0))); usd = ((inp * Decimal("1.60")) + (out * Decimal("5.00"))) / Decimal(1000000); aud = (usd * Decimal("1.52")).quantize(Decimal("0.000001"))
    catalog.record_cost_entry({"cohort_id": COHORT, "run_id": RUN, "task_run_id": row["physical_attempt_id"], "reservation_id": row["reservation_id"], "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(usd.quantize(Decimal("0.000001"))), "currency": "USD"}, "aud_cost": {"amount": str(aud), "currency": "AUD"}, "usage": usage, "recorded_at": timestamp, "pricing_snapshot_id": "pricing:phase5-openai-standard-v1", "fx_snapshot_id": "fx:phase5-usd-aud-1.52"}, entry_key="actual:" + row["physical_attempt_id"])
    pos = catalog.reservation_position(row["reservation_id"]); reserved = Decimal(row["hard_max_aud"])
    if pos["outstanding"] > aud: catalog.release_cost(row["reservation_id"], {"amount": str(Decimal(str(pos["outstanding"])) - aud), "currency": "AUD"}, now=timestamp, entry_key="release:" + row["physical_attempt_id"])
    catalog.settle_execution_mandate_reservation(mandate_id=MANDATE, reservation_id=row["mandate_reservation_id"], actual_aud=aud, ambiguous=False, now=timestamp)
    owner = OWNER; lease = (datetime.fromisoformat(timestamp) + timedelta(hours=1)).isoformat()
    if catalog.claim_task(row["catalog_model_task_id"], owner=owner, lease_expires_at=lease, now=timestamp):
        catalog.begin_task_attempt(row["catalog_model_task_id"], owner=owner, task_run_id=row["physical_attempt_id"], now=timestamp, provider_request_id=response.request_id, reservation_id=row["reservation_id"])
        if valid: catalog.finish_successful_attempt(row["physical_attempt_id"], owner=owner, completed_at=timestamp, result_artifact_id=result_id, provider_request_id=response.request_id, usage=usage, pricing_snapshot_id="pricing:phase5-openai-standard-v1", fx_snapshot_id="fx:phase5-usd-aud-1.52")
        else: catalog.finish_failed_attempt(row["physical_attempt_id"], owner=owner, completed_at=timestamp, retryable=False, error_class="output_validation", error_message_redacted="Direct Service V1.2 output validation failed", result_artifact_id=result_id, provider_request_id=response.request_id, usage=usage, pricing_snapshot_id="pricing:phase5-openai-standard-v1", fx_snapshot_id="fx:phase5-usd-aud-1.52")
    parsed[row["provider_request_item_id"]] = {"valid": valid, "error": error, "proposals": proposals, "response_id": response.body.get("id"), "provider_request_id": response.request_id, "usage": usage, "actual_aud": str(aud)}
    (root / "candidate-results").mkdir(exist_ok=True); (root / "candidate-results" / (row["provider_request_item_id"].replace(":", "_") + ".json")).write_text(json.dumps(parsed[row["provider_request_item_id"]], indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--execute", action="store_true"); ap.add_argument("--catalogue", type=Path, default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")); ap.add_argument("--root", type=Path, default=Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")); args = ap.parse_args()
    if not args.execute: raise SystemExit("--execute is required for the authorized campaign")
    manifest, source_rows, proposal = verify(args.root); timestamp = now(); catalog = SQLiteCatalog(args.catalogue, authorization_path=args.catalogue).open()
    activate(catalog, proposal, timestamp)
    rows = prepare(catalog, source_rows, timestamp)
    for row in rows:
        row["scope_id"] = visible_scope(row["request_body"])
    parsed: dict = {}
    def mandate(row): return evaluate_execution_against_mandate(catalog, MANDATE, {**row, "provider": "openai", "logical_task_id": row["logical_task_id"], "contract_identity_hash": row["contract_identity_hash"]})
    def validator(body): DirectServiceWireOutput.model_validate_json(output_text(body))
    def on_reconciled(row, response, usage): reconcile(catalog, row, response, args.root, timestamp, parsed)
    provider = OpenAIHTTPStandardClient()
    canary = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=args.root, max_concurrency=1, now=timestamp, validator=validator, on_reconciled=on_reconciled, mandate_evaluator=mandate).run([rows[0]])
    if canary.get("stop_campaign") or not canary.get("results") or canary["results"][0]["status"] != "completed":
        raise RuntimeError("V1.2 schema canary did not complete; remaining requests were not launched")
    remainder = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=args.root, max_concurrency=4, now=timestamp, validator=validator, on_reconciled=on_reconciled, mandate_evaluator=mandate).run(rows[1:])
    report = {"campaign": "phase5-direct-service-v1.2-cutover-v1", "manifest_sha256": PREP_SHA, "jsonl_sha256": JSONL_SHA, "amendment_3_active": True, "canary": canary, "remainder": remainder, "candidate_results": parsed, "provider_operations": canary.get("provider_posts", 0) + remainder.get("provider_posts", 0), "governed_promotions": 0, "source_acquisitions": 0, "automatic_retries": 0, "semantic_retries": 0, "fallbacks": []}
    raw = canonical(report) + b"\n"; (args.root / "final-report.json").write_bytes(raw); (args.root / "final-report.sha256").write_text(sha(raw) + "\n", encoding="ascii")
    print(json.dumps({"status": "PHASE5_DIRECT_SERVICE_V1_2_REMAINDER_COMPLETE", "report_sha256": sha(raw), "provider_operations": report["provider_operations"], "canary": canary, "remainder": remainder}, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
