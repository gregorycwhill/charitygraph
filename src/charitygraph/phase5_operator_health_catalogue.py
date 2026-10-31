"""Read-only wiring from the persisted Phase-5 catalogue to operator health.

The adapter is intentionally narrower than the writable runtime catalogue.  It
accepts an explicit SQLite path or connection, an explicit run selection, and
explicit timezone-aware diagnostic/window timestamps.  It only issues bounded
parameterised reads over the existing operational tables, projects safe
diagnostic fields, and delegates arithmetic and fail-closed semantics to
``phase5_operator_health``.  It never migrates, writes, acquires, contacts a
provider, or retains payloads.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .phase5_operator_health import (
    OperatorHealthError,
    OperatorHealthProjection,
    OperatorHealthSnapshot,
    project_operator_health,
)
from .runtime.migrations import SUPPORTED_VERSION


class Phase5CatalogueAdapterError(OperatorHealthError):
    """Raised for an invalid adapter request, not for incomplete evidence."""


_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "schema_migrations": ("version",),
    "runs": ("run_id", "status", "created_at", "updated_at"),
    "tasks": ("model_task_id", "run_id", "subject_id", "scope_id", "status", "created_at", "updated_at"),
    "task_attempts": ("task_run_id", "model_task_id", "attempt_number", "status", "submitted_at", "started_at", "completed_at"),
    "budget_reservations": ("reservation_id", "run_id", "status", "reserved_at", "updated_at"),
    "cost_entries": ("entry_key", "run_id", "reservation_id", "entry_type", "recorded_at"),
    "physical_attempts": ("physical_attempt_id", "run_id", "subject_id", "status", "created_at", "updated_at"),
    "provider_receipts": ("provider_receipt_id", "physical_attempt_id", "received_at"),
    "delivery_jobs": ("delivery_job_id", "run_id", "status", "created_at", "updated_at"),
    "provider_request_items": ("provider_request_item_id", "run_id", "model_task_id", "status", "created_at", "updated_at"),
    "provider_request_attempts": ("delivery_attempt_id", "provider_request_item_id", "status", "attempt_ordinal", "created_at", "updated_at"),
}

_SAFE_FIELDS: dict[str, tuple[str, ...]] = {
    "runs": ("run_id", "status", "created_at", "started_at", "completed_at", "updated_at"),
    "tasks": ("model_task_id", "run_id", "subject_id", "scope_id", "status", "attempt_count", "created_at", "updated_at"),
    "task_attempts": ("task_run_id", "model_task_id", "attempt_number", "status", "provider_request_id", "provider_batch_id", "submitted_at", "started_at", "completed_at", "reservation_id"),
    "requests": ("provider_request_item_id", "run_id", "model_task_id", "physical_attempt_id", "delivery_job_id", "provider_id", "model_route", "status", "provider_request_id", "provider_receipt_id", "created_at", "scheduled_at", "started_at", "submitted_at", "send_started_at", "received_at", "completed_at", "updated_at"),
    "attempts": ("delivery_attempt_id", "provider_request_item_id", "physical_attempt_id", "delivery_job_id", "attempt_ordinal", "predecessor_attempt_id", "status", "provider_request_id", "provider_receipt_id", "created_at", "submitted_at", "completed_at", "updated_at"),
    "jobs": ("delivery_job_id", "run_id", "provider_id", "model_route", "delivery_mode", "status", "pricing_snapshot_id", "created_at", "submitted_at", "completed_at", "updated_at"),
    "physical": ("physical_attempt_id", "run_id", "subject_id", "status", "provider_request_id", "reservation_id", "created_at", "send_started_at", "receipt_persisted_at", "updated_at"),
    "receipts": ("provider_receipt_id", "physical_attempt_id", "provider_request_id", "received_at"),
    "reservations": ("reservation_id", "cohort_id", "run_id", "reserved_amount", "reserved_aud", "accounting_currency", "status", "reserved_at", "expires_at", "updated_at"),
    "cost_entries": ("entry_key", "run_id", "task_run_id", "reservation_id", "entry_type", "provider_amount", "provider_currency", "accounting_amount", "aud_amount", "adjustment_direction", "accounting_currency", "pricing_snapshot_id", "fx_snapshot_id", "recorded_at"),
}

_USAGE_REQUIRED_FIELDS = ("input_tokens", "output_tokens")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise Phase5CatalogueAdapterError(f"{field} must be an explicit ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Phase5CatalogueAdapterError(f"{field} must be an explicit ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Phase5CatalogueAdapterError(f"{field} must include a timezone")


def _safe_row(row: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    return {field: row[field] for field in fields if field in row and row[field] is not None}


def _valid_usage_count(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, str):
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
            return False
        return parsed >= 0 and str(parsed) == value
    return False


def _usage_row(row: Mapping[str, Any], issues: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    projected = _safe_row(row, _SAFE_FIELDS["receipts"])
    raw = row.get("usage_json")
    if raw is None:
        projected["usage_coverage_state"] = "missing"
        projected["usage_coverage_reason"] = "MISSING_USAGE_JSON"
        issues.append({"code": "MISSING_USAGE_JSON", "severity": "warning", "message": f"receipt {identifier} usage_json is missing"})
        return projected
    try:
        usage = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        projected["usage_coverage_state"] = "ambiguous"
        projected["usage_coverage_reason"] = "INVALID_USAGE_JSON"
        issues.append({"code": "INVALID_USAGE_JSON", "severity": "error", "message": f"receipt {identifier} usage_json is not valid structured JSON"})
        return projected
    if not isinstance(usage, Mapping):
        projected["usage_coverage_state"] = "ambiguous"
        projected["usage_coverage_reason"] = "INVALID_USAGE_SHAPE"
        issues.append({"code": "INVALID_USAGE_SHAPE", "severity": "error", "message": f"receipt {identifier} usage_json is not an object"})
        return projected
    # Usage is the only receipt material needed by the diagnostic.  Do not
    # retain arbitrary provider response fields, even transiently in the
    # structured snapshot.
    invalid_fields = [
        name for name in _USAGE_REQUIRED_FIELDS
        if name in usage and not _valid_usage_count(usage[name])
    ]
    for name in invalid_fields:
        issues.append({"code": "INVALID_PROVIDER_USAGE", "severity": "error", "message": f"receipt {identifier} has an invalid {name} type"})
    projected["usage"] = {name: usage[name] for name in _USAGE_REQUIRED_FIELDS if name in usage and name not in invalid_fields}
    missing_fields = [name for name in _USAGE_REQUIRED_FIELDS if name not in usage]
    if invalid_fields:
        projected["usage_coverage_state"] = "ambiguous"
        projected["usage_coverage_reason"] = "INVALID_PROVIDER_USAGE"
    elif missing_fields:
        projected["usage_coverage_state"] = "missing"
        projected["usage_coverage_reason"] = "MISSING_REQUIRED_TOKEN_COUNTS"
        issues.append({"code": "MISSING_REQUIRED_TOKEN_COUNTS", "severity": "warning", "message": f"receipt {identifier} lacks required token counts"})
    return projected


@dataclass(frozen=True)
class Phase5CatalogueSnapshot:
    """Safe, bounded rows and explicit coverage from one catalogue read."""

    catalogue_id: str
    schema_version: int | None
    run_ids_requested: tuple[str, ...]
    run_ids_found: tuple[str, ...]
    as_of: str
    reporting_window_start: str
    reporting_window_end: str
    source_id: str
    source_version: str
    evidence_basis: str
    coverage: Mapping[str, Any]
    records: Mapping[str, tuple[Mapping[str, Any], ...]]
    operator_snapshot: OperatorHealthSnapshot

    def as_dict(self) -> dict[str, Any]:
        return {
            "catalogue_id": self.catalogue_id,
            "schema_version": self.schema_version,
            "run_ids_requested": list(self.run_ids_requested),
            "run_ids_found": list(self.run_ids_found),
            "as_of": self.as_of,
            "reporting_window": {"start": self.reporting_window_start, "end": self.reporting_window_end},
            "source_lineage": {"source_id": self.source_id, "source_version": self.source_version, "evidence_basis": self.evidence_basis},
            "coverage": self.coverage,
            "record_counts": {name: len(rows) for name, rows in self.records.items()},
        }


@dataclass(frozen=True)
class Phase5CatalogueProjection:
    """Canonical catalogue-integrated diagnostic and its identities."""

    snapshot: Phase5CatalogueSnapshot
    operator_health: OperatorHealthProjection
    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {"document": json.loads(self.canonical_json.decode("utf-8")), "canonical_json": self.canonical_json, "sha256": self.sha256}


class Phase5OperatorHealthCatalogueAdapter:
    """Read selected persisted Phase-5 rows without using the writable catalogue API."""

    def __init__(
        self,
        catalogue: str | Path | sqlite3.Connection,
        *,
        run_ids: Sequence[str],
        as_of: str,
        reporting_window_start: str,
        reporting_window_end: str,
        source_id: str | None = None,
        evidence_basis: str = "persisted Phase-5 runtime catalogue; provider evidence not claimed",
        ledger: Mapping[str, Any] | None = None,
        stalled_after_seconds: int | None = None,
    ) -> None:
        if isinstance(run_ids, (str, bytes, bytearray)) or not run_ids:
            raise Phase5CatalogueAdapterError("run_ids must be a non-empty explicit sequence")
        normalized = tuple(str(item) for item in run_ids)
        if any(not item.strip() for item in normalized) or len(set(normalized)) != len(normalized):
            raise Phase5CatalogueAdapterError("run_ids must contain unique non-empty identifiers")
        for field, value in (("as_of", as_of), ("reporting_window_start", reporting_window_start), ("reporting_window_end", reporting_window_end)):
            _validate_timestamp(value, field)
        start_time = datetime.fromisoformat(reporting_window_start.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(reporting_window_end.replace("Z", "+00:00"))
        if start_time >= end_time:
            raise Phase5CatalogueAdapterError("reporting window must have positive elapsed time")
        if not isinstance(evidence_basis, str) or not evidence_basis.strip():
            raise Phase5CatalogueAdapterError("evidence_basis must be non-empty")
        if source_id is not None and (not isinstance(source_id, str) or not source_id.strip()):
            raise Phase5CatalogueAdapterError("source_id must be non-empty when supplied")
        if not isinstance(catalogue, (str, Path, sqlite3.Connection)):
            raise Phase5CatalogueAdapterError("catalogue must be an explicit SQLite path or connection")
        self.catalogue = catalogue
        self.run_ids = normalized
        self.as_of = as_of
        self.reporting_window_start = reporting_window_start
        self.reporting_window_end = reporting_window_end
        self.source_id = source_id
        self.evidence_basis = evidence_basis
        self.ledger = dict(ledger or {})
        self.stalled_after_seconds = stalled_after_seconds

    def _open(self) -> tuple[sqlite3.Connection, bool, str]:
        if isinstance(self.catalogue, sqlite3.Connection):
            connection = self.catalogue
            owned = False
            catalogue_id = "sqlite:connection"
        else:
            path = Path(self.catalogue)
            if not path.is_file():
                raise Phase5CatalogueAdapterError("source SQLite database does not exist")
            wal_path = Path(str(path) + "-wal")
            if wal_path.exists() and wal_path.stat().st_size:
                raise Phase5CatalogueAdapterError("source SQLite database has an uncheckpointed WAL")
            try:
                connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5.0)
            except sqlite3.Error as exc:
                raise Phase5CatalogueAdapterError("source SQLite database cannot be opened read-only") from exc
            owned = True
            catalogue_id = str(path.resolve())
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as exc:
            if owned:
                connection.close()
            raise Phase5CatalogueAdapterError("SQLite connection could not be constrained to read-only operation") from exc
        return connection, owned, catalogue_id

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        try:
            return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        except sqlite3.Error as exc:
            raise Phase5CatalogueAdapterError(f"cannot inspect catalogue table {table}") from exc

    @staticmethod
    def _select(connection: sqlite3.Connection, table: str, column: str, run_ids: Sequence[str], order: str) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in run_ids)
        try:
            rows = connection.execute(f"SELECT * FROM {table} WHERE {column} IN ({placeholders}) ORDER BY {order}", tuple(run_ids)).fetchall()
        except sqlite3.Error as exc:
            raise Phase5CatalogueAdapterError(f"cannot read bounded catalogue table {table}") from exc
        return [{key: row[key] for key in row.keys()} for row in rows]

    @staticmethod
    def _select_joined(connection: sqlite3.Connection, sql: str, run_ids: Sequence[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in run_ids)
        try:
            rows = connection.execute(sql.format(placeholders=placeholders), tuple(run_ids)).fetchall()
        except sqlite3.Error as exc:
            raise Phase5CatalogueAdapterError("cannot read bounded joined catalogue records") from exc
        return [{key: row[key] for key in row.keys()} for row in rows]

    def read_snapshot(self) -> Phase5CatalogueSnapshot:
        connection, owned, catalogue_id = self._open()
        try:
            missing_tables: list[str] = []
            missing_columns: dict[str, list[str]] = {}
            table_columns: dict[str, set[str]] = {}
            for table, required in _TABLE_COLUMNS.items():
                columns = self._columns(connection, table)
                table_columns[table] = columns
                if not columns:
                    missing_tables.append(table)
                else:
                    absent = sorted(set(required) - columns)
                    if absent:
                        missing_columns[table] = absent
            schema_version: int | None = None
            if "schema_migrations" not in missing_tables:
                try:
                    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
                    schema_version = None if row is None or row[0] is None else int(row[0])
                except (sqlite3.Error, TypeError, ValueError):
                    schema_version = None
            schema_issues: list[dict[str, Any]] = []
            if missing_tables or missing_columns:
                schema_issues.append({"code": "INCOMPLETE_CATALOGUE_SCHEMA", "severity": "error", "message": "required persisted Phase-5 tables or columns are missing"})
            if schema_version != SUPPORTED_VERSION:
                schema_issues.append({"code": "UNSUPPORTED_CATALOGUE_SCHEMA", "severity": "error", "message": f"catalogue schema version {schema_version!r} is not supported"})

            requested_source_id = self.source_id
            source_id = requested_source_id or (f"sqlite:{catalogue_id}" if catalogue_id != "sqlite:connection" else catalogue_id)
            lineage_issues: list[dict[str, Any]] = []
            if requested_source_id is None:
                lineage_issues.append({"code": "DERIVED_CATALOGUE_SOURCE_ID", "severity": "warning", "message": "source_id was not supplied; catalogue identity is used as the source boundary"})

            raw: dict[str, list[dict[str, Any]]] = {name: [] for name in ("runs", "jobs", "requests", "tasks", "attempts", "task_attempts", "physical", "receipts", "reservations", "cost_entries")}
            parse_issues: list[dict[str, Any]] = []
            if not schema_issues:
                raw["runs"] = self._select(connection, "runs", "run_id", self.run_ids, "run_id")
                raw["tasks"] = self._select(connection, "tasks", "run_id", self.run_ids, "model_task_id")
                raw["jobs"] = self._select(connection, "delivery_jobs", "run_id", self.run_ids, "delivery_job_id")
                raw["requests"] = self._select(connection, "provider_request_items", "run_id", self.run_ids, "provider_request_item_id")
                raw["physical"] = self._select(connection, "physical_attempts", "run_id", self.run_ids, "physical_attempt_id")
                raw["reservations"] = self._select(connection, "budget_reservations", "run_id", self.run_ids, "reservation_id")
                raw["cost_entries"] = self._select(connection, "cost_entries", "run_id", self.run_ids, "entry_key")
                raw["attempts"] = self._select_joined(connection, "SELECT a.*, i.run_id AS run_id FROM provider_request_attempts AS a JOIN provider_request_items AS i ON i.provider_request_item_id=a.provider_request_item_id WHERE i.run_id IN ({placeholders}) ORDER BY a.delivery_attempt_id", self.run_ids)
                raw["receipts"] = self._select_joined(connection, "SELECT r.*, p.run_id AS run_id FROM provider_receipts AS r JOIN physical_attempts AS p ON p.physical_attempt_id=r.physical_attempt_id WHERE p.run_id IN ({placeholders}) ORDER BY r.provider_receipt_id", self.run_ids)
                raw["task_attempts"] = self._select_joined(connection, "SELECT a.*, t.run_id AS run_id FROM task_attempts AS a JOIN tasks AS t ON t.model_task_id=a.model_task_id WHERE t.run_id IN ({placeholders}) ORDER BY a.task_run_id", self.run_ids)

            found = tuple(sorted(str(row["run_id"]) for row in raw["runs"] if row.get("run_id") is not None))
            missing_runs = sorted(set(self.run_ids) - set(found))
            selection_issues = []
            if missing_runs:
                selection_issues.append({"code": "MISSING_REQUESTED_RUN", "severity": "error", "message": f"requested run records are absent: {', '.join(missing_runs)}"})

            records: dict[str, tuple[Mapping[str, Any], ...]] = {}
            # Task attempts and delivery attempts share one diagnostic group.
            task_attempt_rows = raw["task_attempts"]
            delivery_attempt_rows = raw["attempts"]
            records["runs"] = tuple(_safe_row(row, _SAFE_FIELDS["runs"]) for row in raw["runs"])
            records["tasks"] = tuple(_safe_row(row, _SAFE_FIELDS["tasks"]) for row in raw["tasks"])
            records["jobs"] = tuple(_safe_row(row, _SAFE_FIELDS["jobs"]) for row in raw["jobs"])
            delivery_by_item = {str(row.get("provider_request_item_id")): row for row in delivery_attempt_rows}
            physical_by_id = {str(row.get("physical_attempt_id")): row for row in raw["physical"]}
            receipt_by_physical = {str(row.get("physical_attempt_id")): row for row in raw["receipts"]}
            enriched_requests: list[dict[str, Any]] = []
            for row in raw["requests"]:
                enriched = dict(row)
                attempt = delivery_by_item.get(str(row.get("provider_request_item_id")))
                physical = physical_by_id.get(str(row.get("physical_attempt_id")))
                receipt = receipt_by_physical.get(str(row.get("physical_attempt_id")))
                if attempt is not None:
                    for field_name in ("submitted_at", "completed_at"):
                        if attempt.get(field_name) is not None:
                            enriched[field_name] = attempt[field_name]
                if physical is not None and physical.get("send_started_at") is not None:
                    enriched["send_started_at"] = physical["send_started_at"]
                if receipt is not None and receipt.get("received_at") is not None:
                    enriched["received_at"] = receipt["received_at"]
                enriched_requests.append(enriched)
            records["requests"] = tuple(_safe_row(row, _SAFE_FIELDS["requests"]) for row in enriched_requests)
            records["attempts"] = tuple(_safe_row(row, _SAFE_FIELDS["attempts"]) for row in delivery_attempt_rows)
            records["task_attempts"] = tuple(_safe_row(row, _SAFE_FIELDS["task_attempts"]) for row in task_attempt_rows)
            records["physical"] = tuple(_safe_row(row, _SAFE_FIELDS["physical"]) for row in raw["physical"])
            records["receipts"] = tuple(_usage_row(row, parse_issues, str(row.get("provider_receipt_id") or "unknown")) for row in raw["receipts"])
            records["reservations"] = tuple(_safe_row(row, _SAFE_FIELDS["reservations"]) for row in raw["reservations"])
            records["cost_entries"] = tuple(_safe_row(row, _SAFE_FIELDS["cost_entries"]) for row in raw["cost_entries"])

            material = {"schema_version": schema_version, "run_ids": list(found), "as_of": self.as_of, "window": [self.reporting_window_start, self.reporting_window_end], "records": records}
            digest = hashlib.sha256(_canonical_bytes(material)).hexdigest()
            source_version = self.source_id and f"{self.source_id}:snapshot:{digest}" or f"sqlite-v{schema_version}:{digest}"
            decorated = {
                name: tuple({**dict(row), "source_id": source_id, "source_version": source_version, "evidence_basis": self.evidence_basis} for row in rows)
                for name, rows in records.items()
            }
            coverage_issues = sorted(schema_issues + selection_issues + lineage_issues + parse_issues, key=lambda item: (str(item["severity"]), str(item["code"]), str(item["message"])))
            coverage_state = "unknown" if schema_issues else "incomplete" if coverage_issues else "complete"
            coverage = {
                "state": coverage_state,
                "schema": {"state": "supported" if not schema_issues else "unknown", "version": schema_version, "supported_version": SUPPORTED_VERSION, "missing_tables": sorted(missing_tables), "missing_columns": missing_columns},
                "run_selection": {"requested": list(self.run_ids), "found": list(found), "missing": missing_runs, "bounded": True},
                "source_lineage": {"source_id": source_id, "source_version": source_version, "evidence_basis": self.evidence_basis, "state": "explicit" if requested_source_id else "catalogue_derived"},
                "issues": coverage_issues,
            }
            operator_snapshot = OperatorHealthSnapshot(
                as_of=self.as_of,
                source_id=source_id,
                source_version=source_version,
                evidence_basis=self.evidence_basis,
                reporting_window_start=self.reporting_window_start,
                reporting_window_end=self.reporting_window_end,
                project_id="phase5-runtime-catalogue",
                ledger_source_id=self.ledger.get("source_id"),
                ledger_version=self.ledger.get("version"),
                ledger_as_of=self.ledger.get("as_of"),
                ledger_stale_after=self.ledger.get("stale_after"),
                ledger_complete=self.ledger.get("complete"),
                stalled_after_seconds=self.stalled_after_seconds,
                runs=decorated["runs"], jobs=decorated["jobs"], requests=decorated["requests"],
                tasks=decorated["tasks"], attempts=decorated["attempts"], receipts=decorated["receipts"],
                reservations=decorated["reservations"], cost_entries=decorated["cost_entries"],
            )
            return Phase5CatalogueSnapshot(
                catalogue_id=catalogue_id,
                schema_version=schema_version,
                run_ids_requested=self.run_ids,
                run_ids_found=found,
                as_of=self.as_of,
                reporting_window_start=self.reporting_window_start,
                reporting_window_end=self.reporting_window_end,
                source_id=source_id,
                source_version=source_version,
                evidence_basis=self.evidence_basis,
                coverage=coverage,
                records=decorated,
                operator_snapshot=operator_snapshot,
            )
        except sqlite3.Error as exc:
            raise Phase5CatalogueAdapterError("persisted catalogue read failed closed") from exc
        finally:
            if owned:
                connection.close()

    def project(self) -> Phase5CatalogueProjection:
        snapshot = self.read_snapshot()
        operator_health = project_operator_health(snapshot.operator_snapshot)
        document = json.loads(operator_health.canonical_json.decode("utf-8"))
        document["catalogue_integration"] = {
            "catalogue_id": snapshot.catalogue_id,
            "schema_version": snapshot.schema_version,
            "run_selection": snapshot.coverage["run_selection"],
            "coverage": snapshot.coverage,
            "record_counts": {name: len(rows) for name, rows in snapshot.records.items()},
            "timestamp_provenance": {"as_of": snapshot.as_of, "reporting_window_start": snapshot.reporting_window_start, "reporting_window_end": snapshot.reporting_window_end, "basis": "explicit caller-supplied timestamps"},
        }
        canonical_json = _canonical_bytes(document)
        return Phase5CatalogueProjection(snapshot=snapshot, operator_health=operator_health, document=document, canonical_json=canonical_json, sha256=hashlib.sha256(canonical_json).hexdigest())


def project_operator_health_catalogue(catalogue: str | Path | sqlite3.Connection, **kwargs: Any) -> Phase5CatalogueProjection:
    """Read a bounded persisted catalogue selection and project operator health."""

    return Phase5OperatorHealthCatalogueAdapter(catalogue, **kwargs).project()


__all__ = [
    "Phase5CatalogueAdapterError",
    "Phase5CatalogueSnapshot",
    "Phase5CatalogueProjection",
    "Phase5OperatorHealthCatalogueAdapter",
    "project_operator_health_catalogue",
]
