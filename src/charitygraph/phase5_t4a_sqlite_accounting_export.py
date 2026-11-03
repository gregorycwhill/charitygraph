"""Read-only, source-owned SQLite accounting extraction for Gate 4 T4A9.

This module is deliberately a database boundary, not a ledger and not an
authority.  It opens a caller-selected SQLite catalogue in ``mode=ro`` and
``query_only`` mode, verifies the current migration/schema contract, and
projects only the durable accounting/attempt graph into deterministic in-
memory evidence and coverage documents.  A caller-supplied source authority
and completeness assertion remain separate from the extracted bytes.

No database, file, source row, provider payload or credential is written by
this module.  The candidate is suitable for the existing T4A6/T4A7 path, but
is never independently trusted or send-authorized here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

from .contracts.canonical import canonical_json_bytes
from .phase5_t4a_project_budget_snapshot import (
    DEFAULT_MAX_EVIDENCE_AGE,
    ProjectBudgetSnapshotCandidate,
    build_project_budget_snapshot,
)
from .runtime.migrations import MIGRATIONS, SUPPORTED_VERSION


SQLITE_ACCOUNTING_EXPORT_SCHEMA = "charitygraph.sqlite-accounting-source-export/1"
_COVERAGE_KEYS = (
    "project_wide",
    "logical_paid_tasks_complete",
    "retries_complete",
    "physical_attempts_complete",
    "cohorts_complete",
    "accounting_sources_complete",
    "reservations_complete",
    "actuals_complete",
    "pricing_complete",
)
_REQUIRED_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "schema_migrations": ("version", "name", "checksum", "applied_at"),
    "cohorts": (
        "cohort_id", "cohort_code", "definition_version", "membership_hash",
        "budget_cap_aud", "created_at", "material_hash", "budget_cap_amount",
        "accounting_currency",
    ),
    "runs": ("run_id", "cohort_id", "run_kind", "status", "configuration_hash", "created_at", "updated_at", "material_hash"),
    "tasks": (
        "model_task_id", "run_id", "subject_id", "scope_id", "cohort_id", "task_type",
        "task_schema_id", "cache_key", "provider_id", "model_snapshot", "status",
        "attempt_count", "created_at", "updated_at", "material_hash",
    ),
    "task_attempts": (
        "task_run_id", "model_task_id", "attempt_number", "status", "provider_request_id",
        "provider_batch_id", "pricing_snapshot_id", "fx_snapshot_id", "reservation_id",
        "usage_json",
    ),
    "budget_reservations": (
        "reservation_id", "cohort_id", "run_id", "reserved_aud", "status", "reserved_at",
        "updated_at", "material_hash", "reserved_amount", "accounting_currency",
    ),
    "reservation_tasks": ("reservation_id", "model_task_id"),
    "cost_entries": (
        "entry_key", "entry_hash", "cohort_id", "run_id", "task_run_id", "reservation_id",
        "entry_type", "provider_amount", "provider_currency", "aud_amount",
        "adjustment_direction", "pricing_snapshot_id", "fx_snapshot_id", "usage_json",
        "recorded_at", "accounting_amount", "accounting_currency",
    ),
    "physical_attempts": (
        "physical_attempt_id", "run_id", "subject_id", "delivery_mode", "status",
        "provider_request_id", "reservation_id", "provider_batch_id", "created_at",
        "send_started_at", "receipt_persisted_at", "updated_at",
    ),
    "physical_attempt_members": ("physical_attempt_id", "model_task_id"),
    "provider_request_items": (
        "provider_request_item_id", "run_id", "model_task_id", "physical_attempt_id",
        "delivery_job_id", "provider_id", "model_route", "requested_delivery_mode",
        "effective_service_tier", "status", "provider_request_id", "provider_receipt_id",
        "result_ref", "created_at", "updated_at",
    ),
    "delivery_jobs": (
        "delivery_job_id", "run_id", "provider_id", "model_route", "delivery_mode",
        "provider_batch_id", "status", "pricing_snapshot_id", "created_at", "updated_at",
    ),
    "provider_receipts": (
        "provider_receipt_id", "physical_attempt_id", "provider_request_id", "received_at",
    ),
    "provider_request_attempts": (
        "delivery_attempt_id", "provider_request_item_id", "physical_attempt_id",
        "delivery_job_id", "attempt_ordinal", "authorization_id", "attempt_class",
        "predecessor_attempt_id", "status", "provider_request_id", "provider_receipt_id",
        "result_ref", "created_at", "submitted_at", "completed_at", "updated_at",
    ),
}
_EXPORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "cohorts": ("cohort_id", "budget_cap_amount", "accounting_currency"),
    "runs": ("run_id", "cohort_id", "run_kind", "status", "created_at", "updated_at"),
    "tasks": ("model_task_id", "run_id", "subject_id", "scope_id", "cohort_id", "task_type", "task_schema_id", "provider_id", "model_snapshot", "status", "attempt_count"),
    "task_attempts": ("task_run_id", "model_task_id", "attempt_number", "status", "provider_request_id", "provider_batch_id", "pricing_snapshot_id", "fx_snapshot_id", "reservation_id", "usage_json"),
    "budget_reservations": ("reservation_id", "cohort_id", "run_id", "reserved_amount", "status", "accounting_currency"),
    "reservation_tasks": ("reservation_id", "model_task_id"),
    "cost_entries": ("entry_key", "cohort_id", "run_id", "task_run_id", "reservation_id", "entry_type", "provider_amount", "provider_currency", "aud_amount", "adjustment_direction", "pricing_snapshot_id", "fx_snapshot_id", "usage_json", "accounting_amount", "accounting_currency"),
    "physical_attempts": ("physical_attempt_id", "run_id", "subject_id", "delivery_mode", "status", "provider_request_id", "reservation_id", "provider_batch_id"),
    "physical_attempt_members": ("physical_attempt_id", "model_task_id"),
    "provider_request_items": ("provider_request_item_id", "run_id", "model_task_id", "physical_attempt_id", "delivery_job_id", "provider_id", "model_route", "requested_delivery_mode", "effective_service_tier", "status", "provider_request_id", "provider_receipt_id"),
    "delivery_jobs": ("delivery_job_id", "run_id", "provider_id", "model_route", "delivery_mode", "provider_batch_id", "status", "pricing_snapshot_id"),
    "provider_receipts": ("provider_receipt_id", "physical_attempt_id", "provider_request_id", "received_at"),
    "provider_request_attempts": ("delivery_attempt_id", "provider_request_item_id", "physical_attempt_id", "delivery_job_id", "attempt_ordinal", "authorization_id", "attempt_class", "predecessor_attempt_id", "status", "provider_request_id", "provider_receipt_id"),
}
_RECORD_IDS = {
    "cohorts": "cohort_id",
    "runs": "run_id",
    "tasks": "model_task_id",
    "task_attempts": "task_run_id",
    "budget_reservations": "reservation_id",
    "reservation_tasks": "model_task_id",
    "cost_entries": "entry_key",
    "physical_attempts": "physical_attempt_id",
    "physical_attempt_members": "model_task_id",
    "provider_request_items": "provider_request_item_id",
    "delivery_jobs": "delivery_job_id",
    "provider_receipts": "provider_receipt_id",
    "provider_request_attempts": "delivery_attempt_id",
}
_OPTIONAL_PRICING_FX_TABLES = {
    "pricing_snapshots",
    "pricing_records",
    "fx_snapshots",
    "fx_records",
}
_TABLE_SCHEMA_SHA256 = hashlib.sha256(canonical_json_bytes({key: list(value) for key, value in sorted(_REQUIRED_TABLE_COLUMNS.items())})).hexdigest()

ExportStatus = Literal["CANDIDATE_NOT_ATTESTED", "NOT_ATTESTABLE", "BLOCKED"]


@dataclass(frozen=True)
class SQLiteAccountingSourceExport:
    """In-memory export and diagnostics; never an independent authority."""

    status: ExportStatus
    source_authority: Mapping[str, object] | None = None
    migration_version: int | None = None
    schema_sha256: str | None = None
    column_schema_sha256: str = _TABLE_SCHEMA_SHA256
    source_inventory: tuple[Mapping[str, object], ...] = ()
    coverage_diagnostics: tuple[Mapping[str, object], ...] = ()
    diagnostics: tuple[str, ...] = ()
    accounting_evidence: Mapping[str, object] | None = None
    coverage_manifest: Mapping[str, object] | None = None
    evidence_bytes: bytes | None = None
    manifest_bytes: bytes | None = None
    candidate: ProjectBudgetSnapshotCandidate | None = None
    candidate_bytes: bytes | None = None
    candidate_sha256: str | None = None
    independent_trust: Literal["NOT_SUPPLIED"] = "NOT_SUPPLIED"
    request_ticket: None = None
    send_authorization: Literal["not_authorized_for_send"] = "not_authorized_for_send"


def required_column_schema_sha256() -> str:
    """Return the deterministic hash of the extractor's required columns."""

    return _TABLE_SCHEMA_SHA256


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(char in "0123456789abcdef" for char in value)


def _provenance(authority: Mapping[str, object]) -> list[dict[str, object]]:
    return [{"source_id": authority["source_id"], "source_kind": authority["source_kind"], "content_sha256": authority["content_sha256"]}]


def _authority_diagnostics(authority: Mapping[str, object] | None) -> list[str]:
    required = {"source_id", "source_kind", "source_version", "content_sha256", "authority_id", "authority_version", "retention_id", "retention_version", "retention_status"}
    if not isinstance(authority, Mapping):
        return ["source_authority_missing_or_invalid"]
    reasons = [f"source_authority_field_missing:{key}" for key in sorted(required - set(authority))]
    for key in ("source_id", "source_kind", "source_version", "authority_id", "authority_version", "retention_id", "retention_version"):
        if key in authority and not _valid_id(authority.get(key)):
            reasons.append(f"source_authority_{key}_invalid")
    if not _valid_sha(authority.get("content_sha256")):
        reasons.append("source_authority_content_sha256_invalid")
    if authority.get("retention_status") != "authorized":
        reasons.append("source_retention_not_authorized")
    return reasons


def _iso(value: object, label: str, reasons: list[str]) -> str | None:
    if not isinstance(value, str):
        reasons.append(f"{label}_missing_or_invalid")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        reasons.append(f"{label}_invalid")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        reasons.append(f"{label}_timezone_missing")
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _amount(value: object, label: str, reasons: list[str]) -> Decimal | None:
    if not isinstance(value, str):
        reasons.append(f"{label}_not_decimal_string")
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        reasons.append(f"{label}_invalid")
        return None
    if not parsed.is_finite() or parsed < 0:
        reasons.append(f"{label}_invalid")
        return None
    return parsed


def _json_object(value: object, label: str, reasons: list[str]) -> dict[str, object] | None:
    if value is None:
        reasons.append(f"{label}_missing")
        return None
    try:
        loaded = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        reasons.append(f"{label}_invalid_json")
        return None
    if not isinstance(loaded, dict):
        reasons.append(f"{label}_not_object")
        return None
    return loaded


def _table_columns(conn: sqlite3.Connection) -> dict[str, tuple[str, ...]]:
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {name: tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{name.replace(chr(34), chr(34) * 2)}")')) for name in names}


def _schema_sha256(conn: sqlite3.Connection, tables: Mapping[str, tuple[str, ...]]) -> str:
    material = []
    for name in sorted(tables):
        sql_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        material.append({"name": name, "columns": list(tables[name]), "sql": sql_row[0] if sql_row else None})
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def _read_rows(conn: sqlite3.Connection, table: str, columns: Sequence[str]) -> list[dict[str, object]]:
    quoted = ", ".join(f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns)
    table_name = table.replace(chr(34), chr(34) * 2)
    rows = conn.execute(f'SELECT {quoted} FROM "{table_name}" ORDER BY rowid').fetchall()
    return [{column: row[index] for index, column in enumerate(columns)} for row in rows]


def _inventory(table_rows: Mapping[str, list[dict[str, object]]], authority: Mapping[str, object] | None) -> tuple[Mapping[str, object], ...]:
    source_id = authority.get("source_id") if isinstance(authority, Mapping) else None
    source_hash = authority.get("content_sha256") if isinstance(authority, Mapping) else None
    result = []
    for table in _RECORD_IDS:
        rows = table_rows.get(table)
        if rows is None:
            result.append({"record_class": table, "state": "missing", "row_count": None, "record_id_sha256": None, "source_id": source_id, "source_content_sha256": source_hash})
            continue
        ids = sorted(str(row.get(_RECORD_IDS[table])) for row in rows)
        result.append({"record_class": table, "state": "present", "row_count": len(rows), "record_id_sha256": hashlib.sha256(canonical_json_bytes(ids)).hexdigest(), "source_id": source_id, "source_content_sha256": source_hash})
    return tuple(result)


def _optional_pricing_fx_inventory(
    conn: sqlite3.Connection,
    tables: Mapping[str, tuple[str, ...]],
    authority: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    result = []
    for table in sorted(set(tables) & _OPTIONAL_PRICING_FX_TABLES):
        rows = _read_rows(conn, table, tables[table])
        result.append({
            "record_class": f"pricing_fx_authority:{table}",
            "state": "present",
            "row_count": len(rows),
            "rows_sha256": hashlib.sha256(canonical_json_bytes(rows)).hexdigest(),
            "source_id": authority.get("source_id"),
            "source_content_sha256": authority.get("content_sha256"),
        })
    return tuple(result)


def _coverage_diagnostics(coverage: Mapping[str, object] | None, diagnostics: Sequence[str]) -> tuple[Mapping[str, object], ...]:
    return tuple({"coverage_class": key, "state": "complete" if coverage and coverage.get(key) is True and not any(key in reason for reason in diagnostics) else "incomplete", "asserted": None if coverage is None else coverage.get(key)} for key in _COVERAGE_KEYS)


def _validate_migrations(conn: sqlite3.Connection, reasons: list[str]) -> int | None:
    try:
        rows = conn.execute("SELECT version, name, checksum FROM schema_migrations ORDER BY version").fetchall()
    except sqlite3.Error:
        reasons.append("schema_migrations_missing")
        return None
    if not rows:
        reasons.append("schema_migrations_empty")
        return None
    expected = {migration.version: (migration.name, migration.checksum) for migration in MIGRATIONS}
    actual = {int(row[0]): (row[1], row[2]) for row in rows}
    if max(actual) != SUPPORTED_VERSION or set(actual) != set(expected):
        reasons.append(f"migration_version_mismatch:{max(actual)}:{SUPPORTED_VERSION}")
    for version, identity in expected.items():
        if actual.get(version) != identity:
            reasons.append(f"migration_identity_mismatch:{version}")
    return max(actual)


def _validate_schema(conn: sqlite3.Connection, reasons: list[str]) -> tuple[dict[str, tuple[str, ...]], str | None]:
    tables = _table_columns(conn)
    for table, columns in _REQUIRED_TABLE_COLUMNS.items():
        if table not in tables:
            reasons.append(f"required_table_missing:{table}")
            continue
        missing = sorted(set(columns) - set(tables[table]))
        reasons.extend(f"required_column_missing:{table}.{column}" for column in missing)
    if any(reason.startswith("required_table_missing:") or reason.startswith("required_column_missing:") for reason in reasons):
        return tables, None
    return tables, _schema_sha256(conn, tables)


def _row_with_provenance(row: Mapping[str, object], authority: Mapping[str, object]) -> dict[str, object]:
    result = {key: value for key, value in row.items() if value is not None}
    result["source_provenance"] = _provenance(authority)
    return result


def _scope(row: Mapping[str, object]) -> str:
    return str(row.get("scope_id") or row.get("subject_id") or row.get("cohort_id") or "unknown")


def _coverage_assertion(assertion: Mapping[str, object] | None, authority: Mapping[str, object], reasons: list[str]) -> dict[str, bool]:
    if not isinstance(assertion, Mapping):
        reasons.append("coverage_authority_missing_or_invalid")
        return {key: False for key in _COVERAGE_KEYS}
    if assertion.get("population_complete") is not True or assertion.get("project_wide") is not True:
        reasons.append("global_population_completeness_not_asserted")
    if not _valid_id(assertion.get("scope")):
        reasons.append("coverage_authority_scope_missing")
    if assertion.get("source_provenance") != _provenance(authority):
        reasons.append("coverage_authority_source_binding_missing")
    coverage = {}
    for key in _COVERAGE_KEYS:
        value = assertion.get(key)
        if type(value) is not bool:
            reasons.append(f"coverage_authority_field_invalid:{key}")
            coverage[key] = False
        else:
            coverage[key] = value
    return coverage


def _validate_graph(rows: Mapping[str, list[dict[str, object]]], reasons: list[str]) -> dict[str, object]:
    cohorts = {row["cohort_id"]: row for row in rows["cohorts"]}
    runs = {row["run_id"]: row for row in rows["runs"]}
    tasks = {row["model_task_id"]: row for row in rows["tasks"]}
    reservations = {row["reservation_id"]: row for row in rows["budget_reservations"]}
    physical = {row["physical_attempt_id"]: row for row in rows["physical_attempts"]}
    items = {row["provider_request_item_id"]: row for row in rows["provider_request_items"]}
    jobs = {row["delivery_job_id"]: row for row in rows["delivery_jobs"]}
    receipts = {row["provider_receipt_id"]: row for row in rows["provider_receipts"]}
    provider_attempts = rows["provider_request_attempts"]
    if len({str(row.get("physical_attempt_id")) for row in provider_attempts}) != len(provider_attempts):
        reasons.append("provider_request_attempts_physical_attempt_id_not_unique")
    if len({str(row.get("provider_receipt_id")) for row in rows["provider_receipts"]}) != len(rows["provider_receipts"]):
        reasons.append("provider_receipt_identity_not_unique")
    members_by_physical: dict[str, list[str]] = {}
    for member in rows["physical_attempt_members"]:
        members_by_physical.setdefault(str(member["physical_attempt_id"]), []).append(str(member["model_task_id"]))
        if member["physical_attempt_id"] not in physical:
            reasons.append(f"orphaned_physical_attempt_member:{member['model_task_id']}")
        if member["model_task_id"] not in tasks:
            reasons.append(f"orphaned_physical_attempt_member_task:{member['model_task_id']}")
    for physical_id, member_ids in members_by_physical.items():
        if len(set(member_ids)) != len(member_ids):
            reasons.append(f"duplicate_physical_attempt_member:{physical_id}")
    for run_id, run in runs.items():
        if run.get("cohort_id") not in cohorts:
            reasons.append(f"orphaned_run_cohort:{run_id}")
    for task_id, task in tasks.items():
        run = runs.get(task.get("run_id"))
        if run is None:
            reasons.append(f"orphaned_task_run:{task_id}")
        elif task.get("cohort_id") not in (None, run.get("cohort_id")):
            reasons.append(f"task_run_cohort_conflict:{task_id}")
    for reservation_id, reservation in reservations.items():
        run = runs.get(reservation.get("run_id"))
        if run is None or run.get("cohort_id") != reservation.get("cohort_id"):
            reasons.append(f"reservation_run_cohort_conflict:{reservation_id}")
        if reservation.get("accounting_currency") != "AUD":
            reasons.append(f"reservation_currency_invalid:{reservation_id}")
        _amount(reservation.get("reserved_amount"), f"reserved_amount:{reservation_id}", reasons)
    for physical_id, row in physical.items():
        run = runs.get(row.get("run_id"))
        if run is None or run.get("cohort_id") not in cohorts:
            reasons.append(f"physical_attempt_run_missing:{physical_id}")
        reservation_id = row.get("reservation_id")
        if reservation_id is not None and reservation_id not in reservations:
            reasons.append(f"physical_attempt_reservation_missing:{physical_id}")
        member_ids = members_by_physical.get(str(physical_id), [])
        if not member_ids:
            reasons.append(f"physical_attempt_members_missing:{physical_id}")
        for task_id in member_ids:
            task = tasks.get(task_id)
            if task and (task.get("run_id") != row.get("run_id") or task.get("subject_id") != row.get("subject_id")):
                reasons.append(f"physical_attempt_member_lineage_conflict:{physical_id}")
    for item_id, item in items.items():
        if item.get("run_id") not in runs or item.get("model_task_id") not in tasks:
            reasons.append(f"orphaned_provider_request_item:{item_id}")
        if item.get("physical_attempt_id") not in physical:
            reasons.append(f"orphaned_provider_request_item_physical:{item_id}")
        if item.get("delivery_job_id") not in jobs:
            reasons.append(f"orphaned_provider_request_item_job:{item_id}")
    for job_id, job in jobs.items():
        if job.get("run_id") not in runs:
            reasons.append(f"orphaned_delivery_job_run:{job_id}")
    for receipt_id, receipt in receipts.items():
        if receipt.get("physical_attempt_id") not in physical:
            reasons.append(f"orphaned_provider_receipt:{receipt_id}")
    attempts_by_physical: dict[str, list[dict[str, object]]] = {}
    for attempt in provider_attempts:
        physical_id = str(attempt.get("physical_attempt_id"))
        attempts_by_physical.setdefault(physical_id, []).append(attempt)
        if attempt.get("physical_attempt_id") not in physical:
            reasons.append(f"orphaned_provider_request_attempt:{attempt.get('delivery_attempt_id')}")
        if attempt.get("provider_request_item_id") not in items:
            reasons.append(f"orphaned_provider_request_attempt_item:{attempt.get('delivery_attempt_id')}")
        if attempt.get("delivery_job_id") not in jobs:
            reasons.append(f"orphaned_provider_request_attempt_job:{attempt.get('delivery_attempt_id')}")
        if attempt.get("provider_receipt_id") is not None and attempt.get("provider_receipt_id") not in receipts:
            reasons.append(f"orphaned_provider_request_attempt_receipt:{attempt.get('delivery_attempt_id')}")
    for physical_id, row in physical.items():
        if not attempts_by_physical.get(str(physical_id)):
            reasons.append(f"physical_attempt_provider_attempt_missing:{physical_id}")
        if row.get("status") in {"receipt_persisted", "validated"} and not any(receipt.get("physical_attempt_id") == physical_id for receipt in receipts.values()):
            reasons.append(f"receipt_missing_for_physical_attempt:{physical_id}")
    for receipt_id in receipts:
        if not any(attempt.get("provider_receipt_id") == receipt_id for attempt in provider_attempts):
            reasons.append(f"receipt_attempt_linkage_missing:{receipt_id}")
    for item_id, item in items.items():
        if item.get("provider_receipt_id") is not None:
            receipt = receipts.get(item.get("provider_receipt_id"))
            if receipt is None or receipt.get("physical_attempt_id") != item.get("physical_attempt_id"):
                reasons.append(f"receipt_item_linkage_conflict:{item_id}")
    return {"cohorts": cohorts, "runs": runs, "tasks": tasks, "reservations": reservations, "physical": physical, "items": items, "jobs": jobs, "receipts": receipts, "members_by_physical": members_by_physical, "attempts_by_physical": attempts_by_physical}


def _validate_costs(rows: Mapping[str, list[dict[str, object]]], graph: Mapping[str, object], reasons: list[str]) -> dict[str, str]:
    reservations = graph["reservations"]
    items = graph["items"]
    physical = graph["physical"]
    costs: dict[str, str] = {}
    for row in rows["cost_entries"]:
        entry_id = str(row["entry_key"])
        costs[entry_id] = entry_id
        reservation = reservations.get(row.get("reservation_id"))
        if reservation is None or reservation.get("cohort_id") != row.get("cohort_id") or reservation.get("run_id") != row.get("run_id"):
            reasons.append(f"cost_entry_reservation_lineage_invalid:{entry_id}")
        if row.get("accounting_currency") != "AUD":
            reasons.append(f"cost_entry_currency_invalid:{entry_id}")
        amount = _amount(row.get("accounting_amount"), f"accounting_amount:{entry_id}", reasons)
        if amount is not None and row.get("accounting_currency") == "AUD" and row.get("aud_amount") is not None:
            aud = _amount(row.get("aud_amount"), f"aud_amount:{entry_id}", reasons)
            if aud is not None and aud != amount:
                reasons.append(f"accounting_aud_amount_mismatch:{entry_id}")
        if row.get("entry_type") == "actual":
            pricing = row.get("pricing_snapshot_id")
            fx = row.get("fx_snapshot_id")
            if not _valid_id(pricing) or not _valid_id(fx):
                reasons.append(f"unpriced_actual_cost:{entry_id}")
            provider_amount = None
            if row.get("provider_amount") is not None:
                provider_amount = _amount(row.get("provider_amount"), f"provider_amount:{entry_id}", reasons)
            provider_currency = row.get("provider_currency")
            if provider_currency is not None and (not isinstance(provider_currency, str) or len(provider_currency) != 3 or provider_currency != provider_currency.upper()):
                reasons.append(f"provider_currency_invalid:{entry_id}")
            if provider_amount is not None and provider_currency == "AUD" and amount is not None and provider_amount != amount:
                reasons.append(f"provider_accounting_amount_mismatch:{entry_id}")
            usage = _json_object(row.get("usage_json"), f"actual_usage:{entry_id}", reasons)
            if usage is None or not _valid_id(usage.get("provider_request_item_id")) or not _valid_id(usage.get("provider_receipt_id")):
                reasons.append(f"actual_receipt_item_provenance_missing:{entry_id}")
            else:
                item = items.get(usage.get("provider_request_item_id"))
                if item is None or item.get("provider_receipt_id") != usage.get("provider_receipt_id"):
                    reasons.append(f"actual_receipt_item_linkage_invalid:{entry_id}")
                elif item.get("physical_attempt_id") not in physical:
                    reasons.append(f"actual_physical_attempt_missing:{entry_id}")
                else:
                    row["physical_attempt_id"] = item.get("physical_attempt_id")
        elif row.get("entry_type") not in {"reservation_release", "credit", "adjustment"}:
            reasons.append(f"cost_entry_type_unknown:{entry_id}")
    return costs


def _bind_rows(rows: Mapping[str, list[dict[str, object]]], authority: Mapping[str, object], graph: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    cohorts = []
    for row in rows["cohorts"]:
        cohorts.append(_row_with_provenance({"cohort_id": row["cohort_id"], "accounting_currency": row["accounting_currency"], "scope": f"cohort:{row['cohort_id']}"}, authority))
    runs = []
    for row in rows["runs"]:
        runs.append(_row_with_provenance({"run_id": row["run_id"], "cohort_id": row["cohort_id"], "scope": f"cohort:{row['cohort_id']}"}, authority))
    tasks = []
    for row in rows["tasks"]:
        cohort_id = row.get("cohort_id") or graph["runs"].get(row["run_id"], {}).get("cohort_id")
        tasks.append(_row_with_provenance({"model_task_id": row["model_task_id"], "run_id": row["run_id"], "cohort_id": cohort_id, "scope_id": row.get("scope_id"), "subject_id": row.get("subject_id"), "scope": _scope(row)}, authority))
    task_attempts = [_row_with_provenance(row, authority) for row in rows["task_attempts"]]
    reservations = [_row_with_provenance(row, authority) for row in rows["budget_reservations"]]
    costs = [_row_with_provenance(row, authority) for row in rows["cost_entries"]]
    physical = []
    for row in rows["physical_attempts"]:
        cohort_id = graph["runs"].get(row["run_id"], {}).get("cohort_id")
        physical.append(_row_with_provenance({"physical_attempt_id": row["physical_attempt_id"], "run_id": row["run_id"], "cohort_id": cohort_id, "reservation_id": row.get("reservation_id"), "status": row["status"], "logical_task_ids": sorted(graph["members_by_physical"].get(str(row["physical_attempt_id"]), [])), "scope": f"cohort:{cohort_id}"}, authority))
    provider_attempts = [_row_with_provenance(row, authority) for row in rows["provider_request_attempts"]]
    evidence = {
        "schema_id": "charitygraph.durable-accounting-evidence/1",
        "evidence_id": f"evidence:sqlite:{authority['source_id']}",
        "evidence_version": "sqlite-accounting-export/1",
        "project_id": None,
        "as_of": None,
        "source_provenance": _provenance(authority),
        "runs": runs,
        "cohorts": cohorts,
        "logical_tasks": tasks,
        "task_attempts": task_attempts,
        "reservations": reservations,
        "cost_entries": costs,
        "physical_attempts": physical,
        "provider_request_attempts": provider_attempts,
        "physical_attempt_members": [_row_with_provenance(row, authority) for row in rows["physical_attempt_members"]],
        "provider_request_items": [_row_with_provenance(row, authority) for row in rows["provider_request_items"]],
        "delivery_jobs": [_row_with_provenance(row, authority) for row in rows["delivery_jobs"]],
        "provider_receipts": [_row_with_provenance(row, authority) for row in rows["provider_receipts"]],
        "reservation_tasks": [_row_with_provenance(row, authority) for row in rows["reservation_tasks"]],
    }
    manifest = {
        "schema_id": "charitygraph.project-wide-paid-work-coverage-manifest/1",
        "manifest_id": f"manifest:sqlite:{authority['source_id']}",
        "manifest_version": "sqlite-accounting-export/1",
        "project_id": None,
        "as_of": None,
        "authority": {"authority_id": authority["authority_id"], "authority_version": authority["authority_version"], "source_provenance": _provenance(authority)},
        "coverage_semantics": {
            "scope": "all durable paid work in the supplied SQLite source",
            "logical_paid_tasks": "every durable paid task",
            "retries": "every durable task attempt",
            "physical_attempts": "every durable physical provider attempt",
            "cohorts": "every durable accounting cohort",
            "accounting_sources": "the supplied SQLite source",
            "reservations": "every durable reservation and release",
            "actuals": "every actual, credit and adjustment",
            "pricing": "every actual has persisted pricing/FX identifiers and compatible amounts",
        },
        "coverage": {},
        "accounting_sources": [{"source_id": authority["source_id"], "source_type": authority["source_kind"], "content_sha256": authority["content_sha256"], "scope": "project", "source_provenance": _provenance(authority)}],
        "cohorts": [{"cohort_id": row["cohort_id"], "accounting_source_ids": [authority["source_id"]], "scope": f"cohort:{row['cohort_id']}", "source_provenance": _provenance(authority)} for row in cohorts],
        "logical_paid_tasks": [{"logical_task_id": row["model_task_id"], "cohort_id": row["cohort_id"], "scope": row["scope"], "source_provenance": _provenance(authority)} for row in tasks],
        "retries": [{"task_run_id": row["task_run_id"], "logical_task_id": row["model_task_id"], "attempt_number": row["attempt_number"], "physical_attempt_ids": sorted(str(item["physical_attempt_id"]) for item in rows["physical_attempt_members"] if item["model_task_id"] == row["model_task_id"]), "scope": str(graph["tasks"].get(row["model_task_id"], {}).get("scope_id") or graph["tasks"].get(row["model_task_id"], {}).get("subject_id") or "unknown"), "source_provenance": _provenance(authority)} for row in rows["task_attempts"]],
        "physical_attempts": [{"physical_attempt_id": row["physical_attempt_id"], "cohort_id": graph["runs"].get(row["run_id"], {}).get("cohort_id"), "logical_task_ids": sorted(graph["members_by_physical"].get(str(row["physical_attempt_id"]), [])), "scope": f"cohort:{graph['runs'].get(row['run_id'], {}).get('cohort_id')}", "source_provenance": _provenance(authority)} for row in rows["physical_attempts"]],
        "reservation_ids": sorted(str(row["reservation_id"]) for row in rows["budget_reservations"]),
        "cost_entry_ids": sorted(str(row["entry_key"]) for row in rows["cost_entries"]),
    }
    return evidence, manifest


def _open_read_only(database: str | Path | sqlite3.Connection) -> tuple[sqlite3.Connection, bool]:
    if isinstance(database, sqlite3.Connection):
        conn = database
        conn.execute("PRAGMA query_only = ON")
        if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise sqlite3.OperationalError("SQLite query_only could not be enabled")
        return conn, False
    path = Path(database)
    if not path.is_absolute():
        path = path.resolve()
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
        conn.close()
        raise sqlite3.OperationalError("SQLite query_only could not be enabled")
    return conn, True


def extract_sqlite_accounting_source(
    database: str | Path | sqlite3.Connection,
    *,
    project_id: str,
    as_of: datetime,
    source_authority: Mapping[str, object],
    coverage_authority: Mapping[str, object] | None,
    max_evidence_age: timedelta = DEFAULT_MAX_EVIDENCE_AGE,
) -> SQLiteAccountingSourceExport:
    """Extract the current durable accounting graph without opening write mode."""

    reasons = _authority_diagnostics(source_authority)
    if not _valid_id(project_id):
        reasons.append("project_id_missing_or_invalid")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        reasons.append("as_of_not_timezone_aware")
        as_of_text = None
    else:
        as_of_text = as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    coverage = _coverage_assertion(coverage_authority, source_authority, reasons)
    if not isinstance(source_authority, Mapping) or any(reason.startswith("source_authority_") or reason.startswith("source_retention_") for reason in reasons):
        return SQLiteAccountingSourceExport(status="NOT_ATTESTABLE", source_authority=source_authority if isinstance(source_authority, Mapping) else None, diagnostics=_unique(reasons), coverage_diagnostics=_coverage_diagnostics(coverage, reasons))
    conn: sqlite3.Connection | None = None
    close = False
    try:
        conn, close = _open_read_only(database)
        migration_version = _validate_migrations(conn, reasons)
        tables, schema_hash = _validate_schema(conn, reasons)
        if schema_hash is None:
            return SQLiteAccountingSourceExport(status="NOT_ATTESTABLE", source_authority=source_authority if isinstance(source_authority, Mapping) else None, migration_version=migration_version, schema_sha256=None, diagnostics=_unique(reasons), coverage_diagnostics=_coverage_diagnostics(coverage, reasons))
        table_rows = {table: _read_rows(conn, table, columns) for table, columns in _EXPORT_COLUMNS.items()}
        inventory = _inventory(table_rows, source_authority)
        optional_inventory = _optional_pricing_fx_inventory(conn, tables, source_authority)
        if not optional_inventory:
            reasons.append("pricing_fx_authority_records_unavailable")
            coverage["pricing_complete"] = False
        inventory += optional_inventory
        graph = _validate_graph(table_rows, reasons)
        _validate_costs(table_rows, graph, reasons)
        evidence, manifest = _bind_rows(table_rows, source_authority, graph)
        evidence["project_id"] = project_id
        evidence["as_of"] = as_of_text
        manifest["project_id"] = project_id
        manifest["as_of"] = as_of_text
        manifest["coverage"] = {key: bool(coverage.get(key)) for key in _COVERAGE_KEYS}
        evidence_bytes = canonical_json_bytes(evidence)
        manifest_bytes = canonical_json_bytes(manifest)
        candidate = build_project_budget_snapshot(evidence_bytes, manifest_bytes, project_id=project_id, now=as_of, max_evidence_age=max_evidence_age)
        reasons.extend(candidate.reasons)
        if any(not value for value in manifest["coverage"].values()):
            reasons.append("coverage_manifest_incomplete")
        blocking_prefixes = ("orphaned_", "conflict", "currency_", "unpriced_", "actual_", "physical_attempt_", "provider_request_attempts_physical_attempt_id_not_unique", "receipt_", "cost_entry_", "reserved_amount_", "accounting_", "migration_", "unresolved_", "physical_attempt_status_unknown:")
        status: ExportStatus = "BLOCKED" if any(reason.startswith(blocking_prefixes) for reason in reasons) else "NOT_ATTESTABLE" if reasons else "CANDIDATE_NOT_ATTESTED"
        return SQLiteAccountingSourceExport(status=status, source_authority=source_authority, migration_version=migration_version, schema_sha256=schema_hash, source_inventory=inventory, coverage_diagnostics=_coverage_diagnostics(coverage, reasons), diagnostics=_unique(reasons), accounting_evidence=evidence, coverage_manifest=manifest, evidence_bytes=evidence_bytes, manifest_bytes=manifest_bytes, candidate=candidate, candidate_bytes=candidate.snapshot_bytes, candidate_sha256=candidate.snapshot_sha256)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        reasons.append(f"sqlite_read_failed:{type(exc).__name__}")
        return SQLiteAccountingSourceExport(status="NOT_ATTESTABLE", source_authority=source_authority if isinstance(source_authority, Mapping) else None, diagnostics=_unique(reasons), coverage_diagnostics=_coverage_diagnostics(coverage, reasons))
    finally:
        if close and conn is not None:
            conn.close()


__all__ = [
    "SQLITE_ACCOUNTING_EXPORT_SCHEMA",
    "SQLiteAccountingSourceExport",
    "extract_sqlite_accounting_source",
    "required_column_schema_sha256",
]
