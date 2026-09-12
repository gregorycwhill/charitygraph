"""Execute only the 17 surviving, already-prepared V1.2 rows under Amendment 3.

This continuation deliberately does not activate a mandate, prepare tasks,
create reservations, or replace the abandoned zero-crossing canary.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "src"), str(Path(__file__).resolve().parent)]

from charitygraph.phase5_execution_mandate import evaluate_execution_against_mandate
from charitygraph.phase5_pre_send_certification import certify_standard_execution_row
from charitygraph.phase5_execution_tickets import sha256, validate_superseding_ticket
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient, StandardCampaignCoordinator
from charitygraph.runtime import SQLiteCatalog

base = importlib.import_module("run_phase5_direct_service_v12_campaign")
rebind = importlib.import_module("run_phase5_direct_service_v12_amendment4_campaign")

MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-3"
RUN = "run:phase5-direct-service-v1.2-cutover"
JOB = "deliveryjob:phase5-direct-service-v1.2-standard"
FAILED_CANARY = "requestitem:1c01caaa10b645ed8db98e4acf57b0366807d5be121d7bb2325a3617c9f9cfb3"
PREP_SHA = "69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26"
JSONL_SHA = "35e1ad5ecbca107566a00010d59d4566ece4be2198f49c42a3cb61e2dc2a3f0a"
OLD_TICKET_SHA = "23deB843495F2B27D6257D94C7FD03329606F2102F27C9EA4FD13AA369FDAEF3".lower()
SUPERSESSION_REASON = "Append-only executor/control-plane pin after exact-row certification; preserves V1.2 material and excludes only the terminal zero-crossing pre-send canary."
ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")
DB = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
OLD_TICKET = ROOT / "future-execution-ticket.json"
CURRENT_TICKET = ROOT / "future-execution-ticket-v2.json"
PROPOSAL = Path("proposals/phase5-direct-service-v1.2-amendment-3.json")
PROPOSAL_SHA = "255ee36010083f78d8bd7a08eba684d053a35e34193da1c6ca80672b49c9f42e"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def select_surviving_rows(rows: list[dict]) -> list[dict]:
    """Keep original manifest order while excluding only the spent local canary."""
    ids = [row.get("provider_request_item_id") for row in rows]
    if len(ids) != 18 or len(set(ids)) != 18 or FAILED_CANARY not in ids:
        raise RuntimeError("expected the exact 18-item V1.2 manifest including the abandoned canary")
    return [row for row in rows if row["provider_request_item_id"] != FAILED_CANARY]


def canary_requires_campaign_stop(result: dict) -> bool:
    """Stop only for systemic, ambiguous, pre-send, or lifecycle-integrity outcomes."""
    statuses = {row.get("status") for row in result.get("results", [])}
    return bool(result.get("stop_campaign") or statuses.intersection({
        "failed_pre_send", "ambiguous", "completed_accounting_failed",
    }))


def load_campaign_assets(root: Path) -> tuple[dict, list[dict], bytes, bytes, bytes]:
    prep_raw = (root / "preparation.json").read_bytes()
    jsonl_raw = (root / "requests.jsonl").read_bytes()
    old_ticket_path = root / "future-execution-ticket.json"
    old_ticket_raw = old_ticket_path.read_bytes()
    proposal_raw = PROPOSAL.read_bytes()
    if (sha(prep_raw) != PREP_SHA or sha(jsonl_raw) != JSONL_SHA
            or sha(old_ticket_raw) != OLD_TICKET_SHA or sha(proposal_raw) != PROPOSAL_SHA):
        raise RuntimeError("immutable V1.2 preparation, JSONL, predecessor ticket, or proposal hash mismatch")
    old_ticket = json.loads(old_ticket_raw.decode("utf-8"))
    manifest = json.loads(prep_raw.decode("utf-8"))
    rows = manifest.get("request_items", [])
    if len(rows) != 18 or len({x.get("provider_request_item_id") for x in rows}) != 18:
        raise RuntimeError("V1.2 manifest is not the exact 18-item historical preparation")
    if (old_ticket.get("preparation_manifest_sha256") != PREP_SHA
            or old_ticket.get("jsonl_sha256") != JSONL_SHA
            or old_ticket.get("builder_commit_required") != "ef82e0438e05533fbc3f62819c987f9989e7d8bc"):
        raise RuntimeError("historical ticket identity differs from the recorded predecessor")
    if (manifest.get("model") != old_ticket.get("model")
            or manifest.get("reasoning_effort") != old_ticket.get("reasoning_effort")
            or manifest.get("delivery_mode") != old_ticket.get("delivery_mode")
            or manifest.get("max_output_tokens") != old_ticket.get("max_output_tokens")
            or manifest.get("mandate_id_required") != old_ticket.get("mandate_id_required")):
        raise RuntimeError("V1.2 route or mandate differs from the historical ticket")
    return manifest, rows, prep_raw, jsonl_raw, old_ticket_raw


def preflight(catalog: SQLiteCatalog, root: Path = ROOT, *, require_ticket: bool = True) -> tuple[list[dict], dict]:
    if not catalog.path.is_file():
        raise RuntimeError("expected-existing authoritative catalogue is missing")
    manifest, source_rows, prep_raw, jsonl_raw, old_ticket_raw = load_campaign_assets(root)
    lines = [json.loads(line) for line in jsonl_raw.decode("utf-8", errors="strict").splitlines() if line]
    expected = {row["provider_request_item_id"]: row for row in source_rows}
    actual = {line.get("custom_id"): line for line in lines}
    if len(lines) != 18 or set(actual) != set(expected):
        raise RuntimeError("JSONL custom-ID set differs from the immutable 18-item manifest")
    for rid, row in expected.items():
        if actual[rid].get("body") != row["request_body"]:
            raise RuntimeError(f"JSONL provider body changed: {rid}")

    mandate = catalog.get_execution_mandate(MANDATE)
    if mandate is None or mandate["status"] != "active":
        raise RuntimeError("Amendment 3 is not active")
    if Decimal(mandate["actual_spend_aud"]) < 0 or Decimal(mandate["unresolved_reserved_aud"]) < 0:
        raise RuntimeError("Amendment-3 accounting contains a negative balance")
    if catalog.get_execution_mandate("mandate:phase5-build-standard-luna-v1-amendment-4") is not None:
        raise RuntimeError("Amendment 4 unexpectedly exists")

    durable = {row["provider_request_item_id"]: row for row in catalog.list_provider_request_items(RUN)}
    if len(durable) != 18 or set(durable) != set(expected):
        raise RuntimeError("durable V1.2 item set differs from the immutable manifest")
    if durable[FAILED_CANARY]["status"] != "failed":
        raise RuntimeError("abandoned zero-crossing canary is not still terminally failed")
    failed_attempts = catalog.list_provider_request_attempts(provider_request_item_id=FAILED_CANARY)
    failed_physical = catalog.get_physical_attempt(durable[FAILED_CANARY]["physical_attempt_id"])
    if (len(failed_attempts) != 1 or failed_attempts[0]["failure_class"] != "pre_send_validation"
            or failed_attempts[0]["provider_request_id"] or failed_attempts[0]["provider_receipt_id"]
            or failed_attempts[0]["usage_json"] or failed_attempts[0]["submitted_at"]
            or failed_physical["send_started_at"]):
        raise RuntimeError("abandoned canary no longer proves zero provider crossings")
    with catalog._authorization_connection() as conn:
        failed_budget = conn.execute("SELECT status FROM budget_reservations WHERE reservation_id=?", (failed_physical["reservation_id"],)).fetchone()
        failed_mandate_reservation = conn.execute(
            "SELECT status,actual_aud FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?",
            (MANDATE, failed_physical["reservation_id"]),
        ).fetchone()
        old_v11 = conn.execute(
            "SELECT i.provider_request_item_id,i.status,a.failure_class,a.failure_message_redacted FROM provider_request_items i "
            "LEFT JOIN provider_request_attempts a ON a.provider_request_item_id=i.provider_request_item_id "
            "WHERE i.run_id='run:phase5-direct-service-v1.1-post-acquisition'"
        ).fetchall()
        current_costs = conn.execute(
            "SELECT reservation_id,entry_type FROM cost_entries WHERE run_id=?", (RUN,)
        ).fetchall()
        active_phase5 = conn.execute(
            "SELECT count(*) FROM execution_mandates WHERE phase_scope='phase5-build-calibration' AND status='active'"
        ).fetchone()[0]
        receipts = conn.execute(
            "SELECT count(*) FROM provider_receipts WHERE physical_attempt_id IN "
            "(SELECT physical_attempt_id FROM physical_attempts WHERE run_id=?)", (RUN,),
        ).fetchone()[0]
    if failed_budget is None or failed_budget["status"] != "released":
        raise RuntimeError("abandoned canary Builder reservation is not released")
    if (failed_mandate_reservation is None or failed_mandate_reservation["status"] != "settled"
            or Decimal(failed_mandate_reservation["actual_aud"]) != 0):
        raise RuntimeError("abandoned canary Amendment-3 reservation is not settled at zero")
    exclusion_evidence = {
        "request_item_id": FAILED_CANARY, "request_status": durable[FAILED_CANARY]["status"],
        "physical_status": failed_physical["status"], "failure_class": failed_attempts[0]["failure_class"],
        "send_started": bool(failed_physical["send_started_at"]), "provider_crossings": 0,
        "provider_request_id": failed_attempts[0]["provider_request_id"],
        "provider_receipt_id": failed_attempts[0]["provider_receipt_id"], "usage": None,
        "builder_reservation_status": failed_budget["status"],
        "mandate_reservation_status": failed_mandate_reservation["status"],
        "actual_aud": failed_mandate_reservation["actual_aud"],
    }
    if sum(row["status"] == "completed" for row in old_v11) != 42:
        raise RuntimeError("historical V1.1 completed request population differs from 42")
    if sum(row["failure_class"] == "systemic_provider" and "429" in (row["failure_message_redacted"] or "") for row in old_v11) != 1:
        raise RuntimeError("historical V1.1 terminal 429 is missing or changed")
    if set(expected).intersection(row["provider_request_item_id"] for row in old_v11):
        raise RuntimeError("V1.2 continuation overlaps historical V1.1 request identities")
    if any(row["entry_type"] != "reservation_release" for row in current_costs):
        raise RuntimeError("V1.2 execution already has an unexpected actual-cost ledger entry")
    if active_phase5 != 1 or receipts != 0:
        raise RuntimeError("unexpected active Phase-5 mandate or V1.2 provider receipt already exists")

    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ticket_sha = None
    if require_ticket:
        ticket = validate_superseding_ticket(
            ticket_path=root / "future-execution-ticket-v2.json", predecessor_path=root / "future-execution-ticket.json",
            builder_commit=current_head, preparation_bytes=prep_raw, jsonl_bytes=jsonl_raw,
            excluded_request_id=FAILED_CANARY, exclusion_evidence=exclusion_evidence,
            supersession_reason=SUPERSESSION_REASON,
        )
        ticket_sha = sha256((root / "future-execution-ticket-v2.json").read_bytes())
        if ticket["mandate_id_required"] != MANDATE:
            raise RuntimeError("superseding ticket is not bound to the active Amendment-3 authority")

    rows = rebind.build_rows(catalog, source_rows)
    survivors = select_surviving_rows(rows)
    if len(survivors) != 17:
        raise RuntimeError("surviving set is not exactly 17")
    certificates = []
    evaluations = []
    active_ids = set()
    for row in survivors:
        certificate = certify_standard_execution_row(catalog, row, mandate_id=MANDATE)
        evaluation = evaluate_execution_against_mandate(
            catalog, MANDATE,
            {**row, "provider": "openai", "logical_task_id": row["logical_task_id"],
             "contract_identity_hash": row.get("contract_identity_hash", row.get("semantic_contract_hash"))},
        )
        if not evaluation.authorized:
            raise RuntimeError(f"mandate rejected {row['provider_request_item_id']}: {evaluation.decision}")
        certificates.append(certificate)
        evaluations.append(evaluation)
        active_ids.add(row["mandate_reservation_id"])
    if len(certificates) != 17 or any(c["status"] != "READY_TO_CROSS_PROVIDER_BOUNDARY" for c in certificates):
        raise RuntimeError("not all surviving requests certified")
    with catalog._authorization_connection() as conn:
        reservations = conn.execute(
            "SELECT reservation_id,reserved_aud,status FROM execution_mandate_reservations WHERE mandate_id=? AND status='active'",
            (MANDATE,),
        ).fetchall()
    if {r["reservation_id"] for r in reservations} != active_ids:
        raise RuntimeError("Amendment-3 active reservations do not match the exact surviving set")
    exposure = sum((Decimal(r["reserved_aud"]) for r in reservations), Decimal("0"))
    if exposure != Decimal(mandate["unresolved_reserved_aud"]):
        raise RuntimeError("active reservation sum differs from Amendment-3 unresolved exposure")
    for rid in active_ids:
        physical = next(row for row in survivors if row["mandate_reservation_id"] == rid)
        attempts = catalog.list_provider_request_attempts(provider_request_item_id=physical["provider_request_item_id"])
        item = catalog.get_provider_request_item(physical["provider_request_item_id"])
        phys = catalog.get_physical_attempt(physical["physical_attempt_id"])
        if (item["status"] != "prepared" or phys["status"] != "prepared" or len(attempts) != 1
                or attempts[0]["status"] != "prepared" or attempts[0]["authorization_id"] != MANDATE
                or attempts[0]["provider_request_id"] or attempts[0]["provider_receipt_id"]
                or attempts[0]["usage_json"] or attempts[0]["submitted_at"] or phys["send_started_at"]):
            raise RuntimeError(f"survivor lifecycle is not clean/prepared: {physical['provider_request_item_id']}")
        with catalog._authorization_connection() as conn:
            budget = conn.execute("SELECT status,reserved_aud FROM budget_reservations WHERE reservation_id=?", (rid,)).fetchone()
        if budget is None or budget["status"] != "active" or Decimal(budget["reserved_aud"]) != Decimal(physical["hard_max_aud"]):
            raise RuntimeError(f"survivor Builder reservation differs from its pinned hard exposure: {physical['provider_request_item_id']}")
    return survivors, {
        "status": "17/17_READY_TO_CROSS_PROVIDER_BOUNDARY",
        "preparation_manifest_sha256": PREP_SHA,
        "jsonl_sha256": JSONL_SHA,
        "amendment3_actual_spend_aud": mandate["actual_spend_aud"],
        "amendment3_reserved_aud": str(exposure),
        "remaining_authority_aud": str(Decimal(mandate["aggregate_hard_aud"]) - Decimal(mandate["actual_spend_aud"]) - exposure),
        "certified_count": len(certificates),
        "abandoned_canary_reservation": "released_and_settled_zero",
        "historical_v11_completed_excluded": 42,
        "historical_v11_terminal_429_excluded": 1,
        "builder_commit": current_head,
        "current_ticket_sha256": ticket_sha,
        "excluded_canary_evidence": exclusion_evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--catalogue", type=Path, default=DB)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.preflight_only == args.execute:
        raise SystemExit("choose exactly one of --preflight-only or --execute")
    if not args.catalogue.is_file():
        raise SystemExit("expected-existing catalogue is missing")
    catalog = SQLiteCatalog(args.catalogue, authorization_path=args.catalogue).open()
    rows, evidence = preflight(catalog, args.root)
    if args.preflight_only:
        print(json.dumps(evidence, sort_keys=True))
        return 0

    # Preserve original manifest order after excluding only the proven local
    # pre-send failure. The first remaining item is the live-schema canary.
    canary, remainder = rows[0], rows[1:]
    timestamp = datetime.now(timezone.utc).isoformat()
    base.MANDATE = MANDATE
    base.OWNER = "phase5-direct-service-v1-2-amendment3-worker"
    parsed: dict = {}
    def evaluator(row):
        # Repeat exact-row certification at the immediate pre-send boundary,
        # then evaluate current aggregate authority/reservation state.
        certify_standard_execution_row(catalog, row, mandate_id=MANDATE)
        return evaluate_execution_against_mandate(
            catalog, MANDATE,
            {**row, "provider": "openai", "logical_task_id": row["logical_task_id"],
             "contract_identity_hash": row.get("contract_identity_hash", row.get("semantic_contract_hash"))},
        )
    validator = lambda body: base.DirectServiceWireOutput.model_validate_json(base.output_text(body))
    callback = lambda row, response, usage: base.reconcile(catalog, row, response, args.root, timestamp, parsed)
    provider = OpenAIHTTPStandardClient()
    first = StandardCampaignCoordinator(
        catalog=catalog, provider=provider, runtime_root=args.root, max_concurrency=1,
        now=timestamp, validator=validator, on_reconciled=callback, mandate_evaluator=evaluator,
    ).run([canary])
    # A returned completed Responses body proves request/schema acceptance even
    # if local semantic parsing fails; accounting/lifecycle errors still stop.
    # Definite item-level provider rejection is terminal for that item but
    # does not invalidate the independently pinned remaining requests.
    # Ambiguous, pre-send/lifecycle, accounting, and systemic failures stop.
    if canary_requires_campaign_stop(first):
        report = {"status": "canary_not_accepted", "canary": first, "remaining_unattempted": 16,
                  "preflight": evidence, "provider_operations": first.get("provider_posts", 0)}
        _write_report(args.root, report)
        print(json.dumps(report, sort_keys=True))
        return 2

    remainder_result = StandardCampaignCoordinator(
        catalog=catalog, provider=provider, runtime_root=args.root, max_concurrency=4,
        now=timestamp, validator=validator, on_reconciled=callback, mandate_evaluator=evaluator,
    ).run(remainder)
    report = {
        "status": "PHASE5_DIRECT_SERVICE_V1_2_REMAINDER_EXECUTED",
        "preflight": evidence, "canary": first, "remainder": remainder_result,
        "candidate_results": parsed,
        "provider_operations": first.get("provider_posts", 0) + remainder_result.get("provider_posts", 0),
        "automatic_retries": 0, "semantic_retries": 0, "fallbacks": [],
        "source_acquisitions": 0, "governed_promotions": 0,
    }
    _write_report(args.root, report)
    print(json.dumps(report, sort_keys=True))
    return 0


def _write_report(root: Path, report: dict) -> None:
    encoded = (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path = root / "amendment3-remainder-execution-report.json"
    if path.exists() and path.read_bytes() != encoded:
        raise RuntimeError("append-only Amendment-3 remainder report conflicts with existing report")
    if not path.exists():
        path.write_bytes(encoded)
    (root / "amendment3-remainder-execution-report.sha256").write_text(sha(path.read_bytes()) + "\n", encoding="ascii")


if __name__ == "__main__":
    raise SystemExit(main())
