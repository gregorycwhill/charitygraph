"""Read-only projection of one persisted Phase 5 run.

This module is intentionally an observer, not a second catalogue API.  It
opens the committed SQLite catalogue in ``mode=ro`` and reads only the
committed v29 operational tables needed by the pure diagnostics projection.
It does not import ``SQLiteCatalog`` because the working tree may contain an
unrelated, dirty catalogue implementation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence
from .phase5_run_diagnostics import (
    DiagnosticProjection,
    RunDiagnosticsError,
    project_run_diagnostics,
)
from .runtime.migrations import SUPPORTED_VERSION


class PersistedRunDiagnosticsError(RunDiagnosticsError):
    """Raised when a persisted run cannot be joined without guessing."""


@dataclass(frozen=True)
class PersistedRunDiagnosticSnapshot:
    """Bounded, immutable-in-use evidence read from one SQLite snapshot."""

    database_path: str
    run_id: str
    schema_version: int
    snapshot_observed_at: str
    record_counts: Mapping[str, int]
    snapshot_hash: str
    run_record: Mapping[str, Any]
    ledger_snapshot: Mapping[str, Any]
    provenance_digests: Mapping[str, Any] = field(default_factory=dict)

    @property
    def observation_version(self) -> str:
        return f"sqlite-v{self.schema_version}:{self.snapshot_hash}"


_REQUIRED_TABLES = (
    "schema_migrations",
    "runs",
    "tasks",
    "task_attempts",
    "budget_reservations",
    "reservation_tasks",
    "cost_entries",
    "physical_attempts",
    "physical_attempt_members",
    "provider_receipts",
    "delivery_jobs",
    "provider_request_items",
    "provider_request_attempts",
    "standard_transport_traces",
)

_RUN_STATES = {"planned", "running", "succeeded", "failed", "cancelled", "held"}
_TASK_STATES = {
    "ready",
    "leased",
    "running",
    "succeeded",
    "failed_retryable",
    "failed_terminal",
    "held",
    "cancelled",
}
_ITEM_STATES = {
    "prepared",
    "submitted",
    "in_progress",
    "send_ambiguous",
    "completed",
    "failed",
    "expired",
    "cancelled",
    "held",
}
_DELIVERY_ATTEMPT_STATES = {
    "prepared",
    "send_started",
    "submitted",
    "in_progress",
    "receipt_persisted",
    "completed",
    "failed",
    "expired",
    "cancelled",
    "held",
}
_PHYSICAL_STATES = {"prepared", "send_started", "receipt_persisted", "validated", "held", "failed"}
_TRACE_STATES = {
    "NOT_SENT",
    "CROSSING_STARTED",
    "LOCAL_PRE_SEND_FAILURE",
    "PROVIDER_CROSSING_AMBIGUOUS",
    "PROVIDER_REJECTED",
    "PROVIDER_RESPONSE_RECEIVED",
    "COMPLETED",
}
_COST_TYPES = {"reservation_release", "actual", "credit", "adjustment"}
_PROVENANCE_SCHEMA = "charitygraph.phase5.persisted-operational-provenance/v1"
_TIMESTAMP_FIELDS = {
    "created_at",
    "updated_at",
    "started_at",
    "completed_at",
    "submitted_at",
    "received_at",
    "recorded_at",
    "reserved_at",
    "expires_at",
    "lease_expires_at",
    "next_eligible_at",
    "send_started_at",
    "receipt_persisted_at",
    "request_started_at",
}

# This is deliberately an allowlist rather than a generic row serialiser.  In
# particular, payloads, prompts, evidence, response bodies, usage JSON and
# redacted error text are not inputs to the audit digests.
_PROVENANCE_FIELDS: dict[str, tuple[str, ...]] = {
    "run": (
        "run_id", "cohort_id", "run_kind", "status", "configuration_hash",
        "created_at", "started_at", "completed_at", "updated_at",
    ),
    "tasks": (
        "model_task_id", "run_id", "subject_id", "scope_id", "cohort_id",
        "task_type", "task_schema_id", "cache_key", "provider_id",
        "model_snapshot", "status", "attempt_count", "result_artifact_id",
        "error_class", "created_at", "updated_at",
    ),
    "task_attempts": (
        "task_run_id", "model_task_id", "attempt_number", "status",
        "provider_request_id", "provider_batch_id", "submitted_at", "started_at",
        "completed_at", "retryable", "pricing_snapshot_id", "fx_snapshot_id",
        "reservation_id", "result_artifact_id", "error_class",
    ),
    "provider_request_items": (
        "provider_request_item_id", "run_id", "model_task_id", "physical_attempt_id",
        "delivery_job_id", "provider_id", "model_route", "requested_delivery_mode",
        "effective_service_tier", "status", "provider_request_id", "provider_receipt_id",
        "created_at", "updated_at",
    ),
    "provider_request_attempts": (
        "delivery_attempt_id", "provider_request_item_id", "physical_attempt_id",
        "delivery_job_id", "attempt_ordinal", "attempt_class",
        "predecessor_attempt_id", "status", "provider_request_id", "provider_receipt_id",
        "failure_class", "created_at", "submitted_at", "completed_at", "updated_at",
    ),
    "physical_attempts": (
        "physical_attempt_id", "run_id", "subject_id", "delivery_mode", "status",
        "provider_request_id", "reservation_id", "created_at", "send_started_at",
        "receipt_persisted_at", "updated_at",
    ),
    "physical_attempt_members": ("physical_attempt_id", "model_task_id"),
    "provider_receipts": (
        "provider_receipt_id", "physical_attempt_id", "provider_request_id", "received_at",
    ),
    "delivery_jobs": (
        "delivery_job_id", "run_id", "provider_id", "model_route", "delivery_mode",
        "provider_batch_id", "status", "pricing_snapshot_id", "created_at",
        "submitted_at", "completed_at", "updated_at",
    ),
    "standard_transport_traces": (
        "physical_attempt_id", "delivery_attempt_id", "client_request_id",
        "request_body_sha256", "status", "request_started_at",
        "response_headers_received", "updated_at",
    ),
    "reservations": (
        "reservation_id", "cohort_id", "run_id", "reserved_amount", "reserved_aud",
        "accounting_currency", "status", "reserved_at", "expires_at", "updated_at",
    ),
    "reservation_tasks": ("reservation_id", "model_task_id"),
    "cost_entries": (
        "entry_key", "entry_hash", "cohort_id", "run_id", "task_run_id",
        "reservation_id", "entry_type", "paid_output_category", "provider_amount",
        "provider_currency", "accounting_amount", "aud_amount", "adjustment_direction",
        "pricing_snapshot_id", "fx_snapshot_id", "recorded_at",
    ),
}

_PROVENANCE_ID_FIELDS: dict[str, tuple[str, ...]] = {
    "run": ("run_id",),
    "tasks": ("model_task_id",),
    "task_attempts": ("task_run_id",),
    "provider_request_items": ("provider_request_item_id",),
    "provider_request_attempts": ("delivery_attempt_id",),
    "physical_attempts": ("physical_attempt_id",),
    "physical_attempt_members": ("physical_attempt_id", "model_task_id"),
    "provider_receipts": ("provider_receipt_id",),
    "delivery_jobs": ("delivery_job_id",),
    "standard_transport_traces": ("physical_attempt_id",),
    "reservations": ("reservation_id",),
    "reservation_tasks": ("reservation_id", "model_task_id"),
    "cost_entries": ("entry_key",),
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_sha256__": hashlib.sha256(value).hexdigest(), "length": len(value)}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersistedRunDiagnosticsError(f"{field} is missing")
    return value


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        raise PersistedRunDiagnosticsError(f"{field} is not an exact decimal")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PersistedRunDiagnosticsError(f"{field} is not an exact decimal") from None
    if not amount.is_finite() or amount < 0:
        raise PersistedRunDiagnosticsError(f"{field} is not a finite non-negative decimal")
    return amount


def _provenance_scalar(value: Any, field: str) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    raise PersistedRunDiagnosticsError(f"{field} is not safe operational provenance data")


def _provenance_row(group: str, row: Mapping[str, Any]) -> dict[str, Any]:
    fields = _PROVENANCE_FIELDS[group]
    return {field: _provenance_scalar(row.get(field), f"{group}.{field}") for field in fields if field in row}


def _provenance_manifest(
    *,
    run_id: str,
    schema_version: int,
    run: Mapping[str, Any],
    records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    grouped_rows: dict[str, Sequence[Mapping[str, Any]]] = {"run": (run,), **records}
    groups: dict[str, dict[str, Any]] = {}
    aggregate_material: list[dict[str, Any]] = []
    for group in _PROVENANCE_FIELDS:
        rows = grouped_rows.get(group, ())
        id_fields = _PROVENANCE_ID_FIELDS[group]
        projected_rows = [(_provenance_row(group, row), row) for row in rows]
        projected_rows.sort(key=lambda pair: (_canonical_bytes(pair[0]), tuple(str(pair[0].get(field) or "") for field in id_fields)))
        entries: list[dict[str, str]] = []
        for projected, _row in projected_rows:
            material = {
                "schema": _PROVENANCE_SCHEMA,
                "run_id": run_id,
                "group": group,
                "record": projected,
            }
            entries.append(
                {
                    "record_id": "|".join(str(projected.get(field) or "") for field in id_fields),
                    "digest": hashlib.sha256(_canonical_bytes(material)).hexdigest(),
                }
            )
        group_material = {
            "schema": _PROVENANCE_SCHEMA,
            "run_id": run_id,
            "schema_version": schema_version,
            "group": group,
            "records": entries,
        }
        group_digest = hashlib.sha256(_canonical_bytes(group_material)).hexdigest()
        groups[group] = {"count": len(entries), "digest": group_digest, "records": entries}
        aggregate_material.append({"group": group, "digest": group_digest, "count": len(entries)})
    aggregate_digest = hashlib.sha256(_canonical_bytes({
        "schema": _PROVENANCE_SCHEMA,
        "run_id": run_id,
        "schema_version": schema_version,
        "groups": aggregate_material,
    })).hexdigest()
    return {
        "schema": _PROVENANCE_SCHEMA,
        "scope": {"run_id": run_id, "schema_version": schema_version},
        "aggregate_digest": aggregate_digest,
        "groups": groups,
    }


def _canonical_record_order(records: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        name: sorted(
            (dict(row) for row in rows),
            key=lambda row: _canonical_bytes(_json_safe(row)),
        )
        for name, rows in records.items()
    }


class PersistedRunDiagnosticsAdapter:
    """Read one existing committed-catalogue run without changing its state."""

    def __init__(self, database_path: str | Path, run_id: str) -> None:
        self.database_path = Path(database_path)
        self.run_id = _text(run_id, "run_id")

    def _connect_read_only(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise PersistedRunDiagnosticsError("source SQLite database does not exist")
        wal_path = Path(str(self.database_path) + "-wal")
        if wal_path.exists() and wal_path.stat().st_size:
            raise PersistedRunDiagnosticsError("source SQLite database has an uncheckpointed WAL; snapshot is not safely immutable")
        uri = self.database_path.resolve().as_uri() + "?mode=ro&immutable=1"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5.0)
        except sqlite3.Error as exc:
            raise PersistedRunDiagnosticsError("source SQLite database cannot be opened read-only") from exc
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN")
        except sqlite3.Error as exc:
            connection.close()
            raise PersistedRunDiagnosticsError("source SQLite snapshot could not be started") from exc
        return connection

    @staticmethod
    def _require_tables(connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ({})".format(
                ",".join("?" for _ in _REQUIRED_TABLES)
            ),
            _REQUIRED_TABLES,
        ).fetchall()
        present = {str(row[0]) for row in rows}
        missing = sorted(set(_REQUIRED_TABLES) - present)
        if missing:
            raise PersistedRunDiagnosticsError(f"committed catalogue schema is missing tables: {', '.join(missing)}")

    @staticmethod
    def _rows(connection: sqlite3.Connection, table: str, where: str, parameters: Sequence[Any]) -> list[dict[str, Any]]:
        try:
            rows = connection.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY rowid", tuple(parameters)).fetchall()
        except sqlite3.Error as exc:
            raise PersistedRunDiagnosticsError(f"cannot read committed catalogue table {table}") from exc
        return [_row_dict(row) for row in rows]

    @staticmethod
    def _rows_in(connection: sqlite3.Connection, table: str, column: str, values: Sequence[str]) -> list[dict[str, Any]]:
        if not values:
            return []
        placeholders = ",".join("?" for _ in values)
        return PersistedRunDiagnosticsAdapter._rows(connection, table, f"{column} IN ({placeholders})", values)

    @staticmethod
    def _task_attempt_rows(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
        try:
            rows = connection.execute(
                "SELECT ta.* FROM task_attempts AS ta "
                "LEFT JOIN tasks AS t ON t.model_task_id=ta.model_task_id "
                "WHERE t.run_id=? OR t.model_task_id IS NULL ORDER BY ta.task_run_id",
                (run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistedRunDiagnosticsError("cannot read committed task attempts") from exc
        return [_row_dict(row) for row in rows]

    @staticmethod
    def _delivery_attempt_rows(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
        try:
            rows = connection.execute(
                "SELECT da.* FROM provider_request_attempts AS da "
                "LEFT JOIN provider_request_items AS i ON i.provider_request_item_id=da.provider_request_item_id "
                "WHERE i.run_id=? OR i.provider_request_item_id IS NULL ORDER BY da.delivery_attempt_id",
                (run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistedRunDiagnosticsError("cannot read committed delivery attempts") from exc
        return [_row_dict(row) for row in rows]

    @staticmethod
    def _provider_receipt_rows(connection: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
        try:
            rows = connection.execute(
                "SELECT pr.* FROM provider_receipts AS pr "
                "LEFT JOIN physical_attempts AS p ON p.physical_attempt_id=pr.physical_attempt_id "
                "WHERE p.run_id=? OR p.physical_attempt_id IS NULL ORDER BY pr.provider_receipt_id",
                (run_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            raise PersistedRunDiagnosticsError("cannot read committed provider receipts") from exc
        return [_row_dict(row) for row in rows]

    @staticmethod
    def _one(connection: sqlite3.Connection, table: str, where: str, parameters: Sequence[Any]) -> dict[str, Any] | None:
        rows = PersistedRunDiagnosticsAdapter._rows(connection, table, where, parameters)
        if len(rows) > 1:
            raise PersistedRunDiagnosticsError(f"ambiguous {table} identity")
        return rows[0] if rows else None

    @staticmethod
    def _schema_version(connection: sqlite3.Connection) -> int:
        rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        versions = [int(row[0]) for row in rows]
        if not versions or versions != list(range(1, max(versions) + 1)) or max(versions) != SUPPORTED_VERSION:
            raise PersistedRunDiagnosticsError("catalogue migration state is missing, gapped, or not clean HEAD v29")
        return max(versions)

    @staticmethod
    def _record_counts(records: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, int]:
        return {name: len(records[name]) for name in sorted(records)}

    @staticmethod
    def _stable_time(records: Mapping[str, Sequence[Mapping[str, Any]]], run: Mapping[str, Any]) -> str:
        timestamps: list[datetime] = []
        for row in [run, *[item for rows in records.values() for item in rows]]:
            for key in _TIMESTAMP_FIELDS:
                if key not in row or row[key] is None:
                    continue
                value = row[key]
                if value is None or (isinstance(value, str) and not value.strip()):
                    continue
                if not isinstance(value, str):
                    raise PersistedRunDiagnosticsError("durable observation timestamp is malformed")
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    raise PersistedRunDiagnosticsError("durable observation timestamp is malformed") from None
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise PersistedRunDiagnosticsError("durable observation timestamp is ambiguous")
                timestamps.append(parsed.astimezone(timezone.utc))
        if not timestamps:
            return ""
        return max(timestamps).isoformat(timespec="microseconds")

    @staticmethod
    def _validate_states(run: Mapping[str, Any], records: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        if run.get("status") not in _RUN_STATES:
            raise PersistedRunDiagnosticsError("unknown persisted run state")
        for row in records["tasks"]:
            if row.get("status") not in _TASK_STATES:
                raise PersistedRunDiagnosticsError("unknown persisted task state")
        for row in records["provider_request_items"]:
            if row.get("status") not in _ITEM_STATES:
                raise PersistedRunDiagnosticsError("unknown persisted request-item state")
        for row in records["provider_request_attempts"]:
            if row.get("status") not in _DELIVERY_ATTEMPT_STATES:
                raise PersistedRunDiagnosticsError("unknown persisted delivery-attempt state")
        for row in records["physical_attempts"]:
            if row.get("status") not in _PHYSICAL_STATES:
                raise PersistedRunDiagnosticsError("unknown persisted physical-attempt state")
        for row in records["standard_transport_traces"]:
            if row.get("status") not in _TRACE_STATES:
                raise PersistedRunDiagnosticsError("unknown persisted Standard transport state")
        for row in records["cost_entries"]:
            if row.get("entry_type") not in _COST_TYPES:
                raise PersistedRunDiagnosticsError("unknown persisted cost-entry type")

    @staticmethod
    def _validate_joins(records: Mapping[str, Sequence[Mapping[str, Any]]], run_id: str) -> None:
        tasks = {row["model_task_id"]: row for row in records["tasks"]}
        if len(tasks) != len(records["tasks"]):
            raise PersistedRunDiagnosticsError("duplicate persisted task identity")
        items = {row["provider_request_item_id"]: row for row in records["provider_request_items"]}
        if len(items) != len(records["provider_request_items"]):
            raise PersistedRunDiagnosticsError("duplicate persisted request-item identity")
        if {row["run_id"] for row in records["tasks"]} != ({run_id} if tasks else set()):
            raise PersistedRunDiagnosticsError("task run identity mismatch")
        if {row["run_id"] for row in records["provider_request_items"]} != ({run_id} if items else set()):
            raise PersistedRunDiagnosticsError("request-item run identity mismatch")
        item_by_task: dict[str, list[Mapping[str, Any]]] = {}
        for item in items.values():
            task_id = item.get("model_task_id")
            if task_id not in tasks:
                raise PersistedRunDiagnosticsError("orphan provider request item")
            item_by_task.setdefault(task_id, []).append(item)
        if set(item_by_task) != set(tasks) or any(len(rows) != 1 for rows in item_by_task.values()):
            raise PersistedRunDiagnosticsError("each persisted task must have exactly one request item")

        task_attempts = records["task_attempts"]
        if any(row.get("model_task_id") not in tasks for row in task_attempts):
            raise PersistedRunDiagnosticsError("orphan task attempt")
        attempts_by_task: dict[str, list[Mapping[str, Any]]] = {}
        for row in task_attempts:
            attempts_by_task.setdefault(row["model_task_id"], []).append(row)
        if set(attempts_by_task) != set(tasks) or any(len(rows) != 1 for rows in attempts_by_task.values()):
            raise PersistedRunDiagnosticsError("task attempt is missing or ambiguously repeated")

        physical = {row["physical_attempt_id"]: row for row in records["physical_attempts"]}
        jobs = {row["delivery_job_id"]: row for row in records["delivery_jobs"]}
        if any(row.get("run_id") != run_id for row in physical.values()):
            raise PersistedRunDiagnosticsError("physical attempt run identity mismatch")
        if any(row.get("run_id") != run_id for row in jobs.values()):
            raise PersistedRunDiagnosticsError("delivery job run identity mismatch")
        if any(row.get("physical_attempt_id") not in physical for row in items.values()):
            raise PersistedRunDiagnosticsError("request item has an orphan physical attempt")
        delivery_attempts = {row["delivery_attempt_id"]: row for row in records["provider_request_attempts"]}
        if len(delivery_attempts) != len(records["provider_request_attempts"]):
            raise PersistedRunDiagnosticsError("duplicate delivery-attempt identity")
        attempts_by_item: dict[str, list[Mapping[str, Any]]] = {}
        for row in delivery_attempts.values():
            if row.get("provider_request_item_id") not in items or row.get("physical_attempt_id") not in physical or row.get("delivery_job_id") not in jobs:
                raise PersistedRunDiagnosticsError("orphan delivery attempt")
            attempts_by_item.setdefault(row["provider_request_item_id"], []).append(row)
        if set(attempts_by_item) != set(items) or any(len(rows) != 1 for rows in attempts_by_item.values()):
            raise PersistedRunDiagnosticsError("delivery attempt is missing or ambiguously repeated")

        members = records["physical_attempt_members"]
        member_pairs = {(row["physical_attempt_id"], row["model_task_id"]) for row in members}
        if len(member_pairs) != len(members) or any(physical_id not in physical or task_id not in tasks for physical_id, task_id in member_pairs):
            raise PersistedRunDiagnosticsError("orphan or duplicate physical-attempt membership")
        for item in items.values():
            physical_id = item["physical_attempt_id"]
            if (physical_id, item["model_task_id"]) not in member_pairs:
                raise PersistedRunDiagnosticsError("physical attempt does not bind its request-item task")

        receipts_by_physical: dict[str, list[Mapping[str, Any]]] = {}
        for row in records["provider_receipts"]:
            physical_id = row.get("physical_attempt_id")
            if physical_id not in physical:
                raise PersistedRunDiagnosticsError("orphan provider receipt")
            receipts_by_physical.setdefault(physical_id, []).append(row)
        if any(len(rows) > 1 for rows in receipts_by_physical.values()):
            raise PersistedRunDiagnosticsError("duplicate provider receipt for a physical attempt")
        if len({row.get("provider_receipt_id") for row in records["provider_receipts"]}) != len(records["provider_receipts"]):
            raise PersistedRunDiagnosticsError("duplicate provider receipt identity")
        for item in items.values():
            attempt = attempts_by_item[item["provider_request_item_id"]][0]
            receipts = receipts_by_physical.get(item["physical_attempt_id"], [])
            if item["status"] == "completed" and len(receipts) != 1:
                raise PersistedRunDiagnosticsError("completed request item has an inconsistent receipt")
            if item["status"] == "completed" and item.get("provider_receipt_id") != receipts[0].get("provider_receipt_id"):
                raise PersistedRunDiagnosticsError("completed request item receipt identity is inconsistent")
            if item["status"] != "completed" and len(receipts) > 0:
                raise PersistedRunDiagnosticsError("non-completed request item has a provider receipt")
            if attempt.get("provider_receipt_id") and (not receipts or receipts[0].get("provider_receipt_id") != attempt["provider_receipt_id"]):
                raise PersistedRunDiagnosticsError("delivery attempt receipt binding is inconsistent")

        reservations = {row["reservation_id"]: row for row in records["reservations"]}
        if len(reservations) != len(records["reservations"]):
            raise PersistedRunDiagnosticsError("duplicate reservation identity")
        reservation_tasks: dict[str, set[str]] = {}
        for row in records["reservation_tasks"]:
            if row.get("reservation_id") not in reservations or row.get("model_task_id") not in tasks:
                raise PersistedRunDiagnosticsError("orphan reservation-task binding")
            reservation_tasks.setdefault(row["model_task_id"], set()).add(row["reservation_id"])
        if len({(row.get("reservation_id"), row.get("model_task_id")) for row in records["reservation_tasks"]}) != len(records["reservation_tasks"]):
            raise PersistedRunDiagnosticsError("duplicate reservation-task identity")
        if set(reservation_tasks) != set(tasks) or any(len(ids) != 1 for ids in reservation_tasks.values()):
            raise PersistedRunDiagnosticsError("task reservation is missing or ambiguously repeated")
        if len({row.get("entry_key") for row in records["cost_entries"]}) != len(records["cost_entries"]):
            raise PersistedRunDiagnosticsError("duplicate cost-entry identity")
        if any(row.get("reservation_id") not in reservations for row in records["cost_entries"]):
            raise PersistedRunDiagnosticsError("cost entry refers to an unknown reservation")
        if any(row.get("cohort_id") != reservations[row["reservation_id"]].get("cohort_id") for row in records["cost_entries"]):
            raise PersistedRunDiagnosticsError("cost entry cohort does not match its reservation")
        task_run_ids = {row["task_run_id"] for row in task_attempts}
        if any(row.get("task_run_id") not in task_run_ids for row in records["cost_entries"] if row.get("task_run_id") is not None):
            raise PersistedRunDiagnosticsError("cost entry refers to an orphan task attempt")

        traces = {row["physical_attempt_id"]: row for row in records["standard_transport_traces"]}
        if len(traces) != len(records["standard_transport_traces"]):
            raise PersistedRunDiagnosticsError("duplicate Standard transport trace")
        if set(traces) != set(physical):
            raise PersistedRunDiagnosticsError("Standard transport trace coverage is incomplete or orphaned")
        for row in records["standard_transport_traces"]:
            attempt = delivery_attempts.get(row.get("delivery_attempt_id"))
            if attempt is None or attempt.get("physical_attempt_id") != row["physical_attempt_id"]:
                raise PersistedRunDiagnosticsError("Standard transport trace binding is inconsistent")

        for row in records["cost_entries"]:
            _decimal(row.get("accounting_amount", row.get("aud_amount")), "cost entry accounting amount")
            currency = row.get("accounting_currency") or "AUD"
            if not isinstance(currency, str) or len(currency) != 3 or currency != currency.upper() or not currency.isalpha():
                raise PersistedRunDiagnosticsError("cost entry accounting currency is invalid")
        for row in records["reservations"]:
            _decimal(row.get("reserved_amount", row.get("reserved_aud")), "reservation amount")
            currency = row.get("accounting_currency") or "AUD"
            if not isinstance(currency, str) or len(currency) != 3 or currency != currency.upper() or not currency.isalpha():
                raise PersistedRunDiagnosticsError("reservation accounting currency is invalid")

    @staticmethod
    def _diagnostic_status(item: Mapping[str, Any], attempt: Mapping[str, Any], physical: Mapping[str, Any], trace: Mapping[str, Any]) -> str:
        item_state = item["status"]
        trace_state = trace["status"]
        if item_state == "completed":
            return "completed"
        if item_state == "send_ambiguous" or attempt["status"] == "held" or physical["status"] == "held" or trace_state == "PROVIDER_CROSSING_AMBIGUOUS":
            return "ambiguous"
        if item_state == "failed":
            if trace_state == "LOCAL_PRE_SEND_FAILURE" or attempt.get("failure_class") == "pre_send_validation":
                return "failed_pre_send"
            return "failed_terminal"
        if item_state in {"prepared", "submitted", "in_progress"}:
            return "in_progress"
        if item_state in {"expired", "cancelled", "held"}:
            return item_state
        raise PersistedRunDiagnosticsError("cannot classify persisted request-item state")

    @staticmethod
    def _cost_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in rows:
            entry_type = row["entry_type"]
            if entry_type == "adjustment":
                direction = row.get("adjustment_direction")
                if direction not in {"credit", "debit"}:
                    raise PersistedRunDiagnosticsError("adjustment cost entry has no unambiguous direction")
                entry_type = f"adjustment_{direction}"
            result.append(
                {
                    "entry_key": row["entry_key"],
                    "reservation_id": row["reservation_id"],
                    "entry_type": entry_type,
                    "accounting_amount": str(_decimal(row.get("accounting_amount", row.get("aud_amount")), "cost entry accounting amount")),
                    "accounting_currency": row.get("accounting_currency") or "AUD",
                }
            )
        return result

    def read_snapshot(self) -> PersistedRunDiagnosticSnapshot:
        connection = self._connect_read_only()
        try:
            self._require_tables(connection)
            schema_version = self._schema_version(connection)
            run = self._one(connection, "runs", "run_id=?", (self.run_id,))
            if run is None:
                raise PersistedRunDiagnosticsError("requested persisted run does not exist")

            task_rows = self._rows(connection, "tasks", "run_id=?", (self.run_id,))
            task_ids = [row["model_task_id"] for row in task_rows]
            task_attempt_rows = self._task_attempt_rows(connection, self.run_id)
            item_rows = self._rows(connection, "provider_request_items", "run_id=?", (self.run_id,))
            item_ids = [row["provider_request_item_id"] for row in item_rows]
            delivery_attempt_rows = self._delivery_attempt_rows(connection, self.run_id)
            physical_ids = [row["physical_attempt_id"] for row in item_rows if row.get("physical_attempt_id")]
            physical_rows = self._rows_in(connection, "physical_attempts", "physical_attempt_id", physical_ids)
            physical_id_values = [row["physical_attempt_id"] for row in physical_rows]
            member_rows = self._rows_in(connection, "physical_attempt_members", "physical_attempt_id", physical_id_values)
            receipt_rows = self._provider_receipt_rows(connection, self.run_id)
            job_ids = sorted({row["delivery_job_id"] for row in item_rows if row.get("delivery_job_id")})
            job_rows = self._rows_in(connection, "delivery_jobs", "delivery_job_id", job_ids)
            trace_rows = self._rows_in(connection, "standard_transport_traces", "physical_attempt_id", physical_id_values)
            reservation_rows = self._rows(connection, "budget_reservations", "run_id=?", (self.run_id,))
            reservation_ids = [row["reservation_id"] for row in reservation_rows]
            reservation_task_rows = self._rows_in(connection, "reservation_tasks", "reservation_id", reservation_ids)
            cost_rows = self._rows(connection, "cost_entries", "run_id=?", (self.run_id,))
            records = {
                "tasks": task_rows,
                "task_attempts": task_attempt_rows,
                "provider_request_items": item_rows,
                "provider_request_attempts": delivery_attempt_rows,
                "physical_attempts": physical_rows,
                "physical_attempt_members": member_rows,
                "provider_receipts": receipt_rows,
                "delivery_jobs": job_rows,
                "standard_transport_traces": trace_rows,
                "reservations": reservation_rows,
                "reservation_tasks": reservation_task_rows,
                "cost_entries": cost_rows,
            }
            records = _canonical_record_order(records)
            self._validate_states(run, records)
            self._validate_joins(records, self.run_id)

            items = {row["provider_request_item_id"]: row for row in item_rows}
            delivery_attempts = {row["provider_request_item_id"]: row for row in delivery_attempt_rows}
            physical = {row["physical_attempt_id"]: row for row in physical_rows}
            traces = {row["physical_attempt_id"]: row for row in trace_rows}
            results: list[dict[str, Any]] = []
            for item_id in sorted(items):
                item = items[item_id]
                attempt = delivery_attempts[item_id]
                physical_row = physical[item["physical_attempt_id"]]
                trace = traces[item["physical_attempt_id"]]
                crossed = int(
                    trace["status"] in {
                        "CROSSING_STARTED",
                        "PROVIDER_CROSSING_AMBIGUOUS",
                        "PROVIDER_REJECTED",
                        "PROVIDER_RESPONSE_RECEIVED",
                        "COMPLETED",
                    }
                    or attempt.get("submitted_at") is not None
                )
                task = next(row for row in task_rows if row["model_task_id"] == item["model_task_id"])
                results.append(
                    {
                        "item_id": item_id,
                        "subject_id": _text(task.get("subject_id"), f"task {item['model_task_id']} subject_id"),
                        "scope_id": _text(task.get("scope_id"), f"task {item['model_task_id']} scope_id"),
                        "status": self._diagnostic_status(item, attempt, physical_row, trace),
                        "provider_posts": crossed,
                        "stop_campaign": bool(item["status"] in {"send_ambiguous", "held"} or trace["status"] == "PROVIDER_CROSSING_AMBIGUOUS"),
                    }
                )

            ambiguous = any(result["status"] == "ambiguous" for result in results)
            systemic = any(result["status"] in {"failed_pre_send", "failed_terminal"} for result in results) and run["status"] in {"failed", "held"}
            stopped = run["status"] in {"failed", "cancelled", "held"} or ambiguous or systemic
            classification = "ambiguous" if ambiguous else "systemic" if systemic else "requested" if run["status"] == "cancelled" else "none"
            stable_time = self._stable_time(records, run)
            snapshot_material = _json_safe({"run": run, "records": records})
            snapshot_hash = hashlib.sha256(_canonical_bytes(snapshot_material)).hexdigest()
            if not stable_time:
                stable_time = f"evidence:{snapshot_hash}"
            provenance_digests = _provenance_manifest(
                run_id=self.run_id,
                schema_version=schema_version,
                run=run,
                records=records,
            )
            source_ref = str(self.database_path.resolve())
            run_ref = f"sqlite:{source_ref}:run:{self.run_id}:snapshot:{snapshot_hash}"
            ledger_ref = f"sqlite:{source_ref}:ledger:{snapshot_hash}:observed:{stable_time}"
            run_record = {
                "run_id": self.run_id,
                "provenance": {
                    "run_record_ref": run_ref,
                    "ledger_snapshot_ref": ledger_ref,
                    "operational_digest_manifest": provenance_digests,
                    "evidence_scope": "local_persisted_diagnostic_only; provider_evidence_not_claimed",
                },
                "results": results,
                "planned_item_count": len(task_rows),
                "provider_posts": sum(result["provider_posts"] for result in results),
                "stop": {"campaign_stopped": stopped, "classification": classification},
            }
            ledger_snapshot = {
                "tasks": [
                    {"task_id": row["model_task_id"], "status": row["status"]} for row in task_rows
                ],
                "attempts": [
                    {"attempt_id": row["task_run_id"], "task_id": row["model_task_id"], "status": row["status"]}
                    for row in task_attempt_rows
                ],
                "receipts": [
                    {"receipt_id": row["provider_receipt_id"], "physical_attempt_id": row["physical_attempt_id"]}
                    for row in receipt_rows
                ],
                "reservations": [
                    {
                        "reservation_id": row["reservation_id"],
                        "reserved_aud": row.get("reserved_amount", row.get("reserved_aud")),
                        "currency": row.get("accounting_currency") or "AUD",
                        "status": row["status"],
                    }
                    for row in reservation_rows
                ],
                "cost_entries": self._cost_rows(cost_rows),
            }
            return PersistedRunDiagnosticSnapshot(
                database_path=source_ref,
                run_id=self.run_id,
                schema_version=schema_version,
                snapshot_observed_at=stable_time,
                record_counts=self._record_counts(records),
                snapshot_hash=snapshot_hash,
                run_record=run_record,
                ledger_snapshot=ledger_snapshot,
                provenance_digests=provenance_digests,
            )
        except sqlite3.Error as exc:
            raise PersistedRunDiagnosticsError("persisted run snapshot failed closed") from exc
        finally:
            connection.close()

    def project(self, *, restart_baseline: PersistedRunDiagnosticSnapshot | None = None) -> DiagnosticProjection:
        snapshot = self.read_snapshot()
        run_record = copy.deepcopy(dict(snapshot.run_record))
        if restart_baseline is not None:
            if restart_baseline.run_id != snapshot.run_id or restart_baseline.snapshot_hash != snapshot.snapshot_hash:
                raise PersistedRunDiagnosticsError("restart no-resend evidence changed the durable snapshot")
            run_record["restart_no_resend"] = True
        return project_run_diagnostics(run_record, copy.deepcopy(dict(snapshot.ledger_snapshot)))


__all__ = [
    "PersistedRunDiagnosticsError",
    "PersistedRunDiagnosticSnapshot",
    "PersistedRunDiagnosticsAdapter",
]
