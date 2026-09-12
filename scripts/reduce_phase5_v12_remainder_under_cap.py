"""Reduce the V1.2 remainder to Amendment-3 requests within the AUD 0.25 cap.

This script is provider-free. Without --apply it performs a read-only audit;
--apply performs only the explicitly authorized local append-only accounting,
pre-send exclusion, reservation replacement, ticket, and report operations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.contracts.ids import deterministic_id
from charitygraph.phase5_cost_cap import partition_cost_cap_requests
from charitygraph.phase5_execution_mandate import evaluate_execution_against_mandate
from charitygraph.phase5_execution_tickets import (
    canonical_bytes,
    create_cost_cap_remainder_ticket,
    sha256,
    validate_cost_cap_remainder_ticket,
)
from charitygraph.phase5_openai_dry_run import (
    conservative_standard_hard_max_aud,
    conservative_standard_hard_max_usd,
)
from charitygraph.phase5_pre_send_certification import certify_standard_execution_row
from charitygraph.runtime import SQLiteCatalog


ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")
DB = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-3"
AMENDMENT4 = "mandate:phase5-build-standard-luna-v1-amendment-4"
RUN = "run:phase5-direct-service-v1.2-cutover"
CANARY = "requestitem:eae9e3086c6f35ac6621de83d59e36310ade18e2c51e3a3c4aece1dbb9e7e987"
FX = Decimal("1.52")
CAP = Decimal("0.25")
PREP_SHA = "69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26"
JSONL_SHA = "35e1ad5ecbca107566a00010d59d4566ece4be2198f49c42a3cb61e2dc2a3f0a"
PRIMARY_AUDIT = "cost-recalibration-audit-2026-09-12.json"
CALIBRATION_ADDENDUM = "cost-recalibration-audit-2026-09-12-calibration-addendum.json"
PREDECESSOR_TICKET = "future-execution-ticket-v3.json"
NEW_TICKET = "future-execution-ticket-v4.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_sidecar(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    digest = sha256(raw)
    sidecar = path.with_name(path.name + ".sha256").read_text(encoding="ascii").split()[0]
    if sidecar != digest:
        raise RuntimeError(f"SHA-256 sidecar mismatch: {path.name}")
    return raw, digest


def _request_rows(catalog: SQLiteCatalog, preparation: dict, audit: dict, prep_raw: bytes, jsonl_raw: bytes) -> tuple[list[dict], dict[str, dict]]:
    if sha256(prep_raw) != PREP_SHA or sha256(jsonl_raw) != JSONL_SHA:
        raise RuntimeError("immutable V1.2 preparation or JSONL hash mismatch")
    source_rows = preparation.get("request_items", [])
    lines = [json.loads(line) for line in jsonl_raw.decode("utf-8", errors="strict").splitlines() if line]
    by_line = {line.get("custom_id"): line for line in lines}
    by_audit = {row["provider_request_item_id"]: row for row in audit.get("requests", [])}
    if len(source_rows) != 18 or len(by_line) != 18 or len(by_audit) != 16:
        raise RuntimeError("V1.2 preparation, immutable wire set, or recalibration audit cardinality changed")
    rows: list[dict] = []
    rows_by_id: dict[str, dict] = {}
    for source in source_rows:
        rid = source["provider_request_item_id"]
        raw_body = canonical_bytes(source["request_body"])
        body_hash = sha256(raw_body)
        if body_hash != source["request_body_sha256"] or by_line.get(rid, {}).get("body") != source["request_body"]:
            raise RuntimeError(f"provider-significant V1.2 request bytes changed: {rid}")
        durable = catalog.get_provider_request_item(rid)
        if durable is None:
            raise RuntimeError(f"authoritative request item is missing: {rid}")
        physical = catalog.get_physical_attempt(durable["physical_attempt_id"])
        attempts = catalog.list_provider_request_attempts(provider_request_item_id=rid)
        row = dict(source)
        row.update({"durable": durable, "physical": physical, "attempts": attempts, "body_sha256_verified": body_hash})
        if rid in by_audit:
            estimate = int(source["input_tokens_estimate"])
            usd = conservative_standard_hard_max_usd(estimate, int(source["max_output_tokens"]), model=source["model"])
            aud = conservative_standard_hard_max_aud(estimate, int(source["max_output_tokens"]), str(FX), model=source["model"])
            audited = by_audit[rid]
            if (int(audited["input_tokens_estimate"]) != estimate
                    or Decimal(audited["recalculated_hard_max_aud"]) != aud):
                raise RuntimeError(f"audit identity or conservative AUD calculation mismatch: {rid}")
            row.update({"old_reservation_id": audited["reservation_id"],
                        "old_reserved_aud": Decimal(audited["existing_reserved_aud"]),
                        "corrected_hard_max_usd": usd,
                        "corrected_hard_max_aud": aud,
                        "margin_to_cap_aud": CAP - aud})
            rows.append(row)
        elif rid in {CANARY, "requestitem:1c01caaa10b645ed8db98e4acf57b0366807d5be121d7bb2325a3617c9f9cfb3"}:
            continue
        else:
            raise RuntimeError(f"unexpected non-audited request item: {rid}")
        if rid in by_audit:
            rows_by_id[rid] = row
    if set(by_audit) != {r["provider_request_item_id"] for r in rows}:
        raise RuntimeError("audit does not match the exact 16 outstanding request set")
    return rows, rows_by_id


def _starting_state(catalog: SQLiteCatalog, rows_by_id: dict[str, dict], prep_rows: list[dict]) -> dict:
    mandate = catalog.get_execution_mandate(MANDATE)
    if mandate is None or mandate["status"] != "active":
        raise RuntimeError("Amendment 3 is not active")
    if catalog.get_execution_mandate(AMENDMENT4) is not None:
        raise RuntimeError("Amendment 4 exists; this task must not activate or use it")
    if Decimal(mandate["per_request_hard_aud"]) != CAP:
        raise RuntimeError("Amendment-3 per-request cap differs from AUD 0.25")
    with catalog._authorization_connection() as conn:
        active_phase5 = conn.execute("SELECT mandate_id FROM execution_mandates WHERE phase_scope='phase5-build-calibration' AND status='active'").fetchall()
    if len(active_phase5) != 1 or active_phase5[0]["mandate_id"] != MANDATE:
        raise RuntimeError("active Phase-5 mandate set is not exactly Amendment 3")
    canary = catalog.get_provider_request_item(CANARY)
    if canary is None or canary["status"] != "completed" or not canary["provider_request_id"] or not canary["provider_receipt_id"] or not canary["usage_json"]:
        raise RuntimeError("completed V1.2 canary identity or usage is missing")
    canary_attempts = catalog.list_provider_request_attempts(provider_request_item_id=CANARY)
    canary_physical = catalog.get_physical_attempt(canary["physical_attempt_id"])
    if len(canary_attempts) != 1 or canary_attempts[0]["status"] != "completed" or not canary_physical["send_started_at"]:
        raise RuntimeError("completed V1.2 canary no longer proves its single completed crossing")
    canary_reservation = canary_physical["reservation_id"]
    with catalog._authorization_connection() as conn:
        canary_mandate = conn.execute("SELECT status,actual_aud FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?", (MANDATE, canary_reservation)).fetchone()
        canary_actuals = conn.execute("SELECT provider_amount,aud_amount,usage_json FROM cost_entries WHERE reservation_id=? AND entry_type='actual'", (canary_reservation,)).fetchall()
        receipt_count = conn.execute("SELECT count(*) FROM provider_receipts WHERE physical_attempt_id=?", (canary["physical_attempt_id"],)).fetchone()[0]
    if (canary_mandate is None or canary_mandate["status"] != "settled"
            or Decimal(canary_mandate["actual_aud"]) != Decimal("0.172003")
            or len(canary_actuals) != 1 or Decimal(canary_actuals[0]["aud_amount"]) != Decimal("0.172003")
            or receipt_count != 1):
        raise RuntimeError("historical V1.2 canary accounting is not the settled one-crossing result")
    task_states = {}
    for row in rows_by_id.values():
        durable = row["durable"]
        physical = row["physical"]
        attempts = row["attempts"]
        if (durable["status"] != "prepared" or physical is None or physical["status"] != "prepared"
                or len(attempts) != 1 or attempts[0]["status"] != "prepared"
                or durable["provider_request_id"] or durable["provider_receipt_id"] or durable["usage_json"]
                or attempts[0]["provider_request_id"] or attempts[0]["provider_receipt_id"] or attempts[0]["usage_json"]
                or physical["send_started_at"] or physical["receipt_persisted_at"]):
            raise RuntimeError(f"unsent prepared request has crossing evidence or changed status: {row['provider_request_item_id']}")
        if physical["reservation_id"] != row["old_reservation_id"]:
            raise RuntimeError(f"audit reservation does not match current physical reservation: {row['provider_request_item_id']}")
        budget = catalog.get_reservation(row["old_reservation_id"])
        with catalog._authorization_connection() as conn:
            mandate_res = conn.execute("SELECT status,reserved_aud,actual_aud FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?", (MANDATE, row["old_reservation_id"])).fetchone()
        if (budget is None or budget["status"] != "active" or mandate_res is None or mandate_res["status"] != "active"
                or Decimal(budget["reserved_aud"]) != row["old_reserved_aud"]
                or Decimal(mandate_res["reserved_aud"]) != row["old_reserved_aud"]
                or Decimal(mandate_res["actual_aud"]) != 0):
            raise RuntimeError(f"starting reservation is not active unused authority: {row['provider_request_item_id']}")
        task = catalog.get_task(durable["model_task_id"])
        if task is None:
            raise RuntimeError(f"request task is missing: {row['provider_request_item_id']}")
        task_states[row["provider_request_item_id"]] = task["status"]
    with catalog._authorization_connection() as conn:
        rows_count = conn.execute("SELECT count(*) FROM provider_request_items WHERE run_id=? AND status='prepared'", (RUN,)).fetchone()[0]
        actual_entries = conn.execute("SELECT count(*) FROM cost_entries WHERE run_id=? AND entry_type='actual'", (RUN,)).fetchone()[0]
        replacement_events = conn.execute("SELECT count(*) FROM execution_mandate_events WHERE mandate_id=? AND event_type='reservation_replaced'", (MANDATE,)).fetchone()[0]
    if rows_count != 16 or actual_entries != 1 or replacement_events != 0:
        raise RuntimeError("starting V1.2 state is not exactly 16 unsent requests and one canary actual")
    return {
        "actual_spend_aud": Decimal(mandate["actual_spend_aud"]),
        "unresolved_reserved_aud": Decimal(mandate["unresolved_reserved_aud"]),
        "canary_reservation_id": canary_reservation,
        "canary_actual_aud": Decimal(canary_actuals[0]["aud_amount"]),
        "canary_actual_usd": Decimal(canary_actuals[0]["provider_amount"]),
        "canary_usage": json.loads(canary["usage_json"]),
        "task_states": task_states,
    }


def _execution_row(catalog: SQLiteCatalog, source: dict, corrected_usd: Decimal, corrected_aud: Decimal) -> dict:
    item = catalog.get_provider_request_item(source["provider_request_item_id"])
    physical = catalog.get_physical_attempt(item["physical_attempt_id"])
    attempts = catalog.list_provider_request_attempts(provider_request_item_id=item["provider_request_item_id"])
    if len(attempts) != 1:
        raise RuntimeError("V1.2 exact request must have exactly one delivery attempt")
    return dict(source,
                provider="openai", task_profile="direct_service_semantics", task_profile_version="2",
                catalog_model_task_id=item["model_task_id"], reservation_id=physical["reservation_id"],
                mandate_reservation_id=physical["reservation_id"], physical_attempt_id=physical["physical_attempt_id"],
                delivery_attempt_id=attempts[0]["delivery_attempt_id"], hard_max_usd=format(corrected_usd, ".6f"),
                hard_max_aud=format(corrected_aud, ".6f"), automatic_retries=0, semantic_retries=0,
                fallbacks=[], ambiguous_resend=False)


def _apply_partition(catalog: SQLiteCatalog, eligible: list[dict], excluded: list[dict], timestamp: str) -> int:
    for row in excluded:
        rid = row["provider_request_item_id"]
        old_res = row["old_reservation_id"]
        item = catalog.get_provider_request_item(rid)
        if item["status"] == "prepared":
            catalog.abandon_pre_send_provider_request(rid, now=timestamp, reason="economic_authority_cap_exceeded")
        elif item["status"] != "cancelled":
            raise RuntimeError(f"cost-cap exclusion has unexpected item status: {rid}")
        catalog.release_cost(old_res, {"amount": str(row["old_reserved_aud"]), "currency": "AUD"},
                             now=timestamp, entry_key="release:phase5-cost-cap-exclusion:" + rid)
        catalog.settle_execution_mandate_reservation(mandate_id=MANDATE, reservation_id=old_res,
                                                     actual_aud="0", ambiguous=False, now=timestamp)
    replacement_count = 0
    for row in eligible:
        rid = row["provider_request_item_id"]
        old_res = row["old_reservation_id"]
        new_res = deterministic_id("reservation:", {"run": RUN, "request": rid, "recalibration": "phase5-v1.2-cost-cap-2026-09-12"})
        replacement_id = deterministic_id("mandatereplacement:", {"mandate": MANDATE, "request": rid, "recalibration": "phase5-v1.2-cost-cap-2026-09-12"})
        physical = catalog.get_physical_attempt(row["physical"]["physical_attempt_id"])
        if physical["reservation_id"] == old_res:
            catalog.replace_pre_send_reservation(mandate_id=MANDATE, physical_attempt_id=physical["physical_attempt_id"],
                                                 old_reservation_id=old_res, new_reservation_id=new_res,
                                                 new_amount_aud=row["corrected_hard_max_aud"],
                                                 replacement_id=replacement_id, now=timestamp)
            replacement_count += 1
        elif physical["reservation_id"] != new_res:
            raise RuntimeError(f"eligible physical attempt points to an unexpected reservation: {rid}")
        row["new_reservation_id"] = new_res
    return replacement_count


def _verify_final(catalog: SQLiteCatalog, eligible: list[dict], excluded: list[dict], rows_by_id: dict[str, dict], start: dict) -> dict:
    mandate = catalog.get_execution_mandate(MANDATE)
    if mandate is None or mandate["status"] != "active" or catalog.get_execution_mandate(AMENDMENT4) is not None:
        raise RuntimeError("postcondition failed: Amendment 3 must remain active and Amendment 4 absent")
    if Decimal(mandate["actual_spend_aud"]) != start["actual_spend_aud"]:
        raise RuntimeError("postcondition failed: actual spend changed")
    eligible_ids = {row["provider_request_item_id"] for row in eligible}
    excluded_ids = {row["provider_request_item_id"] for row in excluded}
    with catalog._authorization_connection() as conn:
        active_rows = conn.execute("SELECT reservation_id,reserved_aud FROM execution_mandate_reservations WHERE mandate_id=? AND status='active'", (MANDATE,)).fetchall()
        replacement_events = conn.execute("SELECT event_json FROM execution_mandate_events WHERE mandate_id=? AND event_type='reservation_replaced'", (MANDATE,)).fetchall()
    active_by_id = {row["reservation_id"]: Decimal(row["reserved_aud"]) for row in active_rows}
    expected_reservations = {row["new_reservation_id"]: row["corrected_hard_max_aud"] for row in eligible}
    if active_by_id != expected_reservations:
        raise RuntimeError("postcondition failed: active Amendment-3 reservations do not exactly match the eligible 13")
    total_aud = sum((row["corrected_hard_max_aud"] for row in eligible), Decimal("0"))
    total_usd = sum((row["corrected_hard_max_usd"] for row in eligible), Decimal("0"))
    if Decimal(mandate["unresolved_reserved_aud"]) != total_aud:
        raise RuntimeError("postcondition failed: unresolved mandate exposure differs from eligible reservation sum")
    if Decimal(mandate["actual_spend_aud"]) + total_aud > Decimal(mandate["aggregate_hard_aud"]):
        raise RuntimeError("postcondition failed: Amendment-3 aggregate authority exceeded")
    for row in eligible:
        rid = row["provider_request_item_id"]
        if row["corrected_hard_max_aud"] > CAP or active_by_id[row["new_reservation_id"]] != row["corrected_hard_max_aud"]:
            raise RuntimeError(f"postcondition failed: eligible request exceeds cap or reservation mismatch: {rid}")
        old_budget = catalog.get_reservation(row["old_reservation_id"])
        old_position = catalog.reservation_position(row["old_reservation_id"])
        with catalog._authorization_connection() as conn:
            old_mandate = conn.execute("SELECT status,actual_aud,reserved_aud FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?", (MANDATE, row["old_reservation_id"])).fetchone()
        if (old_budget is None or old_budget["status"] != "released" or old_mandate is None
                or old_mandate["status"] != "settled" or Decimal(old_mandate["actual_aud"]) != 0
                or Decimal(old_mandate["reserved_aud"]) != row["old_reserved_aud"]
                or old_position["outstanding"] != 0):
            raise RuntimeError(f"postcondition failed: superseded reservation history is not preserved and released: {rid}")
        durable = catalog.get_provider_request_item(rid)
        physical = catalog.get_physical_attempt(durable["physical_attempt_id"])
        attempts = catalog.list_provider_request_attempts(provider_request_item_id=rid)
        task = catalog.get_task(durable["model_task_id"])
        with catalog._authorization_connection() as conn:
            actual_count = conn.execute("SELECT count(*) FROM cost_entries WHERE reservation_id=? AND entry_type='actual'", (row["new_reservation_id"],)).fetchone()[0]
            receipt_count = conn.execute("SELECT count(*) FROM provider_receipts WHERE physical_attempt_id=?", (physical["physical_attempt_id"],)).fetchone()[0]
        if (durable["status"] != "prepared" or physical["status"] != "prepared"
                or physical["reservation_id"] != row["new_reservation_id"] or len(attempts) != 1
                or attempts[0]["status"] != "prepared" or durable["provider_request_id"]
                or durable["provider_receipt_id"] or durable["usage_json"] or physical["send_started_at"]
                or attempts[0]["provider_request_id"] or attempts[0]["provider_receipt_id"] or attempts[0]["usage_json"]
                or actual_count != 0 or receipt_count != 0
                or task is None or task["status"] != start["task_states"][rid]):
            raise RuntimeError(f"postcondition failed: eligible request no longer has zero-crossing prepared state: {rid}")
    excluded_results = []
    for row in excluded:
        rid = row["provider_request_item_id"]
        durable = catalog.get_provider_request_item(rid)
        physical = catalog.get_physical_attempt(durable["physical_attempt_id"])
        attempts = catalog.list_provider_request_attempts(provider_request_item_id=rid)
        budget = catalog.get_reservation(row["old_reservation_id"])
        with catalog._authorization_connection() as conn:
            mandate_res = conn.execute("SELECT status,actual_aud FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?", (MANDATE, row["old_reservation_id"])).fetchone()
            actual_count = conn.execute("SELECT count(*) FROM cost_entries WHERE reservation_id=? AND entry_type='actual'", (row["old_reservation_id"],)).fetchone()[0]
        if (durable["status"] != "cancelled" or physical["status"] != "failed" or physical["send_started_at"]
                or len(attempts) != 1 or attempts[0]["status"] != "cancelled"
                or attempts[0]["failure_message_redacted"] != "economic_authority_cap_exceeded"
                or durable["provider_request_id"] or durable["provider_receipt_id"] or durable["usage_json"]
                or budget["status"] != "released" or mandate_res["status"] != "settled"
                or Decimal(mandate_res["actual_aud"]) != 0 or actual_count != 0):
            raise RuntimeError(f"postcondition failed: excluded request is not a terminal zero-crossing economic exclusion: {rid}")
        excluded_results.append({"provider_request_item_id": rid, "subject_id": row["subject_id"],
                                 "reservation_id": row["old_reservation_id"], "reservation_disposition": "released_and_settled_at_zero",
                                 "builder_reservation_status": budget["status"], "mandate_reservation_status": mandate_res["status"],
                                 "old_reserved_aud": format(row["old_reserved_aud"], ".6f"),
                                 "provider_crossings": 0, "provider_actual_cost_aud": "0",
                                 "corrected_hard_max_usd": format(row["corrected_hard_max_usd"], ".6f"),
                                 "corrected_hard_max_aud": format(row["corrected_hard_max_aud"], ".6f"),
                                 "margin_to_cap_aud": format(CAP-row["corrected_hard_max_aud"], ".6f"),
                                 "classification": "EXCLUDED_COST_CAP", "reason": "economic_authority_cap_exceeded"})
    canary = catalog.get_provider_request_item(CANARY)
    if canary["status"] != "completed" or Decimal(catalog.get_execution_mandate(MANDATE)["actual_spend_aud"]) != start["actual_spend_aud"]:
        raise RuntimeError("postcondition failed: historical canary accounting changed")
    return {"actual_spend_aud": Decimal(mandate["actual_spend_aud"]),
            "unresolved_reserved_aud": Decimal(mandate["unresolved_reserved_aud"]),
            "eligible_hard_aud": total_aud, "eligible_hard_usd": total_usd,
            "maximum_eligible_hard_aud": max(row["corrected_hard_max_aud"] for row in eligible),
            "replacement_events": len(replacement_events), "excluded_results": excluded_results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogue", type=Path, default=DB)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true", help="apply authorized local append-only economic reduction")
    args = parser.parse_args()
    if not args.catalogue.is_file() or not args.root.is_dir():
        raise SystemExit("expected existing runtime catalogue and campaign root are required")
    primary_raw, primary_sha = verify_sidecar(args.root / PRIMARY_AUDIT)
    addendum_raw, addendum_sha = verify_sidecar(args.root / CALIBRATION_ADDENDUM)
    primary = json.loads(primary_raw)
    if primary.get("blocker_code") != "PHASE5_COST_RECALIBRATION_CAP_EXCEEDED":
        raise RuntimeError("verified primary audit does not identify the expected cost-cap partition")
    prep_raw = (args.root / "preparation.json").read_bytes()
    jsonl_raw = (args.root / "requests.jsonl").read_bytes()
    preparation = json.loads(prep_raw)
    catalog = SQLiteCatalog(args.catalogue, authorization_path=args.catalogue).open()
    rows, rows_by_id = _request_rows(catalog, preparation, primary, prep_raw, jsonl_raw)
    eligible, excluded = partition_cost_cap_requests(rows)
    if ({r["provider_request_item_id"] for r in eligible + excluded}
            != {r["provider_request_item_id"] for r in primary["requests"]}):
        raise RuntimeError("partition is not derived from the verified audit set")
    if not eligible or any(row["corrected_hard_max_aud"] > CAP for row in eligible) or any(row["corrected_hard_max_aud"] <= CAP for row in excluded):
        raise RuntimeError("mechanical cost-cap partition is invalid")
    start = _starting_state(catalog, rows_by_id, preparation["request_items"])
    prior_ticket_path = args.root / PREDECESSOR_TICKET
    prior_ticket_raw = prior_ticket_path.read_bytes()
    prior_ticket = json.loads(prior_ticket_raw)
    prior_outstanding = set(prior_ticket.get("request_set", {}).get("outstanding_request_item_ids", []))
    if prior_ticket.get("ticket_version") != "phase5-execution-ticket-v3" or prior_outstanding != {r["provider_request_item_id"] for r in rows}:
        raise RuntimeError("current v3 ticket does not match the exact recalibrated 16-item set")
    if prior_ticket.get("request_set", {}).get("completed_canary", {}).get("request_item_id") != CANARY:
        raise RuntimeError("predecessor ticket does not preserve the completed canary as historical")
    if len(eligible) != 13 or len(excluded) != 3:
        raise RuntimeError(f"audit-derived partition is {len(eligible)}/{len(excluded)}, not the expected mechanical 13/3")
    for row in eligible + excluded:
        source = row
        if source["body_sha256_verified"] != source["request_body_sha256"]:
            raise RuntimeError("provider-significant bytes are not unchanged")

    planned = {
        "verified_primary_audit_sha256": primary_sha,
        "verified_calibration_addendum_sha256": addendum_sha,
        "starting_actual_spend_aud": format(start["actual_spend_aud"], ".6f"),
        "starting_unresolved_reserved_aud": format(start["unresolved_reserved_aud"], ".6f"),
        "eligible": eligible, "excluded": excluded,
    }
    if not args.apply:
        print(json.dumps({"status": "READ_ONLY_PARTITION_READY", "provider_operations": 0,
                          "eligible_count": len(eligible), "excluded_count": len(excluded),
                          "starting_actual_spend_aud": planned["starting_actual_spend_aud"],
                          "starting_unresolved_reserved_aud": planned["starting_unresolved_reserved_aud"],
                          "excluded_ids_and_aud": [(r["provider_request_item_id"], format(r["corrected_hard_max_aud"], ".6f")) for r in excluded]}, sort_keys=True))
        return 0

    ticket_path = args.root / NEW_TICKET
    report_date = datetime.now(timezone.utc).date().isoformat()
    report_path = args.root / f"remainder-reduction-report-{report_date}.json"
    if ticket_path.exists() or report_path.exists() or report_path.with_name(report_path.name + ".sha256").exists():
        raise RuntimeError("append-only ticket or report destination already exists")

    timestamp = utc_now()
    replacements = _apply_partition(catalog, eligible, excluded, timestamp)
    final = _verify_final(catalog, eligible, excluded, rows_by_id, start)
    if replacements not in {0, len(eligible)}:
        raise RuntimeError("reservation replacement replay is only partially applied")

    eligible_ticket_rows = []
    for row in eligible:
        current = catalog.get_physical_attempt(row["physical"]["physical_attempt_id"])
        eligible_ticket_rows.append({
            "provider_request_item_id": row["provider_request_item_id"], "logical_task_id": row["logical_task_id"],
            "subject_id": row["subject_id"], "request_body_sha256": row["request_body_sha256"],
            "wire_fingerprint": row["wire_fingerprint"], "old_reservation_id": row["old_reservation_id"],
            "active_reservation_id": current["reservation_id"],
            "hard_max_usd": format(row["corrected_hard_max_usd"], ".6f"),
            "hard_max_aud": format(row["corrected_hard_max_aud"], ".6f"),
        })
    excluded_ticket_rows = []
    for row, result in zip(excluded, final["excluded_results"], strict=True):
        excluded_ticket_rows.append({
            "provider_request_item_id": row["provider_request_item_id"], "logical_task_id": row["logical_task_id"],
            "subject_id": row["subject_id"], "request_body_sha256": row["request_body_sha256"],
            "wire_fingerprint": row["wire_fingerprint"], "classification": "EXCLUDED_COST_CAP",
            "reason": "economic_authority_cap_exceeded", "hard_max_usd": format(row["corrected_hard_max_usd"], ".6f"),
            "hard_max_aud": format(row["corrected_hard_max_aud"], ".6f"),
            "provider_crossings": 0, "provider_request_id": None, "provider_receipt_id": None,
            "usage": None, "actual_aud": "0", "builder_reservation_status": "released",
            "mandate_reservation_status": "settled",
        })
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ticket_kwargs = {
        "predecessor_path": prior_ticket_path, "predecessor_bytes": prior_ticket_raw,
        "builder_commit": head, "preparation_bytes": prep_raw, "jsonl_bytes": jsonl_raw,
        "eligible_requests": eligible_ticket_rows, "excluded_requests": excluded_ticket_rows,
        "mandate_id": MANDATE, "per_request_cap_aud": "0.25",
    }
    ticket, _ = create_cost_cap_remainder_ticket(ticket_path=ticket_path, **ticket_kwargs)
    ticket_raw = ticket_path.read_bytes()
    validate_cost_cap_remainder_ticket(ticket_path=ticket_path, **ticket_kwargs)

    certificates = []
    for row in eligible:
        cert_row = _execution_row(catalog, row, row["corrected_hard_max_usd"], row["corrected_hard_max_aud"])
        if Decimal(cert_row["hard_max_aud"]) > CAP:
            raise RuntimeError("eligible certification row exceeds the active per-request cap")
        certificate = certify_standard_execution_row(catalog, cert_row, mandate_id=MANDATE)
        evaluation = evaluate_execution_against_mandate(
            catalog, MANDATE,
            {**cert_row, "contract_identity_hash": cert_row.get("contract_identity_hash")},
        )
        if not evaluation.authorized or certificate["status"] != "READY_TO_CROSS_PROVIDER_BOUNDARY":
            raise RuntimeError(f"eligible request did not certify under Amendment 3: {row['provider_request_item_id']}")
        certificates.append(certificate)
    if len(certificates) != len(eligible):
        raise RuntimeError("eligible exact-row certification count mismatch")
    for row in excluded:
        cert_row = _execution_row(catalog, row, row["corrected_hard_max_usd"], row["corrected_hard_max_aud"])
        try:
            certify_standard_execution_row(catalog, cert_row, mandate_id=MANDATE)
        except ValueError:
            continue
        raise RuntimeError(f"excluded request unexpectedly passed exact-row certification: {row['provider_request_item_id']}")
    final = _verify_final(catalog, eligible, excluded, rows_by_id, start)
    report_sha_path = report_path.with_name(report_path.name + ".sha256")
    report = {
        "report_version": "phase5-v1.2-remainder-cost-cap-reduction-v1",
        "recorded_at_utc": timestamp, "status": "PHASE5_V1_2_REMAINDER_REDUCED_AND_RECERTIFIED",
        "provider_operations": 0, "amendment4_active": False, "merge": 0,
        "builder_commit": head,
        "verified_audit_inputs": {PRIMARY_AUDIT: primary_sha, CALIBRATION_ADDENDUM: addendum_sha},
        "starting_actual_spend_aud": format(start["actual_spend_aud"], ".6f"),
        "final_actual_spend_aud": format(final["actual_spend_aud"], ".6f"),
        "starting_unresolved_reserved_aud": format(start["unresolved_reserved_aud"], ".6f"),
        "final_unresolved_reserved_aud": format(final["unresolved_reserved_aud"], ".6f"),
        "eligible_count": len(eligible), "excluded_count": len(excluded),
        "eligible_aggregate_hard_aud": format(final["eligible_hard_aud"], ".6f"),
        "eligible_aggregate_hard_usd": format(final["eligible_hard_usd"], ".6f"),
        "maximum_eligible_hard_aud": format(final["maximum_eligible_hard_aud"], ".6f"),
        "assumed_available_provider_credit_usd": "12.00",
        "provider_credit_comparison": {"is_above_eligible_hard_usd": Decimal("12.00") > final["eligible_hard_usd"],
                                       "headroom_usd": format(Decimal("12.00") - final["eligible_hard_usd"], ".6f"),
                                       "queried_or_spent": False},
        "reservation_replacements": replacements,
        "historical_canary": {"request_item_id": CANARY, "reservation_id": start["canary_reservation_id"],
                              "actual_spend_aud": format(start["canary_actual_aud"], ".6f"),
                              "actual_spend_usd": format(start["canary_actual_usd"], ".6f"),
                              "unchanged": True, "provider_crossings": 1},
        "eligible_requests": [{"provider_request_item_id": r["provider_request_item_id"], "subject_id": r["subject_id"],
                               "old_reservation_id": r["old_reservation_id"], "active_reservation_id": r["new_reservation_id"],
                               "corrected_hard_max_usd": format(r["corrected_hard_max_usd"], ".6f"),
                               "corrected_hard_max_aud": format(r["corrected_hard_max_aud"], ".6f"),
                               "margin_to_cap_aud": format(CAP-r["corrected_hard_max_aud"], ".6f"),
                               "provider_crossings": 0} for r in eligible],
        "excluded_requests": final["excluded_results"],
        "provider_significant_bytes": {"preparation_sha256": sha256(prep_raw), "requests_jsonl_sha256": sha256(jsonl_raw),
                                       "all_16_body_hashes_unchanged": all(r["body_sha256_verified"] == r["request_body_sha256"] for r in rows)},
        "execution_ticket": {"path": str(ticket_path), "sha256": sha256(ticket_raw),
                             "predecessor_path": str(prior_ticket_path), "predecessor_sha256": sha256(prior_ticket_raw),
                             "eligible_member_count": ticket["request_set"]["count"],
                             "excluded_member_count": len(ticket["request_set"]["excluded_cost_cap_requests"])},
        "certification": {"status": f"{len(certificates)}/{len(eligible)} READY_TO_CROSS_PROVIDER_BOUNDARY",
                          "certified_ids": [x["provider_request_item_id"] for x in certificates],
                          "excluded_certification_refused": len(excluded)},
        "postconditions": {"active_reservations_exactly_eligible": True, "excluded_unresolved_exposure_zero": True,
                           "amendment3_aggregate_respected": True, "all_eligible_within_cap": True,
                           "excluded_requests_terminal_and_nonexecutable": True,
                           "semantic_failures_added": 0, "fallbacks": [], "automatic_retries": 0,
                           "semantic_retries": 0},
    }
    report_raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if report_path.exists() or report_sha_path.exists():
        raise RuntimeError("append-only final report path already exists")
    digest = sha256(report_raw)
    with report_path.open("xb") as stream:
        stream.write(report_raw)
        stream.flush()
    report_sha_path.write_text(f"{digest}  {report_path.name}\n", encoding="ascii")
    print(json.dumps({"status": report["status"], "report_path": str(report_path), "report_sha256": digest,
                      "ticket_path": str(ticket_path), "ticket_sha256": sha256(ticket_raw),
                      "certification": report["certification"]["status"], "provider_operations": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
