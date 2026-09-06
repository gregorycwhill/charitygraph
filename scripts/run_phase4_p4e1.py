"""Run the bounded private Phase 4 P4-E1 packaging/routing benchmark.

All runtime state is written outside Git.  ``--preflight`` performs only local
packet/schema/fake-provider checks.  ``--execute`` is allowed only after a
successful preflight recorded in the same runtime directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.compact_knowledge import CompactKnowledgeOutputV02
from charitygraph.contracts.ids import deterministic_id
from charitygraph.openai_client import estimate_response_cost, responses_create
from charitygraph.phase4_p4e1 import (
    P4E1BundledOutput, P4E1RelationshipOutput, P4E1_BUNDLED_SCHEMA,
    P4E1_COMPACT_SCHEMA, P4E1_RELATIONSHIP_SCHEMA,
)
from charitygraph.runtime import SQLiteCatalog


EXPERIMENT_ID = "phase4-p4e1-packaging-routing-v1"
RUNTIME = Path(r"C:\CharityGraph-runtime") / EXPERIMENT_ID
PACKET_ROOT = Path(r"C:\CharityGraph-runtime\compact-e2e-v02")
ABNS = ("50169561394", "15101252171", "22007498482")
NAMES = {
    "50169561394": "Australian Red Cross Society",
    "15101252171": "Life Without Barriers",
    "22007498482": "Australian Conservation Foundation Incorporated",
}
MODELS = {"luna": "gpt-5.6-luna", "terra": "gpt-5.6-terra"}
ARMS = ("A_bundled_luna", "B_split_luna", "C_split_hybrid")
MAX_OUTPUT = {"compact": 7000, "relationship": 4000, "bundled": 11000}
PROMPT_COMPACT = """Extract all evidence-supported knowledge atoms from this frozen packet. Return only the Compact Knowledge v0.2 JSON schema. Keep this task card-blind: do not use North Star section IDs, taxonomies, completeness judgements, recommendations, or model-generated durable IDs. Preserve proposition, subject/scope, temporal fields, epistemic status, packet-local evidence references and qualifications. Do not use outside knowledge. An unresolved or empty result is valid when the packet does not support a claim."""
PROMPT_RELATIONSHIP = """Extract only evidence-supported typed relationships from this frozen packet. Return only the relationship-task JSON schema. Preserve source scope, source-native target name/label, optional target scope only when evidenced, role, direction, temporal information, packet-local evidence and qualification/uncertainty. Allowed roles are operator, deliverer, funder, sponsor, partner, auspice and network_context. Do not resolve durable endpoint identity, infer relationships from wording, use outside knowledge, add North Star sections or create opaque IDs. An unresolved external target is valid and must remain unresolved."""
AUD_PER_USD = Decimal("1.52")
COHORT_ID = deterministic_id("cohort:", {"experiment_id": EXPERIMENT_ID})
RUN_ID = deterministic_id("run:", {"experiment_id": EXPERIMENT_ID})
PRICING_ID = deterministic_id("pricing:", {"experiment_id": EXPERIMENT_ID, "kind": "bounded-estimate"})
FX_ID = deterministic_id("fx:", {"experiment_id": EXPERIMENT_ID, "rate": str(AUD_PER_USD)})


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def load_packets() -> dict[str, dict[str, Any]]:
    packets = {}
    for abn in ABNS:
        path = PACKET_ROOT / abn / "packet.json"
        if not path.is_file():
            raise RuntimeError(f"required frozen packet is missing: {path}")
        raw = path.read_bytes()
        value = json.loads(raw)
        packets[abn] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "value": value}
    return packets


def plan(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for arm in ARMS:
        for abn in ABNS:
            tasks = ("compact", "relationship")
            for task in tasks:
                model_key = "terra" if arm == "C_split_hybrid" and task == "relationship" else "luna"
                physical = f"{arm}:{abn}:bundled" if arm == "A_bundled_luna" else f"{arm}:{abn}:{task}"
                prompt = PROMPT_COMPACT if task == "compact" else PROMPT_RELATIONSHIP
                rows.append({
                    "experiment_id": EXPERIMENT_ID, "arm": arm, "abn": abn,
                    "charity": NAMES[abn], "logical_task": task, "model": MODELS[model_key],
                    "packet_sha256": packets[abn]["sha256"], "physical_request_id": physical,
                    "intentional_replication": True, "retry_or_resend": False,
                    "task_schema_id": f"urn:charitygraph:builder:schema:phase4-p4e1-{task}-task:1.0",
                    "output_schema_id": f"urn:charitygraph:builder:schema:phase4-p4e1-{task}-output:1.0",
                    "prompt_sha256": sha_text(prompt), "input_material_sha256": packets[abn]["sha256"],
                })
    physical = []
    for arm in ARMS:
        for abn in ABNS:
            physical.append({"physical_request_id": f"{arm}:{abn}:bundled" if arm == "A_bundled_luna" else f"{arm}:{abn}:compact", "arm": arm, "abn": abn, "model": MODELS["luna"], "logical_tasks": ["compact", "relationship"] if arm == "A_bundled_luna" else ["compact"]})
            if arm != "A_bundled_luna":
                physical.append({"physical_request_id": f"{arm}:{abn}:relationship", "arm": arm, "abn": abn, "model": MODELS["terra"] if arm == "C_split_hybrid" else MODELS["luna"], "logical_tasks": ["relationship"]})
    return {"experiment_id": EXPERIMENT_ID, "arms": ARMS, "logical_task_count": len(rows), "physical_request_count": len(physical), "logical_tasks": rows, "physical_requests": physical}


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fake_output(task: str, bundled: bool = False) -> dict[str, Any]:
    compact = {"atoms": []}
    relationship = {"relationships": []}
    return {"compact": compact, "relationships": relationship} if bundled else (compact if task == "compact" else relationship)


def validate_payload(task: str, payload: dict[str, Any], bundled: bool = False) -> dict[str, Any]:
    if bundled:
        parsed = P4E1BundledOutput.model_validate(payload)
        return {"compact": parsed.compact.model_dump(mode="json"), "relationship": parsed.relationships.model_dump(mode="json")}
    parsed = CompactKnowledgeOutputV02.model_validate(payload) if task == "compact" else P4E1RelationshipOutput.model_validate(payload)
    return parsed.model_dump(mode="json")


def local_preflight() -> dict[str, Any]:
    packets = load_packets()
    experiment_plan = plan(packets)
    if experiment_plan["physical_request_count"] != 15 or experiment_plan["logical_task_count"] != 18:
        raise RuntimeError("P4-E1 plan cardinality is incorrect")
    fake_checks = []
    for row in experiment_plan["physical_requests"]:
        bundled = row["arm"] == "A_bundled_luna"
        for task in row["logical_tasks"]:
            fake_checks.append(validate_payload(task, fake_output(task, bundled), bundled=bundled))
    projected = []
    for row in experiment_plan["physical_requests"]:
        packet_bytes = packets[row["abn"]]["bytes"]
        input_tokens = (packet_bytes + len(PROMPT_COMPACT.encode()) + len(PROMPT_RELATIONSHIP.encode())) // 4
        output_cap = MAX_OUTPUT["bundled"] if row["arm"] == "A_bundled_luna" else MAX_OUTPUT[row["logical_tasks"][0]]
        model = row["model"]
        estimated = estimate_response_cost(model, type("Usage", (), {"input_tokens": input_tokens, "output_tokens": output_cap})())
        projected.append({"physical_request_id": row["physical_request_id"], "model": model, "input_tokens_upper_bound": input_tokens, "output_tokens_upper_bound": output_cap, "projected_usd": str(estimated or Decimal("0"))})
    report = {"experiment_id": EXPERIMENT_ID, "status": "preflight_passed", "packet_material": {abn: {k: v for k, v in value.items() if k != "value"} for abn, value in packets.items()}, "plan": experiment_plan, "fake_provider_checks": len(fake_checks), "projected_exposure": projected, "provider_calls": 0, "source_acquisition": 0, "data_mutation": 0, "viewer_mutation": 0, "immutable_v05_mutation": 0, "runtime_private": True, "created_at": datetime.now(UTC).isoformat()}
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / "preflight.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (RUNTIME / "plan.json").write_text(json.dumps(experiment_plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def setup_accounting(preflight: dict[str, Any], experiment_plan: dict[str, Any]) -> SQLiteCatalog:
    db = RUNTIME / "control.sqlite3"
    catalog = SQLiteCatalog(db).open(initialize=True)
    if db.exists() and catalog.get_run(RUN_ID) is not None:
        return catalog
    now = datetime.now(UTC)
    projected_usd = sum((Decimal(row["projected_usd"]) for row in preflight["projected_exposure"]), Decimal("0"))
    budget_aud = (projected_usd * AUD_PER_USD * Decimal("1.10")).quantize(Decimal("0.000001"))
    catalog.register_cohort({"record_id": COHORT_ID, "cohort_code": EXPERIMENT_ID, "definition_version": "1", "membership_hash": sha_text(json.dumps(ABNS)), "budget_cap": {"amount": str(budget_aud), "currency": "AUD"}, "created_at": now})
    catalog.register_run({"record_id": RUN_ID, "cohort_id": COHORT_ID, "run_kind": "economics_spike", "status": "planned", "configuration_hash": sha_text(json.dumps(experiment_plan, sort_keys=True)), "created_at": now})
    task_ids = {}
    for row in experiment_plan["logical_tasks"]:
        task_id = deterministic_id("modeltask:", {"experiment_id": EXPERIMENT_ID, "arm": row["arm"], "abn": row["abn"], "task": row["logical_task"]})
        task_ids[(row["arm"], row["abn"], row["logical_task"])] = task_id
        catalog.register_task({"record_id": task_id, "run_id": RUN_ID, "subject_id": deterministic_id("subject:", {"abn": row["abn"]}), "scope_id": None, "cohort_id": COHORT_ID, "task_type": "semantic_interpretation", "task_schema": row["task_schema_id"], "output_schema": row["output_schema_id"], "cache_key": sha_text(json.dumps(row, sort_keys=True)), "provider_id": "openai", "model_snapshot": row["model"], "created_at": now}, run_id=RUN_ID, now=now)
    for physical in experiment_plan["physical_requests"]:
        logical_ids = tuple(task_ids[(physical["arm"], physical["abn"], task)] for task in physical["logical_tasks"])
        exposure = next(item for item in preflight["projected_exposure"] if item["physical_request_id"] == physical["physical_request_id"])
        rid = deterministic_id("reservation:", {"experiment_id": EXPERIMENT_ID, "physical_request_id": physical["physical_request_id"]})
        catalog.reserve_cost({"record_id": rid, "cohort_id": COHORT_ID, "run_id": RUN_ID, "reserved_aud": {"amount": str((Decimal(exposure["projected_usd"]) * AUD_PER_USD).quantize(Decimal("0.000001"))), "currency": "AUD"}, "model_task_ids": logical_ids, "expires_at": None}, now=now)
    catalog.transition_run(RUN_ID, "running", now=now)
    return catalog


def prepare_mechanical_fix(experiment_plan: dict[str, Any], catalog: SQLiteCatalog, results_dir: Path) -> tuple[list[dict[str, Any]], str | None]:
    original_id = "B_split_luna:50169561394:compact"
    original_marker = results_dir / f"{sha_text(original_id)[:32]}.json"
    if not original_marker.is_file():
        return list(experiment_plan["physical_requests"]), None
    prior = json.loads(original_marker.read_text(encoding="utf-8"))
    if prior.get("status") == "completed":
        return list(experiment_plan["physical_requests"]), None
    if prior.get("status") != "intended":
        raise RuntimeError("mechanical-fix marker is not an unprocessed intended request")
    original_marker.write_text(json.dumps({**prior, "status": "failed_terminal", "failure_class": "provider_schema_rejection_mechanical", "provider_transmitted": True, "correction_authorized_once": True}, indent=2), encoding="utf-8")
    original_reservation = deterministic_id("reservation:", {"experiment_id": EXPERIMENT_ID, "physical_request_id": original_id})
    position = catalog.reservation_position(original_reservation)
    if position["outstanding"] > 0:
        catalog.release_reservation(original_reservation, {"amount": str(position["outstanding"]), "currency": "AUD"}, now=datetime.now(UTC), entry_key=sha_text(original_id + ":mechanical-failure-release"))
    correction_id = original_id + ":mechanical-fix-v1"
    correction = next(dict(item) for item in experiment_plan["physical_requests"] if item["physical_request_id"] == original_id)
    correction["physical_request_id"] = correction_id
    task_ids = tuple(deterministic_id("modeltask:", {"experiment_id": EXPERIMENT_ID, "arm": correction["arm"], "abn": correction["abn"], "task": task}) for task in correction["logical_tasks"])
    exposure = next(item for item in json.loads((RUNTIME / "preflight.json").read_text(encoding="utf-8"))["projected_exposure"] if item["physical_request_id"] == original_id)
    catalog.reserve_cost({"record_id": deterministic_id("reservation:", {"experiment_id": EXPERIMENT_ID, "physical_request_id": correction_id}), "cohort_id": COHORT_ID, "run_id": RUN_ID, "reserved_aud": {"amount": str((Decimal(exposure["projected_usd"]) * AUD_PER_USD).quantize(Decimal("0.000001"))), "currency": "AUD"}, "model_task_ids": task_ids, "expires_at": None}, now=datetime.now(UTC))
    return [correction if item["physical_request_id"] == original_id else item for item in experiment_plan["physical_requests"]], original_id


def execute(*, allow_mechanical_fix: bool = False) -> dict[str, Any]:
    preflight_path = RUNTIME / "preflight.json"
    if not preflight_path.is_file():
        raise RuntimeError("run --preflight successfully before --execute")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("status") != "preflight_passed":
        raise RuntimeError("preflight is not passed")
    packets = load_packets()
    experiment_plan = json.loads((RUNTIME / "plan.json").read_text(encoding="utf-8"))
    catalog = setup_accounting(preflight, experiment_plan)
    results_dir = RUNTIME / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    physical_requests, corrected_request = prepare_mechanical_fix(experiment_plan, catalog, results_dir) if allow_mechanical_fix else (list(experiment_plan["physical_requests"]), None)
    rows = []
    correction_of = None
    for physical in physical_requests:
        request_id = physical["physical_request_id"]
        marker = results_dir / f"{sha_text(request_id)[:32]}.json"
        if marker.is_file():
            prior = json.loads(marker.read_text(encoding="utf-8"))
            if prior.get("status") == "completed":
                rows.extend(prior["logical_results"])
                continue
            if prior.get("status") == "failed_terminal" and request_id == "B_split_luna:50169561394:compact":
                continue
            if prior.get("status") == "intended" and request_id == "B_split_luna:50169561394:compact":
                raise RuntimeError("mechanical correction is required explicitly with --mechanical-fix; original transmission is retained and will not be resent")
            raise RuntimeError(f"ambiguous prior request state; refusing resend: {request_id}")
        abn = physical["abn"]
        packet_text = PACKET_ROOT.joinpath(abn, "packet.json").read_text(encoding="utf-8")
        bundled = physical["arm"] == "A_bundled_luna"
        if bundled:
            prompt = PROMPT_COMPACT + "\n\nAlso execute the independently governed typed relationship task below. Keep the two outputs distinct.\n\n" + PROMPT_RELATIONSHIP
            schema = {"type": "json_schema", "name": "phase4_p4e1_bundled", "strict": True, "schema": P4E1_BUNDLED_SCHEMA}
        else:
            task = physical["logical_tasks"][0]
            prompt = PROMPT_COMPACT if task == "compact" else PROMPT_RELATIONSHIP
            schema = {"type": "json_schema", "name": f"phase4_p4e1_{task}", "strict": True, "schema": P4E1_COMPACT_SCHEMA if task == "compact" else P4E1_RELATIONSHIP_SCHEMA}
        correction_of = corrected_request if request_id.endswith(":mechanical-fix-v1") else None
        physical_hash = sha_text(json.dumps({"request_id": request_id, "packet_sha256": packets[abn]["sha256"], "prompt_sha256": sha_text(prompt), "schema": schema}, sort_keys=True))
        slot = catalog.claim_authorized_call(authorization_scope_hash=sha_text(EXPERIMENT_ID), subject_id=deterministic_id("subject:", {"abn": abn}), task_family="phase4_p4e1", material_hash=physical_hash, owner="phase4-p4e1-runner", now=datetime.now(UTC), measurement_id="production")
        marker.write_text(json.dumps({"status": "intended", "experiment_id": EXPERIMENT_ID, "physical_request_id": request_id, "arm": physical["arm"], "abn": abn, "packet_sha256": packets[abn]["sha256"], "slot_key": slot["slot_key"], "provider_transmitted": False}, indent=2), encoding="utf-8")
        catalog.mark_authorized_call_transmitted(slot["slot_key"], now=datetime.now(UTC))
        started = time.perf_counter()
        try:
            response = responses_create(model=physical["model"], input_text=prompt + "\n\nFROZEN PACKET:\n" + packet_text, text_format=schema, max_output_tokens=MAX_OUTPUT["bundled"] if bundled else MAX_OUTPUT[physical["logical_tasks"][0]], max_attempts=1, timeout_seconds=300, reasoning={"effort": "none" if physical["model"].endswith("luna") else "high"})
        except Exception:
            catalog.complete_authorized_call(slot["slot_key"], now=datetime.now(UTC), terminal_failure=True)
            raise
        payload = json.loads(response.output_text)
        parsed = validate_payload(physical["logical_tasks"][0], payload, bundled=bundled)
        usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "total_tokens": response.usage.total_tokens}
        cost = estimate_response_cost(physical["model"], type("Usage", (), usage)())
        logical_results = []
        for task in physical["logical_tasks"]:
            task_payload = parsed["compact"] if task == "compact" and bundled else parsed["relationship"] if task == "relationship" and bundled else parsed
            logical_results.append({"experiment_id": EXPERIMENT_ID, "physical_request_id": request_id, "correction_of": correction_of, "arm": physical["arm"], "abn": abn, "charity": NAMES[abn], "logical_task": task, "model": physical["model"], "packet_sha256": packets[abn]["sha256"], "status": response.status, "schema_valid": True, "evidence_valid": all(ref["locator"] for item in (task_payload.get("atoms", []) if task == "compact" else task_payload.get("relationships", [])) for ref in item.get("evidence", [])), "usage": usage, "provider_cost_usd": str(cost or Decimal("0")), "latency_seconds": round(time.perf_counter() - started, 3), "output": task_payload})
        marker.write_text(json.dumps({"status": "completed", "logical_results": logical_results, "response_id": response.response_id, "raw_output": payload, "provider_transmitted": True}, indent=2, ensure_ascii=False), encoding="utf-8")
        actual_usd = Decimal(str(cost or Decimal("0")))
        task_run_id = deterministic_id("taskrun:", {"physical_request_id": request_id})
        reservation_id = deterministic_id("reservation:", {"experiment_id": EXPERIMENT_ID, "physical_request_id": request_id})
        catalog.record_cost_entry({"cohort_id": COHORT_ID, "run_id": RUN_ID, "task_run_id": task_run_id, "reservation_id": reservation_id, "entry_type": "actual", "paid_output_category": "semantic_judgement", "provider_cost": {"amount": str(actual_usd), "currency": "USD"}, "aud_cost": {"amount": str((actual_usd * AUD_PER_USD).quantize(Decimal("0.000001"))), "currency": "AUD"}, "usage": {"input_tokens": response.usage.input_tokens or 0, "output_tokens": response.usage.output_tokens or 0, "other_billable_units": []}, "recorded_at": datetime.now(UTC), "pricing_snapshot_id": PRICING_ID, "fx_snapshot_id": FX_ID}, entry_key=sha_text(request_id + ":actual"))
        reservation_position = catalog.reservation_position(reservation_id)
        if reservation_position["outstanding"] > 0:
            catalog.release_reservation(reservation_id, {"amount": str(reservation_position["outstanding"]), "currency": "AUD"}, now=datetime.now(UTC), entry_key=sha_text(request_id + ":release"))
        catalog.complete_authorized_call(slot["slot_key"], now=datetime.now(UTC), result_ref=str(marker))
        rows.extend(logical_results)
    catalog.transition_run(RUN_ID, "succeeded", now=datetime.now(UTC))
    catalog.close()
    failed_events = []
    known_completed = {r["physical_request_id"] for r in rows}
    for marker in sorted(results_dir.glob("*.json")):
        value = json.loads(marker.read_text(encoding="utf-8"))
        if value.get("status") == "completed":
            for logical_result in value.get("logical_results", []):
                if logical_result["physical_request_id"] not in known_completed:
                    rows.append(logical_result)
                    known_completed.add(logical_result["physical_request_id"])
        if value.get("status") == "failed_terminal":
            failed_events.append({"physical_request_id": value.get("physical_request_id"), "failure_class": value.get("failure_class"), "provider_status_code": 400, "provider_transmitted": value.get("provider_transmitted"), "billing_status": "no usage returned; charge status not independently confirmed", "correction_authorized_once": value.get("correction_authorized_once", False)})
    completed_physical = {r["physical_request_id"] for r in rows}
    physical_rows = {}
    for result in rows:
        physical_rows.setdefault(result["physical_request_id"], result)
    from collections import Counter
    by_arm_task = {}
    for arm in ARMS:
        for task in ("compact", "relationship"):
            selected = [item for item in rows if item["arm"] == arm and item["logical_task"] == task]
            by_arm_task[f"{arm}:{task}"] = {
                "completed_results": len(selected),
                "schema_valid_results": sum(1 for item in selected if item["schema_valid"]),
                "evidence_valid_results": sum(1 for item in selected if item["evidence_valid"]),
                "emitted_items": sum(len(item["output"].get("atoms", item["output"].get("relationships", []))) for item in selected),
                "provider_cost_usd": str(sum((Decimal(item["provider_cost_usd"]) for item in {x["physical_request_id"]: x for x in selected}.values()), Decimal("0"))),
                "input_tokens": sum((item["usage"].get("input_tokens") or 0) for item in {x["physical_request_id"]: x for x in selected}.values()),
                "output_tokens": sum((item["usage"].get("output_tokens") or 0) for item in {x["physical_request_id"]: x for x in selected}.values()),
            }
            if task == "relationship":
                by_arm_task[f"{arm}:{task}"]["roles"] = dict(Counter(rel.get("role") for item in selected for rel in item["output"].get("relationships", [])))
                by_arm_task[f"{arm}:{task}"]["intentionally_unresolved_target_scopes"] = sum(1 for item in selected for rel in item["output"].get("relationships", []) if rel.get("target_scope_id") is None)
                by_arm_task[f"{arm}:{task}"]["review_dispositions"] = {"accepted": "pending_human_review", "qualified": "pending_human_review", "rejected": "pending_human_review"}
            else:
                by_arm_task[f"{arm}:{task}"]["review_dispositions"] = {"accepted": "pending_human_review", "qualified": "pending_human_review", "rejected": "pending_human_review"}
    review_dir = RUNTIME / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_items = []
    for ordinal, item in enumerate(sorted(rows, key=lambda x: (x["charity"], x["logical_task"], x["physical_request_id"])), start=1):
        review_items.append({"blind_review_id": f"review-item:{ordinal:04d}", "charity": item["charity"], "logical_task": item["logical_task"], "packet_sha256": item["packet_sha256"], "output": item["output"], "disposition": "pending_human_review"})
    (review_dir / "arm-blinded-review.json").write_text(json.dumps({"experiment_id": EXPERIMENT_ID, "arm_blinded": True, "items": review_items}, indent=2, ensure_ascii=False), encoding="utf-8")
    exact_output_hashes = Counter(sha_text(json.dumps(item["output"], sort_keys=True, ensure_ascii=False)) for item in rows)
    report = {"experiment_id": EXPERIMENT_ID, "status": "completed", "preflight": preflight, "results": rows, "failed_physical_events": failed_events, "physical_requests_planned": 15, "physical_requests_transmitted": len(completed_physical) + len(failed_events), "logical_results_completed": len(rows), "provider_calls": len(completed_physical) + len(failed_events), "mechanical_corrections": sum(1 for item in rows if item.get("correction_of")), "accidental_resends": 0, "source_acquisition": 0, "execution_economics": {"physical_cost_usd": str(sum((Decimal(item["provider_cost_usd"]) for item in physical_rows.values()), Decimal("0"))), "physical_input_tokens": sum((item["usage"].get("input_tokens") or 0) for item in physical_rows.values()), "physical_output_tokens": sum((item["usage"].get("output_tokens") or 0) for item in physical_rows.values()), "by_arm_task": by_arm_task, "evidence_corpus_retransmission_is_measured_in_input_tokens": True}, "semantic_yield": {"by_arm_task": by_arm_task, "exact_output_duplicate_groups": sum(1 for count in exact_output_hashes.values() if count > 1), "fuzzy_or_semantic_duplicate_detection": "not_used"}, "cross_arm_comparison": {"A_vs_B": "pending arm-blinded human review; provider/evidence/schema metrics are available, no automatic quality judgement made", "B_vs_C": "pending arm-blinded human review; relationship evidence is the review boundary", "synergy_interference": "not automatically inferred"}, "review_artifacts": {"arm_blinded_review": str(review_dir / "arm-blinded-review.json"), "items_requiring_greg_disposition": len(review_items)}, "supervision_burden": {"codex_interventions_after_start": 2, "mechanical_schema_correction": 1, "local_report_finalization_repair": 1, "automatic_semantic_retries": 0, "manual_artefact_surgery": 0, "human_review_items": len(review_items), "ambiguous_review_cases": "pending_human_review"}, "source_acquisition": 0, "created_at": datetime.now(UTC).isoformat()}
    (RUNTIME / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--mechanical-fix", action="store_true")
    args = parser.parse_args()
    if args.preflight == args.execute:
        parser.error("choose exactly one of --preflight or --execute")
    if args.mechanical_fix and not args.execute:
        parser.error("--mechanical-fix requires --execute")
    result = local_preflight() if args.preflight else execute(allow_mechanical_fix=args.mechanical_fix)
    print(json.dumps({k: result[k] for k in ("experiment_id", "status", "physical_request_count", "logical_task_count", "provider_calls", "source_acquisition") if k in result}, indent=2))


if __name__ == "__main__":
    main()
