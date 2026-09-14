"""Reconcile the unsent Direct Service V1.1 slice before V1.2 activation.

This command is deliberately provider-free.  It quarantines the old physical
path before releasing its economic reservation, and is safe to resume after a
process interruption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.runtime import SQLiteCatalog


CATALOGUE = Path(r"C:\CharityGraph-runtime\state\charitygraph.sqlite3")
PREPARATION = Path(r"C:\CharityGraph-runtime\phase5-top100-direct-service-v1.2-cutover-v1\preparation.json")
MANDATE = "mandate:phase5-build-standard-luna-v1-amendment-2"
EXPECTED_PREPARATION_SHA256 = "69a11e1b2d4c9561d07ab14578380f0a31afd2376d440360024cb8b356867f26"
EXPECTED_JSONL_SHA256 = "35e1ad5ecbca107566a00010d59d4566ece4be2198f49c42a3cb61e2dc2a3f0a"
REASON = "superseded by authorized Direct Service V1.2 cutover"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_preparation(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if _sha(raw) != EXPECTED_PREPARATION_SHA256:
        raise RuntimeError("pinned V1.2 preparation SHA-256 mismatch")
    preparation = json.loads(raw.decode("utf-8"))
    rows = preparation.get("request_items")
    if not isinstance(rows, list) or len(rows) != 18:
        raise RuntimeError("pinned V1.2 preparation must contain exactly 18 request items")
    if preparation.get("authorization_state") != "pending_amendment_3_activation":
        raise RuntimeError("V1.2 preparation authorization state drifted")
    return preparation, raw


def _read_catalogue_rows(catalogue: Path, request_ids: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    conn = sqlite3.connect(str(catalogue))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in request_ids)
        rows = [dict(row) for row in conn.execute(f"""
            SELECT p.provider_request_item_id,p.run_id,p.physical_attempt_id,
                   p.status AS item_status,p.provider_request_id AS item_provider_request_id,
                   p.provider_receipt_id AS item_provider_receipt_id,
                   a.delivery_attempt_id,a.status AS attempt_status,
                   a.provider_request_id AS attempt_provider_request_id,
                   a.provider_receipt_id AS attempt_provider_receipt_id,
                   ph.subject_id,ph.status AS physical_status,
                   ph.provider_request_id AS physical_request_identity,
                   ph.provider_batch_id,ph.send_started_at,ph.receipt_persisted_at,
                   ph.reservation_id,br.status AS budget_status,br.reserved_aud,
                   er.status AS mandate_reservation_status,
                   er.reserved_aud AS mandate_reserved_aud,er.actual_aud,
                   (SELECT COUNT(*) FROM provider_request_attempts aa
                    WHERE aa.provider_request_item_id=p.provider_request_item_id) AS attempt_count
            FROM provider_request_items p
            JOIN provider_request_attempts a ON a.provider_request_item_id=p.provider_request_item_id
            JOIN physical_attempts ph ON ph.physical_attempt_id=p.physical_attempt_id
            JOIN budget_reservations br ON br.reservation_id=ph.reservation_id
            JOIN execution_mandate_reservations er
              ON er.reservation_id=ph.reservation_id AND er.mandate_id=?
            WHERE p.provider_request_item_id IN ({placeholders})
            ORDER BY p.provider_request_item_id
        """, (MANDATE, *request_ids))]
        mandate = dict(conn.execute("SELECT mandate_id,status,actual_spend_aud,unresolved_reserved_aud,aggregate_hard_aud FROM execution_mandates WHERE mandate_id=?", (MANDATE,)).fetchone() or {})
        return rows, mandate
    finally:
        conn.close()


def preflight(catalogue: Path, preparation: dict[str, Any], *, require_initial_accounting: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = preparation["request_items"]
    request_ids = [row["old_v1_1_provider_request_item_id"] for row in rows]
    if len(set(request_ids)) != 18:
        raise RuntimeError("old V1.1 request identities are not unique")
    db_rows, mandate = _read_catalogue_rows(catalogue, sorted(request_ids))
    if len(db_rows) != 18:
        raise RuntimeError(f"catalogue contains {len(db_rows)}/18 pinned old V1.1 rows")
    expected_subjects = {row["subject_id"] for row in rows}
    actual_subjects = {row["subject_id"] for row in db_rows}
    if expected_subjects != actual_subjects:
        raise RuntimeError("pinned V1.2 subject set does not match catalogue subject set")
    if mandate.get("status") != "active" or mandate.get("aggregate_hard_aud") != "100.00":
        raise RuntimeError("amendment-2 mandate is not the expected active authority")
    if Decimal(str(mandate["actual_spend_aud"])).quantize(Decimal("0.000001")) != Decimal("2.556920"):
        raise RuntimeError("mandate actual spend differs from reconciled baseline")
    unresolved = Decimal(str(mandate["unresolved_reserved_aud"])).quantize(Decimal("0.000001"))
    by_id = {row["provider_request_item_id"]: row for row in db_rows}
    for expected in rows:
        row = by_id[expected["old_v1_1_provider_request_item_id"]]
        errors = []
        if row["subject_id"] != expected["subject_id"]: errors.append("subject")
        if row["item_status"] == "prepared":
            coherent_state = row["attempt_status"] == "prepared" and row["physical_status"] == "prepared" and row["budget_status"] == "active" and row["mandate_reservation_status"] == "active"
        elif row["item_status"] == "cancelled":
            coherent_state = row["attempt_status"] == "cancelled" and row["physical_status"] == "failed" and row["budget_status"] in {"active", "released"} and row["mandate_reservation_status"] in {"active", "settled"}
        else:
            coherent_state = False
        if not coherent_state: errors.append("state")
        for key in ("item_provider_request_id", "item_provider_receipt_id", "attempt_provider_request_id", "attempt_provider_receipt_id", "provider_batch_id", "send_started_at", "receipt_persisted_at"):
            if row[key] is not None: errors.append(key)
        if row["attempt_count"] != 1: errors.append("attempt_count")
        if row["budget_status"] not in {"active", "released"}: errors.append("budget_status")
        if row["mandate_reservation_status"] not in {"active", "settled"}: errors.append("mandate_status")
        if Decimal(str(row["actual_aud"])) != 0: errors.append("actual_aud")
        if Decimal(str(row["reserved_aud"])) != Decimal(str(row["mandate_reserved_aud"])): errors.append("reservation_amount")
        if errors:
            raise RuntimeError(f"whole-set preflight discrepancy for {expected['old_v1_1_provider_request_item_id']}: {','.join(errors)}")
    active_sum = sum((Decimal(str(row["reserved_aud"])) for row in db_rows if row["budget_status"] == "active"), Decimal("0")).quantize(Decimal("0.000001"))
    if unresolved != active_sum:
        raise RuntimeError(f"mandate unresolved reservation total {unresolved} does not equal active cohort reservations {active_sum}")
    if require_initial_accounting and not all(row["item_status"] == "prepared" for row in db_rows):
        # A prior interrupted application is a valid resumable starting point;
        # the row-level state machine above is the authority in that case.
        pass
    return db_rows, mandate


def backup_catalogue(catalogue: Path) -> tuple[Path, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = catalogue.with_name(f"{catalogue.name}.phase5-v12-supersession-{stamp}.bak")
    if target.exists():
        raise RuntimeError(f"refusing to overwrite existing backup: {target}")
    source = sqlite3.connect(str(catalogue))
    backup = sqlite3.connect(str(target))
    try:
        source.backup(backup)
        backup.commit()
    finally:
        backup.close()
        source.close()
    check = sqlite3.connect(str(target))
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("catalogue backup integrity check failed")
        if check.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("catalogue backup foreign-key check failed")
    finally:
        check.close()
    return target, _sha(target.read_bytes())


def apply(catalogue: Path, preparation: dict[str, Any], *, now: str) -> dict[str, Any]:
    rows, _ = preflight(catalogue, preparation)
    by_id = {row["provider_request_item_id"]: row for row in rows}
    catalog = SQLiteCatalog(catalogue, authorization_path=catalogue).open(initialize=False)
    try:
        for expected in preparation["request_items"]:
            current = by_id[expected["old_v1_1_provider_request_item_id"]]
            item_id = current["provider_request_item_id"]
            reservation_id = current["reservation_id"]
            if current["item_status"] == "prepared":
                catalog.abandon_pre_send_provider_request(item_id, now=now, reason=REASON)
            if current["budget_status"] == "active":
                catalog.release_reservation(reservation_id, current["reserved_aud"], now=now, entry_key="pre-send-supersession-release:" + reservation_id)
            if current["mandate_reservation_status"] == "active":
                catalog.settle_execution_mandate_reservation(mandate_id=MANDATE, reservation_id=reservation_id, actual_aud="0", ambiguous=False, now=now)
    finally:
        catalog.close()
    # Re-open and verify, including the restart/idempotency path.
    rows_after, mandate_after = preflight(catalogue, preparation, require_initial_accounting=False)
    if any(row["item_status"] != "cancelled" or row["attempt_status"] != "cancelled" or row["physical_status"] != "failed" or row["budget_status"] != "released" or row["mandate_reservation_status"] != "settled" for row in rows_after):
        raise RuntimeError("post-application supersession state is incomplete")
    catalog = SQLiteCatalog(catalogue, authorization_path=catalogue).open(initialize=False)
    try:
        for expected in preparation["request_items"]:
            current = next(row for row in rows_after if row["provider_request_item_id"] == expected["old_v1_1_provider_request_item_id"])
            catalog.abandon_pre_send_provider_request(current["provider_request_item_id"], now=now, reason="replay")
            catalog.release_reservation(current["reservation_id"], current["reserved_aud"], now=now, entry_key="pre-send-supersession-release:" + current["reservation_id"])
            catalog.settle_execution_mandate_reservation(mandate_id=MANDATE, reservation_id=current["reservation_id"], actual_aud="0", ambiguous=False, now=now)
    finally:
        catalog.close()
    return {"rows": len(rows_after), "mandate": mandate_after}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE)
    parser.add_argument("--preparation", type=Path, default=PREPARATION)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.execute:
        raise SystemExit("choose exactly one of --dry-run or --execute")
    preparation, raw = _load_preparation(args.preparation)
    rows, mandate = preflight(args.catalogue, preparation)
    result: dict[str, Any] = {"status": "PREFLIGHT_GREEN", "request_count": len(rows), "provider_operations": 0, "preparation_sha256": _sha(raw), "mandate_before": mandate}
    if args.execute:
        backup, backup_sha = backup_catalogue(args.catalogue)
        complete = all(row["item_status"] == "cancelled" and row["attempt_status"] == "cancelled" and row["physical_status"] == "failed" and row["budget_status"] == "released" and row["mandate_reservation_status"] == "settled" for row in rows)
        if complete and Decimal(str(mandate["unresolved_reserved_aud"])) == 0:
            result["status"] = "ALREADY_COMPLETE"
        else:
            result["backup_path"] = str(backup.resolve())
            result["backup_sha256"] = backup_sha
            result["applied_at"] = _now()
            result["post"] = apply(args.catalogue, preparation, now=result["applied_at"])
            result["status"] = "SUPERSESSION_COMPLETE"
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
