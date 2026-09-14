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
from charitygraph.phase5_execution_tickets import sha256, validate_completed_canary_ticket
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient, StandardCampaignCoordinator, StandardProviderResponse
from charitygraph.runtime import SQLiteCatalog

base = importlib.import_module("run_phase5_direct_service_v12_campaign")
rebind = importlib.import_module("run_phase5_direct_service_v12_amendment4_campaign")

MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-3"
RUN = "run:phase5-direct-service-v1.2-cutover"
JOB = "deliveryjob:phase5-direct-service-v1.2-standard"
FAILED_CANARY = "requestitem:1c01caaa10b645ed8db98e4acf57b0366807d5be121d7bb2325a3617c9f9cfb3"
LIVE_CANARY = "requestitem:eae9e3086c6f35ac6621de83d59e36310ade18e2c51e3a3c4aece1dbb9e7e987"
PREP_SHA = "69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26"
JSONL_SHA = "35e1ad5ecbca107566a00010d59d4566ece4be2198f49c42a3cb61e2dc2a3f0a"
OLD_TICKET_SHA = "23deB843495F2B27D6257D94C7FD03329606F2102F27C9EA4FD13AA369FDAEF3".lower()
V2_TICKET_SHA = "44033ad6f43f3c365df9414904e1bb23324f7b28f041967efe6b4c1f1ea5e65c"
SUPERSESSION_REASON = "Append-only executor/control-plane pin after exact-row certification; preserves V1.2 material and excludes only the terminal zero-crossing pre-send canary."
ROOT = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1")
DB = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
OLD_TICKET = ROOT / "future-execution-ticket.json"
V2_TICKET = ROOT / "future-execution-ticket-v2.json"
CURRENT_TICKET = ROOT / "future-execution-ticket-v3.json"
PROPOSAL = Path("proposals/phase5-direct-service-v1.2-amendment-3.json")
PROPOSAL_SHA = "255ee36010083f78d8bd7a08eba684d053a35e34193da1c6ca80672b49c9f42e"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def response_metadata_path(raw_path: Path) -> Path:
    """Match the transport's append-only ``<response>.meta.json`` name."""
    return raw_path.with_suffix(".meta.json")


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


def corrected_canary_interpretation(root: Path, evidence: dict) -> bytes:
    legacy_path = root / "candidate-results" / f"{LIVE_CANARY.replace(':', '_')}.json"
    if not legacy_path.is_file():
        raise RuntimeError("original legacy-parser canary interpretation is missing")
    legacy_raw = legacy_path.read_bytes()
    report = {
        "report_type": "phase5_direct_service_v12_append_only_canary_parser_correction",
        "request_item_id": LIVE_CANARY,
        "provider_request_id": evidence["provider_request_id"],
        "responses_id": evidence["responses_id"],
        "raw_response_sha256": evidence["raw_response_sha256"],
        "preserved_prior_interpretation": {
            "path": str(legacy_path), "sha256": sha(legacy_raw),
            "status": "legacy_dto_parser_misclassification_preserved_unchanged",
        },
        "corrected_v12_interpretation": {
            "status": evidence["corrected_interpretation"],
            "section_counts": evidence["section_counts"],
            "proposal_count": evidence["proposal_count"],
            "relationship_count": evidence["relationship_count"],
            "exact_evidence_validation": evidence["exact_evidence_validation"],
        },
        "provider_operations": 0, "governed_promotions": 0,
    }
    return (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def completed_canary_evidence(catalog: SQLiteCatalog, row: dict, root: Path) -> dict:
    """Prove the already-crossed live canary and its append-only accounting state."""
    if row["provider_request_item_id"] != LIVE_CANARY:
        raise RuntimeError("unexpected request supplied as the completed live canary")
    item = catalog.get_provider_request_item(LIVE_CANARY)
    attempts = catalog.list_provider_request_attempts(provider_request_item_id=LIVE_CANARY)
    physical = catalog.get_physical_attempt(row["physical_attempt_id"])
    if (item is None or item["status"] != "completed" or len(attempts) != 1
            or attempts[0]["status"] != "completed" or not attempts[0]["submitted_at"]
            or not attempts[0]["provider_request_id"] or not attempts[0]["provider_receipt_id"]
            or not attempts[0]["usage_json"] or not physical["send_started_at"]
            or not physical["receipt_persisted_at"]):
        raise RuntimeError("live canary is not exactly one completed provider event")
    raw_path = root / "standard-results" / f"{LIVE_CANARY.replace(':', '_')}.json"
    meta_path = response_metadata_path(raw_path)
    if not raw_path.is_file() or not meta_path.is_file():
        raise RuntimeError("live canary response bytes or metadata are missing")
    raw = raw_path.read_bytes()
    body = json.loads(raw.decode("utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (body.get("status") != "completed" or not isinstance(body.get("id"), str)
            or not 200 <= int(meta.get("status_code", 0)) < 300
            or meta.get("request_id") != attempts[0]["provider_request_id"]
            or body.get("usage") != json.loads(attempts[0]["usage_json"])
            or item.get("result_ref") != "standard-result:" + sha(raw)
            or attempts[0].get("result_ref") != item.get("result_ref")
            or item.get("provider_receipt_id") != "standard-receipt:" + hashlib.sha256(
                (LIVE_CANARY + ":" + body["id"]).encode()
            ).hexdigest()):
        raise RuntimeError("live canary response differs from durable request/receipt/usage identity")
    wire, domain = base.parse_v12_response(body, row)
    usage = body.get("usage") or {}
    usd = ((Decimal(str(usage.get("input_tokens", 0))) * Decimal("1.60")
            + Decimal(str(usage.get("output_tokens", 0))) * Decimal("5.00"))
           / Decimal(1_000_000)).quantize(Decimal("0.000001"))
    aud = (usd * Decimal("1.52")).quantize(Decimal("0.000001"))
    if aud > Decimal("0.25"):
        raise RuntimeError("live canary actual exceeds AUD 0.25 per-request authority")
    with catalog._authorization_connection() as conn:
        actuals = conn.execute(
            "SELECT entry_key,provider_amount,aud_amount,usage_json FROM cost_entries WHERE reservation_id=? AND entry_type='actual'",
            (row["reservation_id"],),
        ).fetchall()
        budget = conn.execute("SELECT status,reserved_aud FROM budget_reservations WHERE reservation_id=?", (row["reservation_id"],)).fetchone()
        mandate_reservation = conn.execute(
            "SELECT status,actual_aud FROM execution_mandate_reservations WHERE mandate_id=? AND reservation_id=?",
            (MANDATE, row["mandate_reservation_id"]),
        ).fetchone()
        task_attempts = conn.execute("SELECT status,error_class FROM task_attempts WHERE task_run_id=?", (row["physical_attempt_id"],)).fetchall()
    ledger_usage = base.provider_usage_for_cost_ledger(usage)
    if (len(actuals) != 1 or actuals[0]["entry_key"] != "actual:" + row["physical_attempt_id"]
            or Decimal(actuals[0]["provider_amount"]) != usd or Decimal(actuals[0]["aud_amount"]) != aud
            or json.loads(actuals[0]["usage_json"]) != ledger_usage
            or budget is None or budget["status"] != "consumed"
            or usd <= Decimal(budget["reserved_aud"])
            or catalog.reservation_position(row["reservation_id"])["outstanding"] != 0
            or mandate_reservation is None or mandate_reservation["status"] != "settled"
            or Decimal(mandate_reservation["actual_aud"]) != aud):
        raise RuntimeError("live canary actual cost or reservation settlement is not reconciled exactly")
    section_counts = {
        "participation": len(wire.participation),
        "capability_access_availability": len(wire.capability_access_availability),
        "scheme_accreditation": len(wire.scheme_accreditation),
        "relationships": len(wire.relationships),
    }
    if task_attempts and not all(a["status"] == "failed_terminal" and a["error_class"] == "output_validation" for a in task_attempts):
        raise RuntimeError("original local task-validation history differs from the preserved parser failure")
    evidence = {
        "request_item_id": LIVE_CANARY, "request_status": item["status"],
        "delivery_attempt_status": attempts[0]["status"], "physical_status": physical["status"],
        "provider_crossings": 1, "provider_request_id": attempts[0]["provider_request_id"],
        "provider_receipt_id": attempts[0]["provider_receipt_id"], "responses_id": body["id"],
        "raw_response_sha256": sha(raw), "request_body_sha256": row["request_body_sha256"],
        "usage": usage, "actual_usd": format(usd, ".6f"), "actual_aud": format(aud, ".6f"),
        "builder_reservation_status": budget["status"],
        "mandate_reservation_status": mandate_reservation["status"],
        "mandate_actual_aud": mandate_reservation["actual_aud"],
        "original_local_task_attempts": [dict(a) for a in task_attempts],
        "corrected_interpretation": "directly_valid_v12_wire_and_domain",
        "section_counts": section_counts, "proposal_count": len(domain.propositions),
        "relationship_count": len(domain.relationships),
        "exact_evidence_validation": "valid",
        "provider_operations_during_reconciliation": 0,
    }
    evidence["corrected_interpretation_report_sha256"] = sha(corrected_canary_interpretation(root, evidence))
    return evidence


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
    if active_phase5 != 1:
        raise RuntimeError("unexpected active Phase-5 mandate")

    rows = rebind.build_rows(catalog, source_rows)
    survivors = select_surviving_rows(rows)
    if len(survivors) != 17:
        raise RuntimeError("surviving set is not exactly 17")
    survivor_by_id = {row["provider_request_item_id"]: row for row in survivors}
    canary_evidence = completed_canary_evidence(catalog, survivor_by_id[LIVE_CANARY], root)
    canary_reservation = survivor_by_id[LIVE_CANARY]["reservation_id"]
    if (receipts != 1 or sum(row["entry_type"] == "actual" and row["reservation_id"] == canary_reservation for row in current_costs) != 1
            or any(row["entry_type"] not in {"reservation_release", "actual"} for row in current_costs)
            or any(row["entry_type"] == "actual" and row["reservation_id"] != canary_reservation for row in current_costs)):
        raise RuntimeError("V1.2 provider receipt/cost rows differ from the one completed canary")

    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ticket_sha = None
    if require_ticket:
        ticket = validate_completed_canary_ticket(
            ticket_path=root / "future-execution-ticket-v3.json", predecessor_path=root / "future-execution-ticket-v2.json",
            predecessor_sha256=V2_TICKET_SHA, builder_commit=current_head,
            preparation_bytes=prep_raw, jsonl_bytes=jsonl_raw,
            completed_canary=canary_evidence,
        )
        ticket_sha = sha256((root / "future-execution-ticket-v3.json").read_bytes())
        if ticket["mandate_id_required"] != MANDATE:
            raise RuntimeError("current ticket is not bound to the active Amendment-3 authority")

    executable_rows = [row for row in survivors if row["provider_request_item_id"] != LIVE_CANARY]
    if len(executable_rows) != 16:
        raise RuntimeError("remaining executable set is not exactly 16")
    certificates = []
    evaluations = []
    active_ids = set()
    for row in executable_rows:
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
    if len(certificates) != 16 or any(c["status"] != "READY_TO_CROSS_PROVIDER_BOUNDARY" for c in certificates):
        raise RuntimeError("not all remaining requests certified")
    with catalog._authorization_connection() as conn:
        reservations = conn.execute(
            "SELECT reservation_id,reserved_aud,status FROM execution_mandate_reservations WHERE mandate_id=? AND status='active'",
            (MANDATE,),
        ).fetchall()
    if {r["reservation_id"] for r in reservations} != active_ids:
        raise RuntimeError("Amendment-3 active reservations do not match the exact remaining 16-item set")
    exposure = sum((Decimal(r["reserved_aud"]) for r in reservations), Decimal("0"))
    if exposure != Decimal(mandate["unresolved_reserved_aud"]):
        raise RuntimeError("active reservation sum differs from Amendment-3 unresolved exposure")
    for rid in active_ids:
        physical = next(row for row in executable_rows if row["mandate_reservation_id"] == rid)
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
        "status": "CANARY_RECONCILED;16/16_READY_TO_CROSS_PROVIDER_BOUNDARY",
        "preparation_manifest_sha256": PREP_SHA,
        "jsonl_sha256": JSONL_SHA,
        "amendment3_actual_spend_aud": mandate["actual_spend_aud"],
        "amendment3_reserved_aud": str(exposure),
        "remaining_authority_aud": str(Decimal(mandate["aggregate_hard_aud"]) - Decimal(mandate["actual_spend_aud"]) - exposure),
        "surviving_authorized_count": 17,
        "completed_canary_count": 1,
        "certified_count": len(certificates),
        "abandoned_canary_reservation": "released_and_settled_zero",
        "historical_v11_completed_excluded": 42,
        "historical_v11_terminal_429_excluded": 1,
        "builder_commit": current_head,
        "current_ticket_sha256": ticket_sha,
        "excluded_canary_evidence": exclusion_evidence,
        "completed_canary_evidence": canary_evidence,
    }


def reconcile_completed_canary_without_provider(catalog: SQLiteCatalog, root: Path) -> dict:
    """Replay retained response validation and verify settled accounting idempotently.

    The original local task attempt is terminally failed by the legacy DTO
    parser. Reopening it would falsify history, so replay uses the normal
    deterministic reconciliation callback against its stable ledger key and
    verifies that the settled totals and terminal task history do not change.
    """
    manifest, source_rows, prep_raw, jsonl_raw, _ = load_campaign_assets(root)
    lines = [json.loads(line) for line in jsonl_raw.decode("utf-8", errors="strict").splitlines() if line]
    if sha(prep_raw) != PREP_SHA or sha(jsonl_raw) != JSONL_SHA or len(lines) != 18:
        raise RuntimeError("immutable campaign inputs failed replay preflight")
    if manifest.get("mandate_id_required") != MANDATE:
        raise RuntimeError("replay mandate binding changed")
    rows = rebind.build_rows(catalog, source_rows)
    survivors = select_surviving_rows(rows)
    row = next((item for item in survivors if item["provider_request_item_id"] == LIVE_CANARY), None)
    if row is None:
        raise RuntimeError("completed live canary is not in the immutable survivor set")
    evidence = completed_canary_evidence(catalog, row, root)
    if (evidence["builder_reservation_status"] != "consumed"
            or evidence["mandate_reservation_status"] != "settled"):
        raise RuntimeError("provider-free replay requires the canary's existing consumed/settled accounting")
    with catalog._authorization_connection() as conn:
        before_actual_count = conn.execute(
            "SELECT count(*) FROM cost_entries WHERE run_id=? AND entry_type='actual'", (RUN,),
        ).fetchone()[0]
        before_mandate = conn.execute(
            "SELECT actual_spend_aud,unresolved_reserved_aud FROM execution_mandates WHERE mandate_id=?",
            (MANDATE,),
        ).fetchone()
    raw_path = root / "standard-results" / f"{LIVE_CANARY.replace(':', '_')}.json"
    meta_path = response_metadata_path(raw_path)
    raw = raw_path.read_bytes()
    body = json.loads(raw.decode("utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    attempts = catalog.list_provider_request_attempts(provider_request_item_id=LIVE_CANARY)
    response = StandardProviderResponse(int(meta["status_code"]), str(meta["request_id"]), body, raw)
    parsed: dict = {}
    base.MANDATE = MANDATE
    base.OWNER = "phase5-direct-service-v1-2-amendment3-worker"
    base.reconcile(
        catalog, row, response, root, attempts[0]["completed_at"], parsed,
        result_dir=root / "candidate-results-v2",
    )
    if not parsed.get(LIVE_CANARY, {}).get("valid"):
        raise RuntimeError("retained canary did not replay as a valid V1.2 result")
    replayed = completed_canary_evidence(catalog, row, root)
    with catalog._authorization_connection() as conn:
        after_actual_count = conn.execute(
            "SELECT count(*) FROM cost_entries WHERE run_id=? AND entry_type='actual'", (RUN,),
        ).fetchone()[0]
        after_mandate = conn.execute(
            "SELECT actual_spend_aud,unresolved_reserved_aud FROM execution_mandates WHERE mandate_id=?",
            (MANDATE,),
        ).fetchone()
    if (replayed["raw_response_sha256"] != evidence["raw_response_sha256"]
            or replayed["actual_usd"] != evidence["actual_usd"]
            or replayed["actual_aud"] != evidence["actual_aud"]
            or before_actual_count != after_actual_count
            or dict(before_mandate) != dict(after_mandate)):
        raise RuntimeError("second provider-free replay changed response or accounting identity")
    return {
        "status": "V1_2_REPLAY_VALID;ACCOUNTING_IDEMPOTENT",
        "request_item_id": LIVE_CANARY,
        "provider_request_id": evidence["provider_request_id"],
        "responses_id": evidence["responses_id"],
        "raw_response_sha256": evidence["raw_response_sha256"],
        "semantic_classification": evidence["corrected_interpretation"],
        "section_counts": evidence["section_counts"],
        "proposal_count": evidence["proposal_count"],
        "relationship_count": evidence["relationship_count"],
        "replay_valid": parsed[LIVE_CANARY]["valid"],
        "usage": evidence["usage"],
        "actual_usd": evidence["actual_usd"],
        "actual_aud": evidence["actual_aud"],
        "reconciliation_idempotency_key": "actual:" + row["physical_attempt_id"],
        "actual_entries_for_canary": 1,
        "actual_entries_before": before_actual_count,
        "actual_entries_after": after_actual_count,
        "builder_reservation_status": evidence["builder_reservation_status"],
        "mandate_reservation_status": evidence["mandate_reservation_status"],
        "mandate_totals_unchanged": True,
        "duplicate_actual_entries": 0,
        "accounting_mutations": 0,
        "provider_operations": 0,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--reconcile-canary-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--catalogue", type=Path, default=DB)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if sum((args.preflight_only, args.reconcile_canary_only, args.execute)) != 1:
        raise SystemExit("choose exactly one of --preflight-only, --reconcile-canary-only, or --execute")
    if not args.catalogue.is_file():
        raise SystemExit("expected-existing catalogue is missing")
    catalog = SQLiteCatalog(args.catalogue, authorization_path=args.catalogue).open()
    if args.reconcile_canary_only:
        print(json.dumps(reconcile_completed_canary_without_provider(catalog, args.root), sort_keys=True))
        return 0
    rows, evidence = preflight(catalog, args.root)
    if args.preflight_only:
        print(json.dumps(evidence, sort_keys=True))
        return 0

    # The deterministic live-schema canary already crossed exactly once and
    # has a completed receipt/cost; never submit it again. Continue only the
    # sixteen still-prepared identities.
    completed_canary = next((r for r in rows if r["provider_request_item_id"] == LIVE_CANARY), None)
    remainder = [r for r in rows if r["provider_request_item_id"] != LIVE_CANARY]
    if completed_canary is None or len(remainder) != 16:
        raise RuntimeError("v3 ticket and prepared remainder do not identify 1 completed canary plus 16 requests")
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
    validator = lambda body: base.DirectServiceV12WireOutput.model_validate_json(base.output_text(body))
    callback = lambda row, response, usage: base.reconcile(
        catalog, row, response, args.root, timestamp, parsed,
        result_dir=args.root / "candidate-results-v2",
    )
    provider = OpenAIHTTPStandardClient()
    remainder_result = StandardCampaignCoordinator(
        catalog=catalog, provider=provider, runtime_root=args.root, max_concurrency=4,
        now=timestamp, validator=validator, on_reconciled=callback, mandate_evaluator=evaluator,
    ).run(remainder)
    report = {
        "status": "PHASE5_DIRECT_SERVICE_V1_2_REMAINDER_EXECUTED",
        "preflight": evidence,
        "canary": {"status": "previously_completed_and_reconciled_no_resend", "request_item_id": LIVE_CANARY,
                   "provider_posts_this_invocation": 0, "provider_request_id": evidence["completed_canary_evidence"]["provider_request_id"],
                   "responses_id": evidence["completed_canary_evidence"]["responses_id"]},
        "remainder": remainder_result,
        "candidate_results": parsed,
        "provider_operations": 1 + remainder_result.get("provider_posts", 0),
        "provider_operations_this_invocation": remainder_result.get("provider_posts", 0),
        "automatic_retries": 0, "semantic_retries": 0, "fallbacks": [],
        "source_acquisitions": 0, "governed_promotions": 0,
    }
    _write_report(args.root, report)
    print(json.dumps(report, sort_keys=True))
    return 0


def _write_report(root: Path, report: dict) -> None:
    encoded = (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    path = root / "amendment3-remainder-execution-report-v2.json"
    if path.exists() and path.read_bytes() != encoded:
        raise RuntimeError("append-only Amendment-3 remainder report conflicts with existing report")
    if not path.exists():
        path.write_bytes(encoded)
    (root / "amendment3-remainder-execution-report.sha256").write_text(sha(path.read_bytes()) + "\n", encoding="ascii")


if __name__ == "__main__":
    raise SystemExit(main())
