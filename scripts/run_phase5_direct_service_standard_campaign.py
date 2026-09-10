"""Prepare and execute the currently authorized Direct Service V1 cohort."""
from __future__ import annotations

import argparse, hashlib, json, sqlite3, sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.contracts.direct_service_wire import DirectServiceWireOutput, wire_to_domain
from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_execution_mandate import evaluate_execution_against_mandate
from charitygraph.phase5_execution_packet import ExecutionPacketUnready, materialize_execution_packet
from charitygraph.phase5_openai_dry_run import PRICING, estimate_tokens, serialize_execution_packet_request
from charitygraph.phase5_semantic_contracts import executable_contract_for
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient, StandardCampaignCoordinator
from charitygraph.runtime import SQLiteCatalog

MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-1"
RUN = "run:phase5-direct-service-v1-top100"
COHORT = "cohort:phase5-direct-service-v1-top100"
JOB = "deliveryjob:phase5-direct-service-v1-top100-standard"
OWNER = "phase5-direct-service-v1-worker"
NOW = "2026-09-10T00:00:00+00:00"
PARTIAL_RESERVATION = "reservation:bf19e58a620084541fdb1bb56a65361a2b28e3e3c0c69f8867a1f52ced919fd8"
PARTIAL_RESERVATION_AUD = "0.032917"


def validate_existing_authority(*, catalogue: Path, authority: Path, mandate_id: str = MANDATE) -> None:
    """Validate an existing authority without initializing or changing it."""
    if not catalogue.is_file() or not authority.is_file():
        raise RuntimeError("catalogue and authority must be existing files")
    if catalogue.resolve() != authority.resolve():
        # An alternate store is allowed only when it already has the exact mandate.
        pass
    required = {"execution_mandates", "execution_mandate_contracts", "execution_mandate_events", "execution_mandate_reservations"}
    try:
        conn = sqlite3.connect(f"file:{authority}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("authority integrity check failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("authority foreign-key check failed")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required.issubset(tables):
            raise RuntimeError("authority lacks existing execution-mandate structures")
        mandate = conn.execute("SELECT * FROM execution_mandates WHERE mandate_id=?", (mandate_id,)).fetchone()
        if mandate is None or mandate["status"] != "active":
            raise RuntimeError("existing amendment-1 mandate is not active")
        if mandate["actual_spend_aud"] != "0.480103":
            raise RuntimeError("existing mandate accounting does not match the reconciled baseline")
        active_reservations = conn.execute(
            "SELECT reservation_id, reserved_aud, status FROM execution_mandate_reservations WHERE mandate_id=? AND status IN ('active','ambiguous')",
            (mandate_id,),
        ).fetchall()
        if active_reservations:
            if len(active_reservations) != 1 or dict(active_reservations[0]) != {
                "reservation_id": PARTIAL_RESERVATION,
                "reserved_aud": PARTIAL_RESERVATION_AUD,
                "status": "active",
            }:
                raise RuntimeError("unexpected unresolved mandate reservation")
        unresolved = Decimal(mandate["unresolved_reserved_aud"])
        expected_unresolved = Decimal(PARTIAL_RESERVATION_AUD) if active_reservations else Decimal("0")
        if unresolved != expected_unresolved:
            raise RuntimeError("mandate unresolved exposure does not match durable reservations")
        active = conn.execute("SELECT count(1) FROM execution_mandates WHERE status='active' AND phase_scope='phase5-build-calibration'").fetchone()[0]
        if active != 1:
            raise RuntimeError("unexpected number of active Phase-5 mandates")
        contracts = {row[0] for row in conn.execute("SELECT contract_key FROM execution_mandate_contracts WHERE mandate_id=?", (mandate_id,))}
        if "urn:charitygraph:builder:semantic-contract:direct-service-v1:1.0" not in contracts:
            raise RuntimeError("Direct Service V1 is not allowlisted by the existing mandate")
    except sqlite3.Error as exc:
        raise RuntimeError("could not read existing authority store") from exc
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_rows(catalog: SQLiteCatalog, *, task_root: Path, corpus_dir: Path, runtime_root: Path) -> list[dict]:
    tasks = json.loads((task_root / "planned-logical-tasks.json").read_text(encoding="utf-8"))
    inv = {row["subject_id"]: row for row in json.loads((task_root / "semantic-reuse-inventory.json").read_text(encoding="utf-8"))}
    with catalog._connection() as conn:
        locators = {row["source_record_id"]: row["evidence_locator_id"] for row in conn.execute("SELECT source_record_id,evidence_locator_id FROM evidence_locators WHERE source_record_id IS NOT NULL")}
        scopes = {}
        for row in conn.execute("SELECT subject_id,scope_id FROM subject_scopes WHERE lifecycle_status='active' ORDER BY scope_id"):
            scopes.setdefault(row["subject_id"], row["scope_id"])
    rows=[]
    for task in sorted((x for x in tasks if x["claim_family_id"] == "direct-service-access-v1"), key=lambda x:x["logical_task_id"]):
        members=[]
        corpus=json.loads((corpus_dir / (inv[task["subject_id"]]["abn"] + ".json")).read_text(encoding="utf-8"))
        for member in corpus["material_members"]:
            item=json.loads(json.dumps(member)); item["evidence_locator_ids"]=[locators[s] for s in item.get("source_record_ids", []) if s in locators]; members.append(item)
        scope_id=scopes.get(task["subject_id"])
        if scope_id is None: continue
        contract=executable_contract_for(task)
        packet=materialize_execution_packet(task=task, corpus={"subject_id":task["subject_id"],"material_members":members}, contract=contract, runtime_root=runtime_root, catalog_path=catalog.path, model="gpt-5.6-luna", reasoning_effort="low", service_tier="standard")
        request=serialize_execution_packet_request(task, packet, delivery_job_id=JOB, delivery_mode="standard")
        body_bytes=json.dumps(request.body,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
        input_tokens=estimate_tokens(request.body); price=PRICING["gpt-5.6-luna"]; usd=(Decimal(input_tokens)*price["input"]+Decimal(8000)*price["output"])/Decimal(1_000_000); hard_aud=(usd*Decimal("1.52")).quantize(Decimal("0.000001"))
        rows.append({"task":task,"packet":packet,"contract":contract,"request":request,"request_body_sha256":sha(body_bytes),"input_tokens_estimate":input_tokens,"hard_max_usd":str(usd.quantize(Decimal("0.000001"))),"hard_max_aud":str(hard_aud),"scope_id":scope_id})
    return rows


def prepare(catalog: SQLiteCatalog, rows: list[dict], output: Path) -> list[dict]:
    catalog.register_cohort({"record_id":COHORT,"cohort_code":"PHASE5-DIRECT-SERVICE-V1-TOP100","definition_version":"1","membership_hash":sha("|".join(r["task"]["logical_task_id"] for r in rows).encode()),"budget_cap":{"amount":"30.00","currency":"AUD"},"created_at":NOW})
    catalog.register_run({"record_id":RUN,"cohort_id":COHORT,"run_kind":"phase5_direct_service_v1_standard","status":"planned","configuration_hash":sha(json.dumps([r["request"].provider_request_item_id for r in rows]).encode()),"created_at":NOW})
    catalog.create_delivery_job(delivery_job_id=JOB,run_id=RUN,provider_id="openai",model_route="gpt-5.6-luna",delivery_mode="standard",pricing_snapshot_id="pricing:phase5-openai-standard-v1",now=NOW)
    manifest=[]
    for row in rows:
        task=row["task"]; request=row["request"]; rid=request.provider_request_item_id
        identity={"run": RUN, "request": rid, "ordinal": 1}
        physical=deterministic_id("taskrun:",{"kind":"direct_service_standard_physical","run":RUN,"request":rid})
        attempt="deliveryattempt:" + sha(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
        reservation=deterministic_id("reservation:",{"run":RUN,"request":rid}); mandate_res=reservation
        catalog.register_task({"record_id":task["logical_task_id"],"subject_id":task["subject_id"],"cohort_id":COHORT,"task_type":"direct_service_semantics","task_schema":{"schema_id":"urn:charitygraph:builder:schema:direct-service-task:1.0"},"cache_key":sha((row["packet"].packet_hash+task["logical_task_id"]).encode()),"provider_id":"openai","model_snapshot":"gpt-5.6-luna"},run_id=RUN,now=NOW)
        catalog.reserve_cost({"record_id":reservation,"cohort_id":COHORT,"run_id":RUN,"reserved_aud":{"amount":row["hard_max_aud"],"currency":"AUD"},"model_task_ids":(task["logical_task_id"],)},now=NOW)
        catalog.reserve_execution_mandate(mandate_id=MANDATE,reservation_id=mandate_res,amount_aud=row["hard_max_aud"],now=NOW)
        catalog.prepare_physical_attempt(physical_attempt_id=physical,run_id=RUN,subject_id=task["subject_id"],delivery_mode="standard",provider_request_id=rid,model_task_ids=(task["logical_task_id"],),reservation_id=reservation,now=NOW)
        catalog.create_provider_request_item(provider_request_item_id=rid,run_id=RUN,model_task_id=task["logical_task_id"],provider_id="openai",model_route="gpt-5.6-luna",requested_delivery_mode="standard",effective_service_tier="standard",delivery_job_id=JOB,physical_attempt_id=physical,now=NOW)
        catalog.create_provider_request_attempt(delivery_attempt_id=attempt,provider_request_item_id=rid,physical_attempt_id=physical,delivery_job_id=JOB,attempt_ordinal=1,authorization_id=MANDATE,attempt_class="initial",predecessor_attempt_id=None,now=NOW)
        manifest.append({"provider_request_item_id":rid,"delivery_attempt_id":attempt,"physical_attempt_id":physical,"reservation_id":reservation,"mandate_reservation_id":mandate_res,"logical_task_id":task["logical_task_id"],"subject_id":task["subject_id"],"scope_id":row["scope_id"],"evidence_ids":[x.evidence_id for x in row["packet"].evidence_units],"provider":"openai","model":"gpt-5.6-luna","reasoning_effort":"low","delivery_mode":"standard","provider_schema_name":row["request"].schema_name,"provider_service_tier":None,"max_output_tokens":8000,"request_body":request.body,"request_body_sha256":row["request_body_sha256"],"schema_hash":row["contract"].schema_hash_for_evidence(tuple(x.evidence_id for x in row["packet"].evidence_units)),"semantic_contract_hash":row["contract"].identity_hash(tuple(x.evidence_id for x in row["packet"].evidence_units)),"contract_id":row["contract"].contract_id,"contract_version":row["contract"].contract_version,"task_profile":row["contract"].task_profile,"task_profile_version":row["contract"].task_profile_version,"prompt_sha256":row["contract"].prompt_sha256,"schema_id":row["contract"].schema_id,"schema_version":row["contract"].schema_version,"hard_max_aud":row["hard_max_aud"],"input_tokens_estimate":row["input_tokens_estimate"],"automatic_retries":0,"semantic_retries":0,"fallbacks":[],"ambiguous_resend":False})
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps({"run_id":RUN,"mandate_id":MANDATE,"request_items":manifest,"provider_operations":0},ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return manifest


def _usage(response: dict) -> dict:
    raw = response.get("usage") or {}
    details = raw.get("input_tokens_details") or {}
    reasoning = raw.get("output_tokens_details") or {}
    return {
        "input_tokens": int(raw.get("input_tokens", 0)),
        "cached_input_tokens": int(details.get("cached_tokens", 0)),
        "output_tokens": int(raw.get("output_tokens", 0)),
        "embedding_input_tokens": 0, "image_units": 0, "tool_calls": 0,
        "other_billable_units": ({"name": "reasoning_tokens", "units": int(reasoning.get("reasoning_tokens", 0))},) if reasoning.get("reasoning_tokens") is not None else (),
    }


def _cost(usage: dict) -> tuple[Decimal, Decimal]:
    price = PRICING["gpt-5.6-luna"]
    uncached = Decimal(usage["input_tokens"] - usage["cached_input_tokens"])
    usd = (uncached * price["input"] + Decimal(usage["cached_input_tokens"]) * price["cached_input"] + Decimal(usage["output_tokens"]) * price["output"]) / Decimal(1_000_000)
    return usd.quantize(Decimal("0.000001")), (usd * Decimal("1.52")).quantize(Decimal("0.000001"))


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--execute",action="store_true"); ap.add_argument("--catalogue",type=Path,default=Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")); ap.add_argument("--authorization",type=Path,default=None); ap.add_argument("--task-root",type=Path,default=Path(r"C:\CharityGraph-runtime\phase5-top100-factory-preflight-clean-v1")); ap.add_argument("--corpus-dir",type=Path,default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corpora")); ap.add_argument("--runtime-root",type=Path,default=Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1")); ap.add_argument("--output-root",type=Path,default=Path(r"C:\CharityGraph-runtime\phase5-direct-service-v1-top100-standard")); args=ap.parse_args()
    authority = args.authorization or args.catalogue
    validate_existing_authority(catalogue=args.catalogue, authority=authority)
    catalog=SQLiteCatalog(args.catalogue, authorization_path=authority).open(); catalog.migrate(); rows=load_rows(catalog,task_root=args.task_root,corpus_dir=args.corpus_dir,runtime_root=args.runtime_root); manifest=prepare(catalog,rows,args.output_root/"preparation.json")
    if not args.execute: print(json.dumps({"prepared":len(manifest),"provider_operations":0})); return 0
    def mandate(row): return evaluate_execution_against_mandate(catalog,MANDATE,row)
    parsed: dict[str, dict] = {}
    def reconcile(row, response, raw_usage):
        usage = _usage(response.body)
        actual_usd, actual_aud = _cost(usage)
        task_run_id = row["physical_attempt_id"]
        result_id = "modelresult:" + sha((task_run_id + response.body["id"] + sha(response.body.get("output_text", "").encode())).encode())
        errors = []
        output = None
        try:
            wire = DirectServiceWireOutput.model_validate_json(response.body["output_text"])
            output = wire_to_domain(wire, allowed_scope_ids={row["scope_id"]}, evidence_locators=set(row["evidence_ids"]))
        except Exception as exc:
            errors.append(str(exc)[:500])
        catalog.record_cost_entry({"cohort_id": COHORT, "run_id": RUN, "task_run_id": task_run_id, "reservation_id": row["reservation_id"], "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(actual_usd), "currency": "USD"}, "aud_cost": {"amount": str(actual_aud), "currency": "AUD"}, "usage": usage, "recorded_at": NOW, "pricing_snapshot_id": "pricing:phase5-openai-standard-v1", "fx_snapshot_id": "fx:phase5-usd-aud-1.52"}, entry_key="actual:" + task_run_id)
        reserved = Decimal(row["hard_max_aud"])
        if actual_aud < reserved:
            catalog.release_cost(row["reservation_id"], reserved - actual_aud, now=NOW, entry_key="release:" + task_run_id)
        catalog.settle_execution_mandate_reservation(mandate_id=MANDATE, reservation_id=row["mandate_reservation_id"], actual_aud=actual_aud, ambiguous=False, now=NOW)
        owner = OWNER
        if catalog.claim_task(row["logical_task_id"], owner=owner, lease_expires_at="2026-09-10T01:00:00+00:00", now=NOW):
            catalog.begin_task_attempt(row["logical_task_id"], owner=owner, task_run_id=task_run_id, now=NOW, provider_request_id=response.request_id, reservation_id=row["reservation_id"])
            if errors:
                catalog.finish_failed_attempt(task_run_id, owner=owner, completed_at=NOW, retryable=False, error_class="output_validation", error_message_redacted="Direct Service output validation failed", result_artifact_id=result_id, provider_request_id=response.request_id, usage=usage, pricing_snapshot_id="pricing:phase5-openai-standard-v1", fx_snapshot_id="fx:phase5-usd-aud-1.52")
            else:
                catalog.finish_successful_attempt(task_run_id, owner=owner, completed_at=NOW, result_artifact_id=result_id, provider_request_id=response.request_id, usage=usage, pricing_snapshot_id="pricing:phase5-openai-standard-v1", fx_snapshot_id="fx:phase5-usd-aud-1.52")
        parsed[row["provider_request_item_id"]] = {"response_id": response.body["id"], "valid": not errors, "errors": errors, "proposition_count": len(output.propositions) if output else 0, "relationship_count": len(output.relationships) if output else 0, "usage": usage, "actual_usd": str(actual_usd), "actual_aud": str(actual_aud), "result_id": result_id}
        (args.output_root / "candidate-results").mkdir(parents=True, exist_ok=True)
        (args.output_root / "candidate-results" / (row["provider_request_item_id"].replace(":", "_") + ".json")).write_text(json.dumps(parsed[row["provider_request_item_id"]] | {"output": output.model_dump(mode="json") if output else None}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    def validate(body):
        DirectServiceWireOutput.model_validate_json(body["output_text"])
    result=StandardCampaignCoordinator(catalog=catalog,provider=OpenAIHTTPStandardClient(),runtime_root=args.output_root,max_concurrency=4,now=NOW,validator=validate,on_reconciled=reconcile,mandate_evaluator=mandate).run(manifest)
    result["candidate_results"] = parsed
    (args.output_root/"execution.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(result,sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
