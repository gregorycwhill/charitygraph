"""Deterministic, provider-free operator health for the Phase-5 runtime.

This module is an observer, not a runner and not a second catalogue.  It
accepts an immutable-in-use snapshot of existing catalogue-shaped rows (or a
small adapter object exposing those rows), performs only mechanical joins and
arithmetic, and returns a canonical JSON diagnostic.  It never opens a file,
contacts a provider, schedules work, reserves budget, or persists state.

The adapter boundary is deliberately structural.  A caller may pass a mapping
with the fields documented by :class:`OperatorHealthSnapshot`, an
``OperatorHealthSnapshot`` instance, or an object with those attributes.  The
shape is compatible with the row groups emitted by
``phase5_run_diagnostics_catalog.PersistedRunDiagnosticsAdapter``; no catalog
interface or schema change is required.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_ID = "charitygraph.phase5.operator-health"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"
UNKNOWN = "UNKNOWN"
NOT_OBSERVED = "NOT_OBSERVED"


class OperatorHealthError(ValueError):
    """Raised when the snapshot cannot be interpreted without guessing."""


@dataclass(frozen=True)
class OperatorHealthSnapshot:
    """Read-only snapshot/adapter input.

    ``source_id``, ``source_version`` and ``evidence_basis`` identify the
    snapshot, not a provider or source document.  ``ledger_complete`` must be
    explicitly true, and ``ledger_as_of`` plus ``ledger_source_id`` and
    ``ledger_version`` must be supplied, before a cost total can be reported as
    observed.  All row groups are ordinary mappings and may be empty.
    """

    as_of: str
    source_id: str
    source_version: str
    evidence_basis: str
    reporting_window_start: str | None = None
    reporting_window_end: str | None = None
    project_id: str | None = None
    ledger_source_id: str | None = None
    ledger_version: str | None = None
    ledger_as_of: str | None = None
    ledger_stale_after: str | None = None
    ledger_complete: bool | None = None
    stalled_after_seconds: int | None = None
    runs: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    jobs: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    requests: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    tasks: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    attempts: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    receipts: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    reservations: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    cost_entries: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    observations: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OperatorHealthProjection:
    """Canonical diagnostic document and its content identity."""

    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


_GROUPS = ("runs", "jobs", "requests", "tasks")
_ACTIVE = {"planned", "ready", "leased", "running", "prepared", "submitted", "in_progress", "send_started"}
_SUCCESS = {"succeeded", "success", "completed", "validated", "receipt_persisted"}
_FAILURE = {"failed", "failed_retryable", "failed_terminal", "cancelled", "expired", "rejected"}
_AMBIGUOUS = {"ambiguous", "send_ambiguous", "provider_crossing_ambiguous"}
_USAGE_MISSING = object()
_USAGE_INVALID = object()


def _value(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
    else:
        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
    return default


def _text(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OperatorHealthError(f"{field} must be a non-empty string")
    return value


def _no_float(value: Any, path: str = "snapshot", _seen: set[int] | None = None) -> None:
    if isinstance(value, float):
        raise OperatorHealthError(f"binary floating-point value is not admissible at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _no_float(child, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _no_float(child, f"{path}[{index}]")
    elif hasattr(value, "__dict__"):
        seen = _seen if _seen is not None else set()
        marker = id(value)
        if marker in seen:
            return
        seen.add(marker)
        for key, child in vars(value).items():
            _no_float(child, f"{path}.{key}", seen)


def _timestamp(value: Any, field: str, issues: list[dict[str, Any]], *, required: bool = False) -> datetime | None:
    if value is None or value == "":
        if required:
            issues.append({"code": "MISSING_TIMESTAMP", "severity": "warning", "message": f"{field} is missing"})
        return None
    if not isinstance(value, str):
        issues.append({"code": "INVALID_TIMESTAMP", "severity": "error", "message": f"{field} is not an ISO timestamp"})
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append({"code": "INVALID_TIMESTAMP", "severity": "error", "message": f"{field} is not an ISO timestamp"})
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        issues.append({"code": "AMBIGUOUS_TIMESTAMP", "severity": "error", "message": f"{field} lacks an explicit timezone"})
        return None
    return parsed.astimezone(timezone.utc)


def _decimal(value: Any, field: str, issues: list[dict[str, Any]]) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (bool, float)):
        issues.append({"code": "INVALID_DECIMAL", "severity": "error", "message": f"{field} is not an exact decimal"})
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        issues.append({"code": "INVALID_DECIMAL", "severity": "error", "message": f"{field} is not an exact decimal"})
        return None
    if not result.is_finite() or result < 0:
        issues.append({"code": "INVALID_DECIMAL", "severity": "error", "message": f"{field} must be finite and non-negative"})
        return None
    return result


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, Mapping):
        return {str(key): _canonical(child) for key, child in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(child) for child in value]
    return value


def _row_id(row: Mapping[str, Any], group: str, index: int) -> str:
    names = {
        "run": ("run_id", "record_id"),
        "job": ("delivery_job_id", "job_id"),
        "request": ("provider_request_item_id", "request_item_id", "request_id"),
        "task": ("model_task_id", "task_id"),
        "attempt": ("delivery_attempt_id", "task_run_id", "attempt_id"),
        "receipt": ("provider_receipt_id", "receipt_id"),
        "reservation": ("reservation_id",),
        "cost": ("entry_key", "entry_id"),
    }.get(group, ("id", "record_id"))
    identifier = _value(row, *names)
    return str(identifier) if identifier not in (None, "") else f"missing:{group}:{index}"


def _stable_identity(row: Mapping[str, Any], names: Sequence[str]) -> str | None:
    value = _value(row, *names)
    return str(value) if value not in (None, "") else None


def _evidence_payload(row: Mapping[str, Any], excluded: set[str]) -> Any:
    return _canonical({key: value for key, value in row.items() if str(key) not in excluded})


def _deduplicate_rows(
    snapshot: OperatorHealthSnapshot,
    rows: Sequence[Mapping[str, Any]],
    issues: list[dict[str, Any]],
    *,
    identity_names: Sequence[str],
    excluded_payload_fields: set[str],
    duplicate_codes: Sequence[str],
    conflict_code: str,
    label: str,
) -> tuple[tuple[Mapping[str, Any], ...], set[str]]:
    first_by_identity: dict[str, tuple[Mapping[str, Any], Any]] = {}
    ambiguous: set[str] = set()
    without_identity: list[Mapping[str, Any]] = []
    for row in rows:
        identity = _stable_identity(row, identity_names)
        if identity is None:
            without_identity.append(row)
            continue
        payload = _evidence_payload(row, excluded_payload_fields)
        prior = first_by_identity.get(identity)
        if prior is None:
            first_by_identity[identity] = (row, payload)
            continue
        if identity in ambiguous:
            continue
        if prior[1] == payload:
            for code in duplicate_codes:
                _issue(issues, code, "warning", f"duplicate {label} {identity} was counted once", scope=_scope(snapshot), action=f"Retain one immutable {label} identity in the evidence ledger.")
            continue
        ambiguous.add(identity)
        _issue(issues, conflict_code, "error", f"{label} {identity} has conflicting duplicate material", scope=_scope(snapshot), action=f"Reconcile the conflicting {label} rows before using diagnostic totals.")
    deduplicated = [row for identity, (row, _payload) in first_by_identity.items() if identity not in ambiguous]
    deduplicated.extend(without_identity)
    return tuple(deduplicated), ambiguous


def _currency_code(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 3 and value == value.upper() and value.isalpha()


def _rows(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise OperatorHealthError(f"{field} must be a sequence of row mappings")
    result = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise OperatorHealthError(f"{field}[{index}] must be a mapping")
        result.append(dict(row))
    return tuple(result)


def _adapt(snapshot: Any) -> OperatorHealthSnapshot:
    if isinstance(snapshot, OperatorHealthSnapshot):
        _no_float(snapshot.__dict__)
        return snapshot
    if snapshot is None:
        raise OperatorHealthError("snapshot is required")
    ledger = _value(snapshot, "ledger", "ledger_snapshot", default={}) or {}
    run_record = _value(snapshot, "run_record", default=None)
    runs = _value(snapshot, "runs", "run_records", default=None)
    if runs is None and run_record is not None:
        runs = (run_record,)
    def group(name: str, *aliases: str) -> tuple[Mapping[str, Any], ...]:
        found = _value(snapshot, name, *aliases, default=None)
        if found is None:
            found = _value(ledger, name, *aliases, default=())
        return _rows(found, name)

    _no_float(snapshot)
    as_of = _value(snapshot, "as_of", "snapshot_observed_at", "observed_at")
    source_id = _value(snapshot, "source_id", "database_path", default="snapshot:unspecified")
    source_version = _value(snapshot, "source_version", "observation_version", "snapshot_hash", default="version:unspecified")
    evidence_basis = _value(snapshot, "evidence_basis", default="caller-supplied structured runtime snapshot")
    if as_of is None:
        raise OperatorHealthError("snapshot.as_of is required; diagnostics must not use wall-clock time")
    return OperatorHealthSnapshot(
        as_of=_text(as_of, "snapshot.as_of") or "",
        source_id=_text(source_id, "snapshot.source_id") or "",
        source_version=_text(source_version, "snapshot.source_version") or "",
        evidence_basis=_text(evidence_basis, "snapshot.evidence_basis") or "",
        reporting_window_start=_value(snapshot, "reporting_window_start", "window_start"),
        reporting_window_end=_value(snapshot, "reporting_window_end", "window_end"),
        project_id=_value(snapshot, "project_id"),
        ledger_source_id=_value(snapshot, "ledger_source_id", default=_value(ledger, "source_id")),
        ledger_version=_value(snapshot, "ledger_version", default=_value(ledger, "source_version", "version")),
        ledger_as_of=_value(snapshot, "ledger_as_of", default=_value(ledger, "as_of", "observed_at")),
        ledger_stale_after=_value(snapshot, "ledger_stale_after", default=_value(ledger, "stale_after")),
        ledger_complete=_value(snapshot, "ledger_complete", default=_value(ledger, "complete")),
        stalled_after_seconds=_value(snapshot, "stalled_after_seconds", default=_value(snapshot, "stalled_after")),
        runs=_rows(runs, "runs"),
        jobs=group("jobs", "delivery_jobs"),
        requests=group("requests", "request_items", "provider_request_items"),
        tasks=group("tasks"),
        attempts=group("attempts", "task_attempts", "provider_request_attempts"),
        receipts=group("receipts", "provider_receipts"),
        reservations=group("reservations", "budget_reservations"),
        cost_entries=group("cost_entries", "costs"),
        observations=group("observations", "factual_observations"),
    )


def _issue(issues: list[dict[str, Any]], code: str, severity: str, message: str, *, scope: Mapping[str, Any], action: str) -> None:
    issues.append({"code": code, "severity": severity, "message": message, "scope": dict(scope), "action_hint": action})


def _scope(snapshot: OperatorHealthSnapshot, *, run_ids: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "run_ids": sorted(set(run_ids)),
        "source_ids": [snapshot.source_id],
        "evidence_basis": snapshot.evidence_basis,
        "as_of": snapshot.as_of,
    }


def _row_sources(snapshot: OperatorHealthSnapshot, rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    values = {(str(_value(row, "source_id", default=snapshot.source_id)), str(_value(row, "source_version", default=snapshot.source_version)), str(_value(row, "evidence_basis", default=snapshot.evidence_basis))) for row in rows}
    return [{"source_id": source, "source_version": version, "evidence_basis": basis} for source, version, basis in sorted(values)]


def _status_group(rows: Sequence[Mapping[str, Any]], group: str) -> dict[str, Any]:
    counter = Counter(str(_value(row, "status", default=UNKNOWN)) for row in rows)
    denominator = len(rows)
    rates = {}
    for status, count in sorted(counter.items()):
        rates[status] = {"count": count, "denominator": denominator, "rate": _decimal_text(Decimal(count) / Decimal(denominator)) if denominator else None}
    return {"count": denominator, "status_counts": dict(sorted(counter.items())), "rates": rates, "denominator_basis": f"observed_{group}_rows"}


def _window(snapshot: OperatorHealthSnapshot, all_rows: Iterable[Mapping[str, Any]], issues: list[dict[str, Any]]) -> tuple[datetime | None, datetime | None, dict[str, Any]]:
    start_value = snapshot.reporting_window_start
    end_value = snapshot.reporting_window_end
    times: list[datetime] = []
    for row in all_rows:
        for name in ("created_at", "started_at", "submitted_at", "send_started_at", "receipt_persisted_at", "received_at", "completed_at", "updated_at", "recorded_at"):
            parsed = _timestamp(_value(row, name), f"{_row_id(row, 'row', 0)}.{name}", issues)
            if parsed is not None:
                times.append(parsed)
    start = _timestamp(start_value, "reporting_window_start", issues) if start_value else (min(times) if times else None)
    end = _timestamp(end_value, "reporting_window_end", issues) if end_value else (max(times) if times else None)
    elapsed = None
    if start is not None and end is not None and end > start:
        elapsed = Decimal(str((end - start).total_seconds()))
    elif start is not None and end is not None:
        _issue(issues, "NON_POSITIVE_WINDOW", "warning", "reporting window has no positive observed elapsed time", scope=_scope(snapshot), action="Review the supplied reporting-window timestamps.")
    else:
        _issue(issues, "NO_OBSERVED_ELAPSED_TIME", "warning", "throughput cannot be calculated without two timezone-aware window timestamps", scope=_scope(snapshot), action="Supply a bounded reporting window or durable event timestamps.")
    return start, end, {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None, "elapsed_seconds": _decimal_text(elapsed), "basis": "explicit_window" if start_value or end_value else "derived_from_durable_event_timestamps"}


def _throughput(count: int, observed_count: int, elapsed: Decimal | None, unit: str) -> dict[str, Any]:
    usable = bool(observed_count and elapsed and elapsed > 0)
    return {"value": _decimal_text(Decimal(count) / elapsed) if usable else None, "unit": unit, "numerator": count, "denominator_elapsed_seconds": _decimal_text(elapsed) if observed_count else None, "observed_elapsed_only": usable}


def _latency(snapshot: OperatorHealthSnapshot, rows: Sequence[Mapping[str, Any]], issues: list[dict[str, Any]], start_name: str, end_name: str, metric: str) -> dict[str, Any]:
    values: list[Decimal] = []
    for row in rows:
        start = _timestamp(_value(row, start_name), f"{_row_id(row, 'row', 0)}.{start_name}", issues)
        end = _timestamp(_value(row, end_name), f"{_row_id(row, 'row', 0)}.{end_name}", issues)
        if start and end:
            seconds = Decimal(str((end - start).total_seconds()))
            if seconds >= 0:
                values.append(seconds)
            else:
                _issue(issues, "NEGATIVE_LATENCY", "error", f"{metric} has a negative elapsed interval", scope=_scope(snapshot, run_ids=[str(_value(row, "run_id"))] if _value(row, "run_id") else []), action="Reconcile the source timestamps before using latency telemetry.")
    if not values:
        return {"value": None, "unit": "seconds", "sample_count": 0, "basis": NOT_OBSERVED}
    return {"value": _decimal_text(sum(values, Decimal(0)) / Decimal(len(values))), "unit": "seconds", "sample_count": len(values), "basis": f"observed_{start_name}_to_{end_name}"}


def _cost_provenance(row: Mapping[str, Any], snapshot: OperatorHealthSnapshot) -> tuple[str | None, str | None, str | None]:
    pricing = _value(row, "pricing_snapshot_id", "pricing_version")
    fx = _value(row, "fx_snapshot_id", "fx_version")
    source = _value(row, "source_id", default=snapshot.source_id)
    return (
        pricing.strip() if isinstance(pricing, str) and pricing.strip() else None,
        fx.strip() if isinstance(fx, str) and fx.strip() else None,
        source.strip() if isinstance(source, str) and source.strip() else None,
    )


def _ledger_health(snapshot: OperatorHealthSnapshot, issues: list[dict[str, Any]]) -> tuple[str, str]:
    if snapshot.ledger_source_id is None or snapshot.ledger_version is None or snapshot.ledger_as_of is None:
        _issue(issues, "MISSING_PROJECT_LEDGER", "error", "project ledger provenance or as-of time is missing", scope=_scope(snapshot), action="Supply an explicitly scoped, versioned project ledger snapshot.")
        return "missing", "project-wide ledger is not evidenced"
    ledger_as_of_issues: list[dict[str, Any]] = []
    ledger_time = _timestamp(snapshot.ledger_as_of, "ledger_as_of", ledger_as_of_issues)
    as_of = _timestamp(snapshot.as_of, "as_of", ledger_as_of_issues)
    stale_after = _timestamp(snapshot.ledger_stale_after, "ledger_stale_after", ledger_as_of_issues) if snapshot.ledger_stale_after else None
    if ledger_as_of_issues:
        _issue(issues, "INVALID_LEDGER_TIME", "error", "project ledger freshness cannot be established", scope=_scope(snapshot), action="Repair the ledger as-of/freshness timestamps.")
        return "unknown", "ledger freshness is ambiguous"
    if snapshot.ledger_complete is not True:
        _issue(issues, "INCOMPLETE_PROJECT_LEDGER", "error", "project ledger does not explicitly attest complete coverage", scope=_scope(snapshot), action="Provide a project-wide completeness assertion covering unknown and ambiguous states.")
        return "unknown", "project-wide ledger completeness is not attested"
    if stale_after is not None and as_of is not None and as_of > stale_after:
        _issue(issues, "STALE_PROJECT_LEDGER", "error", "project ledger is stale at the diagnostic as-of time", scope=_scope(snapshot), action="Refresh the project ledger before relying on totals.")
        return "stale", "project-wide ledger is stale"
    if ledger_time is None or as_of is None or ledger_time > as_of:
        _issue(issues, "AMBIGUOUS_PROJECT_LEDGER", "error", "project ledger temporal relation is not safe", scope=_scope(snapshot), action="Reconcile ledger and diagnostic as-of timestamps.")
        return "unknown", "project-wide ledger time is ambiguous"
    return "observed", "complete, versioned and current at as-of"


def _costs(snapshot: OperatorHealthSnapshot, issues: list[dict[str, Any]]) -> dict[str, Any]:
    ledger_state, ledger_reason = _ledger_health(snapshot, issues)
    seen: dict[str, Mapping[str, Any]] = {}
    usable: list[Mapping[str, Any]] = []
    ambiguous_keys: set[str] = set()
    for index, row in enumerate(snapshot.cost_entries):
        key = str(_value(row, "entry_key", "entry_id", default=f"row:{index}"))
        prior = seen.get(key)
        if prior is not None:
            if _canonical(prior) == _canonical(row):
                _issue(issues, "DUPLICATE_COST_ENTRY", "warning", f"duplicate cost entry {key} was counted once", scope=_scope(snapshot), action="Keep one immutable cost-entry identity in the source ledger.")
                continue
            ambiguous_keys.add(key)
            _issue(issues, "AMBIGUOUS_COST_ENTRY", "error", f"cost entry {key} has conflicting duplicate material", scope=_scope(snapshot), action="Reconcile the conflicting ledger rows before using cost totals.")
            continue
        seen[key] = row
        usable.append(row)
    actual_by_receipt: dict[str, tuple[Decimal, str, Any]] = {}
    ambiguous_receipts: set[str] = set()
    release_total = Decimal(0)
    release_row_count = 0
    forecast_total = Decimal(0)
    currencies: set[str] = set()
    invalid_actual = False
    for row in usable:
        entry_type = str(_value(row, "entry_type", default="unknown"))
        if entry_type not in {"actual", "provider_actual", "reservation_release", "release", "forecast"}:
            continue
        raw_amount = _value(row, "accounting_amount", "aud_amount", "amount")
        amount = _decimal(raw_amount, f"cost.{_row_id(row, 'cost', 0)}.amount", issues)
        currency = _value(row, "accounting_currency", "currency", default=None)
        if amount is None or not _currency_code(currency):
            invalid_actual = True
            _issue(issues, "INVALID_COST_CURRENCY", "error", f"cost {_row_id(row, 'cost', 0)} lacks a valid accounting currency", scope=_scope(snapshot), action="Supply an explicit three-letter accounting currency for every cost row.")
            continue
        currencies.add(currency)
        if entry_type in {"actual", "provider_actual"}:
            pricing, fx, _ = _cost_provenance(row, snapshot)
            provider_amount = _decimal(_value(row, "provider_amount"), f"cost.{_row_id(row, 'cost', 0)}.provider_amount", issues)
            provider_currency = _value(row, "provider_currency")
            if not isinstance(pricing, str) or not pricing.strip() or not isinstance(fx, str) or not fx.strip() or provider_amount is None or not _currency_code(provider_currency):
                invalid_actual = True
                _issue(issues, "MISSING_COST_PROVENANCE", "error", f"actual cost { _row_id(row, 'cost', 0)} lacks immutable pricing or FX provenance", scope=_scope(snapshot, run_ids=[str(_value(row, "run_id"))] if _value(row, "run_id") else []), action="Bind the actual to immutable pricing, currency and FX source versions.")
                continue
            receipt_key = _stable_identity(row, ("provider_receipt_id", "receipt_id"))
            if receipt_key is None:
                invalid_actual = True
                _issue(
                    issues,
                    "UNIDENTIFIABLE_RECEIPT_IDENTITY",
                    "error",
                    f"actual cost {_row_id(row, 'cost', 0)} has no stable provider receipt identity",
                    scope=_scope(snapshot, run_ids=[str(_value(row, "run_id"))] if _value(row, "run_id") else []),
                    action="Bind each actual-cost observation to a stable provider receipt identity before relying on spend totals.",
                )
                continue
            payload = _evidence_payload(row, {"provider_receipt_id", "receipt_id", "entry_key", "entry_id"})
            prior_receipt = actual_by_receipt.get(receipt_key)
            if prior_receipt is not None:
                if receipt_key in ambiguous_receipts:
                    continue
                if prior_receipt[2] != payload:
                    ambiguous_receipts.add(receipt_key)
                    invalid_actual = True
                    _issue(issues, "AMBIGUOUS_RECEIPT_IDENTITY", "error", f"receipt {receipt_key} has conflicting actual-cost observations", scope=_scope(snapshot), action="Reconcile the conflicting receipt observations before relying on spend totals.")
                else:
                    _issue(issues, "DUPLICATE_RECEIPT", "warning", f"receipt {receipt_key} was counted once", scope=_scope(snapshot), action="Retain one actual ledger entry per provider receipt.")
                continue
            actual_by_receipt[receipt_key] = (amount, currency, payload)
        elif entry_type in {"reservation_release", "release"}:
            release_total += amount
            release_row_count += 1
        else:
            forecast_total += amount
    actual_total = sum((value[0] for key, value in actual_by_receipt.items() if key not in ambiguous_receipts), Decimal(0))
    reservation_rows, ambiguous_reservations = _deduplicate_rows(
        snapshot,
        snapshot.reservations,
        issues,
        identity_names=("reservation_id",),
        excluded_payload_fields={"reservation_id"},
        duplicate_codes=("DUPLICATE_RESERVATION_ID", "DUPLICATE_RESERVATION"),
        conflict_code="AMBIGUOUS_RESERVATION_IDENTITY",
        label="reservation",
    )
    reservation_total = Decimal(0)
    reservation_valid = True
    active_reservations = []
    for row in reservation_rows:
        status = str(_value(row, "status", default=UNKNOWN))
        if status not in {"active", "held", "reserved", "committed", "leased"}:
            continue
        active_reservations.append(row)
        amount = _decimal(_value(row, "reserved_aud", "reserved_amount", "amount"), f"reservation.{_row_id(row, 'reservation', 0)}.amount", issues)
        currency = _value(row, "accounting_currency", "currency", default=None)
        if amount is None or not _currency_code(currency) or currency != "AUD":
            reservation_valid = False
        else:
            reservation_total += amount
    if ambiguous_reservations:
        reservation_valid = False
    freshness_ok = ledger_state == "observed"
    difference: Decimal | None = None
    def total(state: str, amount: Decimal | None, count: int, reason: str) -> dict[str, Any]:
        amount_states = {"observed_actual", "committed_reserved", "forecast"}
        return {"state": state, "amount": _decimal_text(amount) if state in amount_states else None, "currency": "AUD" if state in amount_states else None, "entry_count": count, "reason": reason}
    if ledger_state == "stale":
        actual = total("stale", None, len(actual_by_receipt) - len(ambiguous_receipts), ledger_reason)
        reserved = total("stale", None, len(active_reservations), ledger_reason)
        forecast = total("stale", None, 0, ledger_reason)
        reconciliation_state = "STALE"
    elif ledger_state != "observed":
        state = "ambiguous" if ambiguous_keys or invalid_actual else ledger_state
        actual = total(state, None, len(actual_by_receipt) - len(ambiguous_receipts), ledger_reason)
        reserved = total(state, None, len(active_reservations), ledger_reason)
        forecast = total(state, None, 0, ledger_reason)
        reconciliation_state = state.upper()
    elif invalid_actual or len(currencies) != 1 or (currencies and currencies != {"AUD"}) or not reservation_valid:
        actual = total("ambiguous", None, len(actual_by_receipt) - len(ambiguous_receipts), "currency, provenance or amount evidence is incomplete")
        reserved = total("ambiguous", None, len(active_reservations), "currency, provenance or amount evidence is incomplete")
        forecast = total("ambiguous", None, 0, "currency, provenance or amount evidence is incomplete")
        reconciliation_state = "AMBIGUOUS"
    else:
        valid_actual_count = len(actual_by_receipt) - len(ambiguous_receipts)
        actual = total("observed_actual", actual_total, valid_actual_count, "deduplicated provider receipts with pricing and FX provenance") if valid_actual_count else total("missing", None, 0, "no actual provider receipt cost evidence supplied")
        reserved = total("committed_reserved", reservation_total, len(active_reservations), "active/held/committed reservations") if active_reservations else total("missing", None, 0, "no committed reservation evidence supplied")
        forecast = total("forecast", forecast_total, sum(1 for row in usable if str(_value(row, "entry_type", default="")) == "forecast"), "explicit forecast entries") if any(str(_value(row, "entry_type", default="")) == "forecast" for row in usable) else total("missing", None, 0, "no forecast evidence supplied")
        difference = reservation_total - actual_total - release_total if release_row_count and valid_actual_count and active_reservations else None
        reconciliation_state = "MISSING" if not valid_actual_count or not active_reservations or not release_row_count else ("RECONCILED" if difference >= 0 else "DISCREPANT")
        if difference is not None and difference < 0:
            _issue(issues, "RESERVATION_OVERRUN", "error", "actuals and releases exceed committed reservations", scope=_scope(snapshot), action="Reconcile reservation and actual-cost ledger entries before further work.")
    provenance = {"ledger_source_id": snapshot.ledger_source_id, "ledger_version": snapshot.ledger_version, "ledger_as_of": snapshot.ledger_as_of, "currency": "AUD" if currencies == {"AUD"} else None, "pricing_versions": sorted({str(_cost_provenance(row, snapshot)[0]) for row in usable if _cost_provenance(row, snapshot)[0]}), "fx_versions": sorted({str(_cost_provenance(row, snapshot)[1]) for row in usable if _cost_provenance(row, snapshot)[1]})}
    release_state = "observed_actual" if freshness_ok and not invalid_actual and release_row_count else ("missing" if freshness_ok and not invalid_actual else ledger_state)
    return {"ledger_state": ledger_state, "actual": actual, "committed_reserved": reserved, "forecast": forecast, "reservation_releases": {"amount": _decimal_text(release_total) if release_state == "observed_actual" else None, "currency": "AUD" if release_state == "observed_actual" else None, "entry_count": release_row_count, "state": release_state}, "reconciliation": {"state": reconciliation_state, "actual_minus_release_basis": "actual + releases <= committed reserved", "difference": _decimal_text(difference) if difference is not None and ledger_state == "observed" and not invalid_actual and reservation_valid and currencies == {"AUD"} else None}, "provenance": provenance}


def _health_flags(snapshot: OperatorHealthSnapshot, rows: Sequence[Mapping[str, Any]], attempts: Sequence[Mapping[str, Any]], receipts: Sequence[Mapping[str, Any]], issues: list[dict[str, Any]], jobs: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    as_of_issues: list[dict[str, Any]] = []
    as_of = _timestamp(snapshot.as_of, "as_of", as_of_issues)
    flags = {"stalled": [], "ambiguous": [], "retry": [], "recovery": [], "failed": []}
    threshold = snapshot.stalled_after_seconds
    labelled_rows = [("request", row) for row in rows] + [("job", row) for row in jobs] + [("attempt", row) for row in attempts]
    for index, (group, row) in enumerate(labelled_rows):
        identifier = _row_id(row, group, index)
        run_id = _value(row, "run_id")
        status = str(_value(row, "status", default=UNKNOWN))
        base = {"id": identifier, "run_id": str(run_id) if run_id else None, "source_timestamps": {key: _value(row, key) for key in ("created_at", "submitted_at", "started_at", "updated_at", "completed_at") if _value(row, key) is not None}, "provenance": {"source_id": str(_value(row, "source_id", default=snapshot.source_id)), "source_version": str(_value(row, "source_version", default=snapshot.source_version)), "evidence_basis": str(_value(row, "evidence_basis", default=snapshot.evidence_basis))}}
        if status in _AMBIGUOUS or str(_value(row, "trace_status", default="")).lower() in _AMBIGUOUS:
            flags["ambiguous"].append(base)
        if status in _FAILURE:
            flags["failed"].append(base)
        if group in {"request", "job"} and status in _ACTIVE:
            last = None
            for name in ("updated_at", "started_at", "submitted_at", "created_at"):
                parsed = _timestamp(_value(row, name), f"{identifier}.{name}", issues)
                if parsed is not None:
                    last = parsed
                    break
            if threshold is not None and as_of is not None and last is not None:
                age = Decimal(str((as_of - last).total_seconds()))
                if age >= Decimal(threshold):
                    flags["stalled"].append({**base, "last_observed_at": last.isoformat(), "age_seconds": _decimal_text(age), "threshold_seconds": threshold})
            elif last is None:
                _issue(issues, "STALL_UNDETERMINED", "warning", f"active item {identifier} has no durable timestamp", scope=_scope(snapshot, run_ids=[str(run_id)] if run_id else []), action="Record a durable scheduling or heartbeat timestamp before declaring health.")
        attempt_number = _value(row, "attempt_number", "attempt_ordinal")
        if attempt_number is not None and int(attempt_number) > 1:
            flags["retry"].append({**base, "attempt_number": int(attempt_number)})
        if _value(row, "predecessor_attempt_id", "replayed_from", "recovery_of"):
            flags["recovery"].append({**base, "predecessor_attempt_id": str(_value(row, "predecessor_attempt_id", "replayed_from", "recovery_of"))})
    return {key: sorted(value, key=lambda row: (str(row.get("run_id") or ""), str(row.get("id") or ""))) for key, value in flags.items()}


def _usage_container(row: Mapping[str, Any]) -> tuple[Any, str | None]:
    if "usage" in row:
        usage = row["usage"]
    else:
        usage = _value(row, "usage_json", default=_USAGE_MISSING)
        if isinstance(usage, str):
            try:
                usage = json.loads(usage)
            except (TypeError, ValueError, json.JSONDecodeError):
                return _USAGE_INVALID, "INVALID_USAGE_JSON"
    if usage is _USAGE_MISSING or usage is None:
        return usage, None
    if not isinstance(usage, Mapping):
        return _USAGE_INVALID, "INVALID_USAGE_SHAPE"
    return usage, None


def _usage_value(row: Mapping[str, Any], name: str) -> tuple[bool, Any]:
    if name in row:
        return True, row[name]
    usage, _reason = _usage_container(row)
    if isinstance(usage, Mapping) and name in usage:
        return True, usage[name]
    return False, None


def _token_count(snapshot: OperatorHealthSnapshot, row: Mapping[str, Any], name: str, issues: list[dict[str, Any]]) -> int | None:
    present, raw = _usage_value(row, name)
    if not present:
        _issue(issues, "MISSING_PROVIDER_USAGE", "warning", f"receipt {_row_id(row, 'receipt', 0)} lacks required {name}", scope=_scope(snapshot), action="Reconcile provider usage before relying on token totals.")
        return None
    if raw is None:
        _issue(issues, "INVALID_PROVIDER_USAGE", "error", f"receipt {_row_id(row, 'receipt', 0)} has null {name}", scope=_scope(snapshot), action="Reconcile provider usage before relying on token totals.")
        return None
    if isinstance(raw, bool):
        _issue(issues, "INVALID_PROVIDER_USAGE", "error", f"receipt {_row_id(row, 'receipt', 0)} has non-integer {name}", scope=_scope(snapshot), action="Reconcile provider usage before relying on token totals.")
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError, OverflowError):
        _issue(issues, "INVALID_PROVIDER_USAGE", "error", f"receipt {_row_id(row, 'receipt', 0)} has non-integer {name}", scope=_scope(snapshot), action="Reconcile provider usage before relying on token totals.")
        return None
    if str(raw) != str(value) and not isinstance(raw, int):
        _issue(issues, "INVALID_PROVIDER_USAGE", "error", f"receipt {_row_id(row, 'receipt', 0)} has non-integer {name}", scope=_scope(snapshot), action="Reconcile provider usage before relying on token totals.")
        return None
    if value < 0:
        _issue(issues, "INVALID_PROVIDER_USAGE", "error", f"receipt {_row_id(row, 'receipt', 0)} has negative {name}", scope=_scope(snapshot), action="Reconcile provider usage before relying on token totals.")
        return None
    return value


def _usage_marker(row: Mapping[str, Any]) -> tuple[str | None, str | None]:
    state = _value(row, "usage_coverage_state")
    reason = _value(row, "usage_coverage_reason")
    if not (isinstance(state, str) and state.strip()):
        _container, parse_reason = _usage_container(row)
        if parse_reason is not None:
            return "ambiguous", parse_reason
    return (
        state.strip().lower() if isinstance(state, str) and state.strip() else None,
        reason.strip() if isinstance(reason, str) and reason.strip() else None,
    )


def _per_run(snapshot: OperatorHealthSnapshot, groups: Mapping[str, Sequence[Mapping[str, Any]]], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids: set[str] = set()
    for rows in groups.values():
        ids.update(str(_value(row, "run_id")) for row in rows if _value(row, "run_id"))
    ids.update(str(_value(row, "run_id", "run_id")) for row in snapshot.runs if _value(row, "run_id", "record_id"))
    output = []
    for run_id in sorted(ids):
        selected = {name: [row for row in rows if str(_value(row, "run_id")) == run_id] for name, rows in groups.items()}
        output.append({"run_id": run_id, "subject_ids": sorted({str(_value(row, "subject_id", "durable_subject_id")) for rows in selected.values() for row in rows if _value(row, "subject_id", "durable_subject_id")}), "scope_ids": sorted({str(_value(row, "scope_id", "durable_scope_id")) for rows in selected.values() for row in rows if _value(row, "scope_id", "durable_scope_id")}), "source_ids": sorted({str(_value(row, "source_id", default=snapshot.source_id)) for rows in selected.values() for row in rows}), "evidence_basis": snapshot.evidence_basis, "as_of": snapshot.as_of, "status_counts": {name: _status_group(rows, name) for name, rows in selected.items()}, "flags": {"failed": sum(1 for row in selected["requests"] if str(_value(row, "status", default="")) in _FAILURE), "ambiguous": sum(1 for row in selected["requests"] if str(_value(row, "status", default="")) in _AMBIGUOUS), "retries": sum(1 for row in selected["attempts"] if int(_value(row, "attempt_number", "attempt_ordinal", default=1)) > 1), "recovery": sum(1 for row in selected["attempts"] if _value(row, "predecessor_attempt_id", "replayed_from", "recovery_of"))}})
    return output


def project_operator_health(snapshot: Any) -> OperatorHealthProjection:
    """Build a deterministic operator-health document from existing rows."""

    data = _adapt(snapshot)
    issues: list[dict[str, Any]] = []
    as_of_issues: list[dict[str, Any]] = []
    as_of = _timestamp(data.as_of, "as_of", as_of_issues)
    if as_of is None:
        raise OperatorHealthError("snapshot.as_of must be timezone-aware")
    for issue in as_of_issues:
        _issue(issues, issue["code"], issue["severity"], issue["message"], scope=_scope(data), action="Repair the diagnostic as-of timestamp.")
    all_rows = (*data.runs, *data.jobs, *data.requests, *data.tasks, *data.attempts, *data.receipts, *data.reservations, *data.cost_entries, *data.observations)
    start, end, window = _window(data, all_rows, issues)
    elapsed = Decimal(window["elapsed_seconds"]) if window["elapsed_seconds"] is not None else None
    groups = {"runs": data.runs, "jobs": data.jobs, "requests": data.requests, "tasks": data.tasks}
    receipt_rows, ambiguous_receipts = _deduplicate_rows(
        data,
        data.receipts,
        issues,
        identity_names=("provider_receipt_id", "receipt_id"),
        excluded_payload_fields={"provider_receipt_id", "receipt_id"},
        duplicate_codes=("DUPLICATE_RECEIPT_ID", "DUPLICATE_RECEIPT"),
        conflict_code="AMBIGUOUS_RECEIPT_IDENTITY",
        label="provider receipt",
    )
    unidentifiable_receipts = tuple(
        row for row in receipt_rows
        if _stable_identity(row, ("provider_receipt_id", "receipt_id")) is None
    )
    if unidentifiable_receipts:
        for row in unidentifiable_receipts:
            _issue(
                issues,
                "UNIDENTIFIABLE_RECEIPT_IDENTITY",
                "error",
                "provider receipt observation has neither provider_receipt_id nor receipt_id",
                scope=_scope(data, run_ids=[str(_value(row, "run_id"))] if _value(row, "run_id") else []),
                action="Retain a stable provider receipt identity before claiming deduplicated usage or actual cost.",
            )
    identified_receipts = tuple(
        row for row in receipt_rows
        if _stable_identity(row, ("provider_receipt_id", "receipt_id")) is not None
    )
    flags = _health_flags(data, data.requests, data.attempts, identified_receipts, issues, data.jobs)
    input_tokens = 0
    output_tokens = 0
    usage_invalid = False
    usage_missing = False
    usage_reasons: set[str] = set()
    for receipt in identified_receipts:
        marker_state, marker_reason = _usage_marker(receipt)
        if marker_state in {"ambiguous", "invalid"}:
            usage_invalid = True
            usage_reasons.add(marker_reason or "INVALID_PROVIDER_USAGE")
            _issue(
                issues,
                marker_reason or "INVALID_PROVIDER_USAGE",
                "error",
                f"receipt {_row_id(receipt, 'receipt', 0)} has ambiguous provider usage coverage",
                scope=_scope(data, run_ids=[str(_value(receipt, "run_id"))] if _value(receipt, "run_id") else []),
                action="Reconcile provider usage before relying on token totals.",
            )
            continue
        if marker_state == "missing":
            usage_missing = True
            usage_reasons.add(marker_reason or "MISSING_PROVIDER_USAGE")
            _issue(
                issues,
                marker_reason or "MISSING_PROVIDER_USAGE",
                "warning",
                f"receipt {_row_id(receipt, 'receipt', 0)} has incomplete provider usage coverage",
                scope=_scope(data, run_ids=[str(_value(receipt, "run_id"))] if _value(receipt, "run_id") else []),
                action="Reconcile provider usage before relying on token totals.",
            )
            continue
        before = len(issues)
        input_value = _token_count(data, receipt, "input_tokens", issues)
        output_value = _token_count(data, receipt, "output_tokens", issues)
        if input_value is None or output_value is None:
            new_codes = {str(issue["code"]) for issue in issues[before:]}
            if "INVALID_PROVIDER_USAGE" in new_codes:
                usage_invalid = True
                usage_reasons.add("INVALID_PROVIDER_USAGE")
            else:
                usage_missing = True
                usage_reasons.add("MISSING_PROVIDER_USAGE")
            continue
        input_tokens += input_value
        output_tokens += output_value
    if ambiguous_receipts:
        usage_reasons.add("AMBIGUOUS_RECEIPT_IDENTITY")
    if unidentifiable_receipts:
        usage_reasons.add("UNIDENTIFIABLE_RECEIPT_IDENTITY")
    if not identified_receipts and not ambiguous_receipts and not unidentifiable_receipts:
        usage_reasons.add("NO_IDENTIFIED_RECEIPTS")
    usage_state = "ambiguous" if ambiguous_receipts or unidentifiable_receipts or usage_invalid else ("missing" if usage_missing or not identified_receipts else "observed")
    if usage_state == "observed":
        usage_reasons.add("OBSERVED_COMPLETE_USAGE")
    for observation in data.observations:
        if str(_value(observation, "state", default="")) in {"ambiguous", "stale", "missing"}:
            _issue(issues, "FACTUAL_OBSERVATION_LIMIT", "warning", "an explicitly supplied observation limits health interpretation", scope=_scope(data, run_ids=[str(_value(observation, "run_id"))] if _value(observation, "run_id") else []), action="Review the supplied observation and retain its uncertainty state.")
    document = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "diagnostic_identity": {"projection": "phase5-operator-health", "project_id": data.project_id, "snapshot_source_id": data.source_id, "snapshot_source_version": data.source_version},
        "scope": {"run_ids": sorted({str(_value(row, "run_id")) for row in all_rows if _value(row, "run_id")}), "source_ids": sorted({str(_value(row, "source_id", default=data.source_id)) for row in all_rows} | {data.source_id}), "evidence_basis": data.evidence_basis, "as_of": data.as_of},
        "reporting_window": window,
        "status": {group: _status_group(rows, group) for group, rows in groups.items()},
        "throughput": {"completed_requests_per_observed_second": _throughput(sum(1 for row in data.requests if str(_value(row, "status", default="")) in _SUCCESS), len(data.requests), elapsed, "requests/second"), "completed_tasks_per_observed_second": _throughput(sum(1 for row in data.tasks if str(_value(row, "status", default="")) in _SUCCESS), len(data.tasks), elapsed, "tasks/second")},
        "latency": {"queue_wait": _latency(data, data.requests, issues, "created_at", "submitted_at", "queue_wait"), "provider_crossing": _latency(data, data.requests, issues, "send_started_at", "received_at", "provider_crossing"), "completion": _latency(data, data.requests, issues, "submitted_at", "completed_at", "completion")},
        "scheduling": {"health": "OBSERVED" if any(_value(row, "scheduled_at") is not None and _value(row, "started_at") is not None for row in data.requests) else UNKNOWN, "sample_count": sum(1 for row in data.requests if _value(row, "scheduled_at") is not None and _value(row, "started_at") is not None), "lag": _latency(data, data.requests, issues, "scheduled_at", "started_at", "scheduling"), "basis": "explicit scheduled_at_to_started_at pairs only"},
        "flags": flags,
        "provider_usage": {"state": usage_state, "receipt_count": len(receipt_rows), "receipts_with_usage": len(identified_receipts) if usage_state == "observed" else None, "input_tokens": input_tokens if usage_state == "observed" else None, "output_tokens": output_tokens if usage_state == "observed" else None, "coverage_reasons": sorted(usage_reasons), "basis": "deduplicated provider receipt identities only; no provider invocation"},
        "cost": _costs(data, issues),
        "per_run": _per_run(data, groups={**groups, "attempts": data.attempts}, issues=issues),
        "issues": sorted(issues, key=lambda issue: (str(issue.get("severity")), str(issue.get("code")), str(issue.get("message")))),
        "limitations": ["Provider-side exactly-once effects and provider invocation are not observed or performed.", "Health is scoped to supplied runtime rows and factual observations; no cross-project completeness is inferred.", "Operator action hints are recommendations only and never execute work or grant permission.", "Source-private retention does not imply provider-processing authority; model output is not promoted to knowledge."],
    }
    canonical_json = json.dumps(_canonical(document), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return OperatorHealthProjection(document=document, canonical_json=canonical_json, sha256=hashlib.sha256(canonical_json).hexdigest())


build_operator_health = project_operator_health
operator_health = project_operator_health


def canonical_operator_health_json(projection: OperatorHealthProjection | Mapping[str, Any]) -> bytes:
    document = projection.document if isinstance(projection, OperatorHealthProjection) else projection
    return json.dumps(_canonical(document), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def operator_health_sha256(projection: OperatorHealthProjection | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_operator_health_json(projection)).hexdigest()


__all__ = ["SCHEMA_ID", "SCHEMA_VERSION", "SCHEMA", "UNKNOWN", "NOT_OBSERVED", "OperatorHealthError", "OperatorHealthSnapshot", "OperatorHealthProjection", "project_operator_health", "build_operator_health", "operator_health", "canonical_operator_health_json", "operator_health_sha256"]
