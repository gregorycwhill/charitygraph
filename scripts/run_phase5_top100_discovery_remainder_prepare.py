"""Prepare, but never transmit, the remaining Top-100 Discovery V2 Standard campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_discovery_campaign import (
    INPUT_ALLOWANCE_FACTOR,
    PHASE5_CAMPAIGN_BUDGET_AUD,
    STANDARD_OUTPUT_TOKENS,
    campaign_budget_fits,
    conservative_input_allowance,
    standard_hard_max_aud,
    standard_hard_max_usd,
)
from charitygraph.phase5_execution_packet import materialize_execution_packet
from charitygraph.phase5_openai_dry_run import PRICING, estimate_tokens, serialize_execution_packet_request
from charitygraph.phase5_semantic_contracts import executable_contract_for, sha256_json
from charitygraph.runtime.catalog import SQLiteCatalog
from charitygraph.native_program_discovery import build_discovery_task_v2


HISTORICAL_ROOT = Path(r"C:\CharityGraph-runtime\top100-terra-v31-20260829")
IDENTITY_REPORT = Path(r"C:\CharityGraph-runtime\phase5-top100-subject-bootstrap-v1\identity-map.json")
PROJECTION = Path(r"C:\CharityGraph-runtime\phase5-top100-acnc-addressed-v1\addressed-projection.json")
CORPUS_DIR = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1-clean\corpora")
RUNTIME_ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-baseline-corpus-v1")
CATALOG = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
OUTPUT_ROOT = Path(r"C:\CharityGraph-runtime\phase5-discovery-v2-top100-remainder-standard-v1")
PRICING_ID = "openai-model-pages-2026-09-07"
FX_ID = "fx:usd-aud-1.52-2026-09-07"
AUD_PER_USD = Decimal("1.52")
FIXED_NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)
CAMPAIGN_CODE = "phase5-discovery-v2-top100-remainder-standard-v1"
MODEL = "gpt-5.6-luna"
CLAIM_FAMILY = "program-service-discovery-v2"
COMPLETED_ABNS = {
    "50169561394", "22627812672", "84114483091", "56749449191",
    "57001594074", "74851544037", "33107782196",
}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_json(value: Any) -> str:
    return _sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _opaque_deterministic_id(prefix: str, value: Any) -> str:
    return prefix + _sha_json(value)


def _cohort_and_identity() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str]:
    cohort_path = HISTORICAL_ROOT / "top100-cohort-manifest.json"
    cohort_manifest = _json(cohort_path)
    cohort_bytes = cohort_path.read_bytes()
    cohort = cohort_manifest["selected"]
    if len(cohort) != 100 or {row["donation_rank_2024_public"] for row in cohort} != set(range(1, 101)) or len({row["abn"] for row in cohort}) != 100:
        raise RuntimeError("authoritative cohort is not exactly ranks 1-100")
    identity = _json(IDENTITY_REPORT)
    rows = {row["abn"]: row for row in identity["rows"]}
    if len(rows) != 100:
        raise RuntimeError("identity report does not contain exactly 100 ABNs")
    return cohort, rows, _sha_bytes(cohort_bytes)


def _completed_identity_rows() -> list[dict[str, Any]]:
    six = _json(Path(r"C:\CharityGraph-runtime\phase5-discovery-v2-six-subject-slice-utf8-correction-v1\six-subject-preparation-utf8-correction.json"))
    rows = []
    for item in six["request_items"]:
        task = item["task"]
        rows.append({
            "abn": item["abn"], "subject_id": item["subject_id"], "logical_task_id": task["logical_task_id"],
            "provider_request_item_id": item["provider_request_item_id"], "semantic_contract_hash": item["semantic_contract_hash"],
            "schema_hash": item["schema_hash"], "result_status": "completed", "result_ref": "batch-result:retained",
        })
    control = _json(Path(r"C:\CharityGraph-runtime\phase5-first-paid-discovery-control-v6\authorization-manifest.json"))
    reconciliation = _json(Path(r"C:\CharityGraph-runtime\phase5-first-paid-discovery-control-v6\corrected-envelope-reconciliation.json"))
    rows.append({
        "abn": "50169561394", "subject_id": control["subject_id"], "logical_task_id": control["logical_task_id"],
        "provider_request_item_id": control["provider_request_item_id"], "semantic_contract_hash": control["semantic_contract_hash"],
        "schema_hash": control["schema_hash"], "result_status": reconciliation["classification"], "result_ref": reconciliation["responses_id"],
    })
    if {row["abn"] for row in rows} != COMPLETED_ABNS or any(row["result_status"] != "completed" and row["result_status"] != "provider_item_successful_completed" for row in rows):
        raise RuntimeError("completed production Discovery V2 identity set is not the expected seven")
    return sorted(rows, key=lambda row: row["abn"])


def _build_rows(catalog: SQLiteCatalog, cohort: list[dict[str, Any]], identities: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    projection = _json(PROJECTION)
    if len(projection["members"]) != 100:
        raise RuntimeError("addressed projection is not exactly 100 members")
    specs: list[dict[str, Any]] = []
    completed = _completed_identity_rows()
    for member in sorted(projection["members"], key=lambda row: row["subject_id"]):
        identity = next((row for row in identities.values() if row["subject_id"] == member["subject_id"]), None)
        if identity is None:
            raise RuntimeError(f"addressed subject has no governed ABN binding: {member['subject_id']}")
        abn = identity["abn"]
        if abn in COMPLETED_ABNS:
            continue
        cohort_row = next(row for row in cohort if row["abn"] == abn)
        corpus = _json(CORPUS_DIR / f"{abn}.json")
        acnc_members = [row for row in corpus["material_members"] if row.get("source_family") == "acnc_register"]
        if len(acnc_members) != 1:
            raise RuntimeError(f"expected one ACNC corpus member for {abn}")
        acnc = dict(acnc_members[0])
        acnc["evidence_locator_ids"] = [member["evidence_locator_id"]]
        packet_corpus = {**corpus, "material_members": [acnc]}
        evidence_corpus_hash = _sha_json({"subject_id": member["subject_id"], "source_record_id": member["source_record_id"], "evidence_locator_id": member["evidence_locator_id"], "material_hash": member["material_hash"]})
        task = {
            "logical_task_id": deterministic_id("semtask:", {"campaign": CAMPAIGN_CODE, "subject_id": member["subject_id"], "evidence_corpus_hash": evidence_corpus_hash}),
            "subject_id": member["subject_id"], "claim_family_id": CLAIM_FAMILY, "task_profile": "program_service_discovery", "task_profile_version": "1",
            "prompt_policy_version": "program-service-discovery-v2:prompt-policy:v1", "schema_version": "urn:charitygraph:phase5:planned:program_service_discovery:v1",
            "evidence_corpus_hash": evidence_corpus_hash, "difficulty": "lower_cost_constrained_semantic", "abn": abn,
            "charity_name": cohort_row["charity_name"], "rank": cohort_row["donation_rank_2024_public"], "evidence_locator_id": member["evidence_locator_id"],
            "source_record_id": member["source_record_id"], "material_hash": member["material_hash"], "packet_corpus": packet_corpus,
        }
        typed = build_discovery_task_v2(catalog, subject_id=task["subject_id"], evidence_ids=[task["evidence_locator_id"]], prompt_template_id="program_service_discovery", prompt_template_version="1", provider_id="openai", model_snapshot=MODEL)
        task["logical_task_id"] = typed.record_id
        contract = executable_contract_for(task)
        packet = materialize_execution_packet(task=task, corpus=packet_corpus, contract=contract, runtime_root=RUNTIME_ROOT, catalog_path=CATALOG, model=MODEL, reasoning_effort="low", service_tier="standard")
        request = serialize_execution_packet_request(task, packet, delivery_job_id="pending", delivery_mode="standard")
        estimate = estimate_tokens(request.body)
        allowance = conservative_input_allowance(estimate)
        hard_usd = standard_hard_max_usd(estimate, input_price_per_million=PRICING[MODEL]["input"], output_price_per_million=PRICING[MODEL]["output"])
        hard_aud = standard_hard_max_aud(hard_usd, AUD_PER_USD)
        specs.append({"task": task, "contract": contract, "packet": packet, "request": request, "estimate": estimate, "allowance": allowance, "hard_usd": hard_usd, "hard_aud": hard_aud})
    if len(specs) != 93:
        raise RuntimeError(f"remaining addressed cohort is {len(specs)}, expected 93")
    return specs, completed


def prepare(*, output_root: Path = OUTPUT_ROOT, catalog_path: Path = CATALOG) -> dict[str, Any]:
    cohort, identities, cohort_hash = _cohort_and_identity()
    catalog = SQLiteCatalog(catalog_path).open()
    try:
        specs, completed = _build_rows(catalog, cohort, identities)
        total_aud = sum((item["hard_aud"] for item in specs), Decimal("0"))
        if not campaign_budget_fits(total_aud):
            raise RuntimeError(f"hard exposure {total_aud} AUD exceeds Phase-5 cap {PHASE5_CAMPAIGN_BUDGET_AUD} AUD")
        campaign_hash = _sha_json({"code": CAMPAIGN_CODE, "cohort_manifest_sha256": cohort_hash, "completed": completed, "request_ids": [item["request"].provider_request_item_id for item in specs]})
        cohort_id = deterministic_id("cohort:", {"campaign": campaign_hash})
        run_id = deterministic_id("run:", {"campaign": campaign_hash})
        authorization_id = "authorization:" + CAMPAIGN_CODE
        now = FIXED_NOW
        catalog.register_cohort({"record_id": cohort_id, "cohort_code": CAMPAIGN_CODE, "definition_version": "standard-campaign-v1", "membership_hash": campaign_hash, "budget_cap": {"amount": str(PHASE5_CAMPAIGN_BUDGET_AUD), "currency": "AUD"}, "created_at": now})
        catalog.register_run({"record_id": run_id, "cohort_id": cohort_id, "run_kind": "phase5_discovery_v2_top100_remainder_standard", "status": "planned", "configuration_hash": campaign_hash, "created_at": now})
        request_rows: list[dict[str, Any]] = []
        for item in specs:
            task = item["task"]
            typed = build_discovery_task_v2(catalog, subject_id=task["subject_id"], evidence_ids=[task["evidence_locator_id"]], prompt_template_id="program_service_discovery", prompt_template_version="1", provider_id="openai", model_snapshot=MODEL)
            task_id = typed.record_id
            if catalog.get_task(task_id) is None:
                catalog.register_task(typed, run_id=run_id, now=now)
            request = serialize_execution_packet_request(task, item["packet"], delivery_job_id="pending", delivery_mode="standard")
            request_item_id = request.provider_request_item_id
            delivery_job_id = deterministic_id("deliveryjob:", {"run_id": run_id, "request_item_id": request_item_id})
            request = serialize_execution_packet_request(task, item["packet"], delivery_job_id=delivery_job_id, delivery_mode="standard")
            request_item_id = request.provider_request_item_id
            reservation_id = deterministic_id("reservation:", {"run_id": run_id, "request_item_id": request_item_id})
            physical_id = _opaque_deterministic_id("physical:", {"run_id": run_id, "request_item_id": request_item_id})
            attempt_id = _opaque_deterministic_id("deliveryattempt:", {"run_id": run_id, "request_item_id": request_item_id})
            catalog.create_delivery_job(delivery_job_id=delivery_job_id, run_id=run_id, provider_id="openai", model_route=MODEL, delivery_mode="standard", pricing_snapshot_id=PRICING_ID, now=now)
            catalog.reserve_cost({"record_id": reservation_id, "cohort_id": cohort_id, "run_id": run_id, "reserved_aud": {"amount": str(item["hard_aud"]), "currency": "AUD"}, "model_task_ids": (task_id,), "expires_at": None}, now=now)
            catalog.prepare_physical_attempt(physical_attempt_id=physical_id, run_id=run_id, subject_id=task["subject_id"], delivery_mode="standard", provider_request_id=request_item_id, model_task_ids=(task_id,), reservation_id=reservation_id, now=now)
            catalog.create_provider_request_item(provider_request_item_id=request_item_id, run_id=run_id, model_task_id=task_id, provider_id="openai", model_route=MODEL, requested_delivery_mode="standard", effective_service_tier="standard", delivery_job_id=delivery_job_id, physical_attempt_id=physical_id, now=now)
            catalog.create_provider_request_attempt(delivery_attempt_id=attempt_id, provider_request_item_id=request_item_id, physical_attempt_id=physical_id, delivery_job_id=delivery_job_id, attempt_ordinal=1, authorization_id=authorization_id, attempt_class="initial", predecessor_attempt_id=None, now=now)
            request_rows.append({"abn": task["abn"], "rank": task["rank"], "charity_name": task["charity_name"], "subject_id": task["subject_id"], "logical_task_id": task_id, "provider_request_item_id": request_item_id, "delivery_job_id": delivery_job_id, "delivery_attempt_id": attempt_id, "physical_attempt_id": physical_id, "reservation_id": reservation_id, "model": MODEL, "reasoning_effort": "low", "delivery_mode": "standard", "provider_schema_name": request.schema_name, "provider_service_tier": None, "packet_hash": item["packet"].packet_hash, "semantic_contract_hash": item["contract"].identity_hash(tuple(unit.evidence_id for unit in item["packet"].evidence_units)), "schema_hash": item["contract"].schema_hash_for_evidence(tuple(unit.evidence_id for unit in item["packet"].evidence_units)), "request_body_sha256": _sha_json(request.body), "request_body": request.body, "input_tokens_estimate": item["estimate"], "authorized_input_allowance": item["allowance"], "max_output_tokens": STANDARD_OUTPUT_TOKENS, "hard_max_usd": str(item["hard_usd"]), "hard_max_aud": str(item["hard_aud"]), "evidence_locator_id": task["evidence_locator_id"], "source_record_id": task["source_record_id"]})
        preparation = {"manifest_version": "phase5-discovery-v2-standard-campaign-v1", "campaign_code": CAMPAIGN_CODE, "campaign_hash": campaign_hash, "cohort_manifest_sha256": cohort_hash, "cohort_id": cohort_id, "run_id": run_id, "authorization_id": authorization_id, "model": MODEL, "reasoning_effort": "low", "claim_family_id": CLAIM_FAMILY, "task_profile": "program_service_discovery", "task_profile_version": "1", "provider_schema_name": "program_service_discovery_v2", "delivery_mode": "standard", "provider_service_tier": "omitted", "max_output_tokens": STANDARD_OUTPUT_TOKENS, "input_allowance_factor": str(INPUT_ALLOWANCE_FACTOR), "pricing_snapshot_id": PRICING_ID, "fx_snapshot_id": FX_ID, "aud_per_usd": str(AUD_PER_USD), "concurrency": {"max_workers": 4, "basis": "modest configurable local default; no governed provider-rate limit supplied"}, "automatic_retries": 0, "fallbacks": [], "governed_promotions": 0, "provider_operations": 0, "semantic_executions": 0, "completed_existing": completed, "request_items": request_rows, "aggregate": {"request_item_count": len(request_rows), "input_tokens_estimate": sum(row["input_tokens_estimate"] for row in request_rows), "authorized_input_tokens": sum(row["authorized_input_allowance"] for row in request_rows), "expected_standard_usd": str(sum((Decimal(row["input_tokens_estimate"])/Decimal(1_000_000)*PRICING[MODEL]["input"] + Decimal(STANDARD_OUTPUT_TOKENS)/Decimal(1_000_000)*PRICING[MODEL]["output"] for row in request_rows), Decimal("0")).quantize(Decimal("0.000001"))), "hard_max_usd": str(sum((Decimal(row["hard_max_usd"]) for row in request_rows), Decimal("0"))), "hard_max_aud": str(sum((Decimal(row["hard_max_aud"]) for row in request_rows), Decimal("0"))), "budget_cap_aud": str(PHASE5_CAMPAIGN_BUDGET_AUD)}}
        output_root.mkdir(parents=True, exist_ok=True)
        _write(output_root / "standard-request-manifest.json", {"campaign_code": CAMPAIGN_CODE, "ordered_request_items": request_rows})
        preparation["standard_request_manifest_sha256"] = _sha_bytes((output_root / "standard-request-manifest.json").read_bytes())
        _write(output_root / "preparation-manifest.json", preparation)
        preparation_sha = _sha_bytes((output_root / "preparation-manifest.json").read_bytes())
        authorization = {"authorization_manifest_version": "1", "authorization_id": authorization_id, "campaign_code": CAMPAIGN_CODE, "real_provider_enabled": False, "approved_run": run_id, "preparation_manifest_sha256": preparation_sha, "standard_request_manifest_sha256": preparation["standard_request_manifest_sha256"], "model": MODEL, "reasoning_effort": "low", "delivery_mode": "standard", "provider_service_tier": "omitted", "max_concurrency": 4, "max_submissions_per_request": 1, "automatic_retries": 0, "fallbacks": [], "governed_promotion": "prohibited", "canonical_observations": "prohibited", "hard_max_usd": preparation["aggregate"]["hard_max_usd"], "hard_max_aud": preparation["aggregate"]["hard_max_aud"], "request_item_count": 93}
        _write(output_root / "authorization-manifest.json", authorization)
        authorization_sha = _sha_bytes((output_root / "authorization-manifest.json").read_bytes())
        lifecycle = {"campaign_code": CAMPAIGN_CODE, "cohort_id": cohort_id, "run_id": run_id, "authorization_id": authorization_id, "preparation_manifest_sha256": preparation_sha, "authorization_manifest_sha256": authorization_sha, "request_item_count": 93, "delivery_attempt_count": 93, "physical_attempt_count": 93, "reservation_count": 93, "provider_assigned_id_count": 0, "provider_operations": 0, "semantic_executions": 0, "batch_count": 0, "flex_count": 0, "standard_count": 93, "promotion_count": 0, "status": "prepared_not_authorized"}
        _write(output_root / "lifecycle-manifest.json", lifecycle)
        summary = {"status": "PHASE5_TOP100_DISCOVERY_V2_REMAINDER_READY_FOR_AUTHORIZATION", "authoritative_top100_count": 100, "completed_existing_count": 7, "remaining_prepared_count": 93, "completed_plus_prepared_count": 100, "provider_calls": 0, "source_acquisition": 0, "semantic_executions": 0, "promotions": 0, "batch_count": 0, "flex_count": 0, "standard_count": 93, "preparation_manifest_sha256": preparation_sha, "authorization_manifest_sha256": authorization_sha, "lifecycle_manifest_sha256": _sha_bytes((output_root / "lifecycle-manifest.json").read_bytes()), "input_tokens_estimate": preparation["aggregate"]["input_tokens_estimate"], "authorized_input_tokens": preparation["aggregate"]["authorized_input_tokens"], "expected_standard_usd": preparation["aggregate"]["expected_standard_usd"], "hard_max_usd": preparation["aggregate"]["hard_max_usd"], "hard_max_aud": preparation["aggregate"]["hard_max_aud"], "pricing_snapshot_id": PRICING_ID, "fx_snapshot_id": FX_ID}
        _write(output_root / "preparation-summary.json", summary)
        return summary
    finally:
        catalog.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    args = parser.parse_args()
    print(json.dumps(prepare(output_root=args.output_root, catalog_path=args.catalog), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
