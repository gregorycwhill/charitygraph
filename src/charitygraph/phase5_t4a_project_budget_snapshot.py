"""Pure, fail-closed reconciliation of project-wide AUD accounting evidence.

This module is an adapter, not a ledger.  Callers supply an immutable export of
the existing durable accounting records and a separately governed,
versioned project-wide coverage manifest.  The adapter only validates and
reconciles those values; it never opens a catalogue, writes state, reads a
file, contacts a provider, or makes a send decision.

The returned candidate hash is a reproducibility aid.  It is deliberately not
an attestation: a later independent trusted pin and the existing T4A5 verifier
remain necessary for ``BUDGET_EVIDENCE_VERIFIED_NON_SEND``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from .contracts.canonical import canonical_json_bytes


PROJECT_BUDGET_SNAPSHOT_SCHEMA = "charitygraph.project-wide-aud-budget-candidate/1"
ACCOUNTING_EVIDENCE_SCHEMA = "charitygraph.durable-accounting-evidence/1"
COVERAGE_MANIFEST_SCHEMA = "charitygraph.project-wide-paid-work-coverage-manifest/1"
DEFAULT_MAX_EVIDENCE_AGE = timedelta(hours=24)

SnapshotStatus = Literal["CANDIDATE_NOT_ATTESTED", "INCOMPLETE_OR_UNKNOWN"]

_COVERAGE_KEYS = {
    "project_wide",
    "logical_paid_tasks_complete",
    "retries_complete",
    "physical_attempts_complete",
    "cohorts_complete",
    "accounting_sources_complete",
    "reservations_complete",
    "actuals_complete",
    "pricing_complete",
}
_RECORD_KEYS = {
    "cohorts": "cohort_id",
    "logical_tasks": "model_task_id",
    "task_attempts": "task_run_id",
    "reservations": "reservation_id",
    "cost_entries": "entry_key",
    "physical_attempts": "physical_attempt_id",
    "provider_request_attempts": "delivery_attempt_id",
}
_PENDING_STATUSES = {"prepared", "send_started", "submitted", "in_progress"}
_AMBIGUOUS_STATUSES = {"held", "send_ambiguous"}
_TERMINAL_PHYSICAL_STATUSES = {"receipt_persisted", "validated", "failed"}


@dataclass(frozen=True)
class ProjectBudgetSnapshotCandidate:
    """Read-only diagnostic and candidate bytes; never a send authorisation."""

    status: SnapshotStatus
    snapshot_bytes: bytes | None = None
    snapshot_sha256: str | None = None
    as_of: str | None = None
    actual_aud: Decimal | None = None
    outstanding_reservations_aud: Decimal | None = None
    pending_or_ambiguous_physical_attempt_ids: tuple[str, ...] = ()
    unpriced_physical_attempt_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    independent_trust: Literal["NOT_SUPPLIED"] = "NOT_SUPPLIED"
    request_ticket: None = None
    send_authorization: Literal["not_authorized_for_send"] = "not_authorized_for_send"


def _unique_reasons(reasons: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(reasons)))


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(
        char in "0123456789abcdef" for char in value
    )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _load_object(value: object, label: str) -> tuple[dict[str, object] | None, str | None, list[str]]:
    if isinstance(value, bytes):
        digest = _sha256(value)
        try:
            loaded = json.loads(value.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
            if not isinstance(loaded, Mapping) or value != canonical_json_bytes(loaded):
                raise ValueError("non_canonical")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return None, digest, [f"{label}_bytes_invalid:{str(exc) or 'invalid'}"]
        return dict(loaded), digest, []
    if not isinstance(value, Mapping):
        return None, None, [f"{label}_missing_or_invalid"]
    try:
        raw = canonical_json_bytes(value)
        loaded = json.loads(raw.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, None, [f"{label}_invalid:{str(exc) or 'invalid'}"]
    return dict(loaded), _sha256(raw), []


def _parse_amount(row: Mapping[str, object], field: str, reasons: list[str]) -> Decimal | None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        reasons.append(f"{field}_missing_or_invalid")
        return None
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        reasons.append(f"{field}_invalid")
        return None
    if not amount.is_finite():
        reasons.append(f"{field}_non_finite")
        return None
    if amount < 0:
        reasons.append(f"{field}_negative")
        return None
    return amount


def _parse_time(value: object, field: str, reasons: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        reasons.append(f"{field}_missing_or_invalid")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        reasons.append(f"{field}_invalid")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        reasons.append(f"{field}_not_timezone_aware")
        return None
    return parsed.astimezone(timezone.utc)


def _time_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_fields(row: Mapping[str, object], fields: set[str], label: str, reasons: list[str]) -> None:
    for field in sorted(fields - set(row)):
        reasons.append(f"{label}_field_missing:{field}")


def _require_provenance(row: Mapping[str, object], label: str, reasons: list[str]) -> None:
    provenance = row.get("source_provenance")
    if not isinstance(provenance, list) or not provenance:
        reasons.append(f"{label}_source_provenance_missing")
        return
    for item in provenance:
        if not isinstance(item, Mapping) or not _valid_id(item.get("source_id")) or not _valid_id(item.get("source_kind")) or not _valid_sha256(item.get("content_sha256")):
            reasons.append(f"{label}_source_provenance_invalid")


def _records(value: object, label: str, id_key: str, reasons: list[str]) -> list[dict[str, object]]:
    if not isinstance(value, list):
        reasons.append(f"{label}_missing_or_invalid")
        return []
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            reasons.append(f"{label}_record_invalid")
            continue
        record = dict(item)
        record_id = record.get(id_key)
        if not _valid_id(record_id):
            reasons.append(f"{label}_id_invalid")
            continue
        if record_id in seen:
            reasons.append(f"{label}_duplicate_id:{record_id}")
        seen.add(record_id)
        result.append(record)
    return sorted(result, key=lambda item: str(item.get(id_key)))


def _manifest_shape(manifest: Mapping[str, object], project_id: str, reasons: list[str]) -> dict[str, object]:
    required = {
        "schema_id", "manifest_id", "manifest_version", "project_id", "as_of", "authority",
        "coverage_semantics", "coverage", "accounting_sources", "cohorts", "logical_paid_tasks",
        "retries", "physical_attempts", "reservation_ids", "cost_entry_ids",
    }
    missing = sorted(required - set(manifest))
    if missing:
        reasons.append("coverage_manifest_fields_missing:" + ",".join(missing))
    if manifest.get("schema_id") != COVERAGE_MANIFEST_SCHEMA:
        reasons.append("coverage_manifest_schema_invalid")
    if manifest.get("project_id") != project_id:
        reasons.append("coverage_manifest_project_mismatch")
    if not _valid_id(manifest.get("manifest_id")) or not _valid_id(manifest.get("manifest_version")):
        reasons.append("coverage_manifest_identity_invalid")
    authority = manifest.get("authority")
    if not isinstance(authority, Mapping) or not _valid_id(authority.get("authority_id")) or not _valid_id(authority.get("authority_version")):
        reasons.append("coverage_manifest_authority_invalid")
    else:
        _require_provenance(authority, "coverage_manifest_authority", reasons)
    semantics = manifest.get("coverage_semantics")
    if not isinstance(semantics, Mapping):
        reasons.append("coverage_manifest_semantics_invalid")
    else:
        expected = {"scope", "logical_paid_tasks", "retries", "physical_attempts", "cohorts", "accounting_sources", "reservations", "actuals", "pricing"}
        if set(semantics) != expected or any(not _valid_id(semantics.get(key)) for key in expected):
            reasons.append("coverage_manifest_semantics_invalid")
    coverage = manifest.get("coverage")
    if not isinstance(coverage, Mapping) or set(coverage) != _COVERAGE_KEYS or any(type(coverage.get(key)) is not bool for key in _COVERAGE_KEYS):
        reasons.append("coverage_manifest_assertion_invalid")
    elif not all(coverage.values()):
        reasons.append("coverage_manifest_incomplete")
    result = dict(manifest)
    for key, id_key in (("accounting_sources", "source_id"), ("cohorts", "cohort_id"), ("logical_paid_tasks", "logical_task_id"), ("retries", "task_run_id"), ("physical_attempts", "physical_attempt_id")):
        rows = _records(manifest.get(key), f"coverage_manifest_{key}", id_key, reasons)
        result[key] = rows
        for row in rows:
            _require_fields(row, {id_key, "scope", "source_provenance"}, f"coverage_manifest_{key}", reasons)
            _require_provenance(row, f"coverage_manifest_{key}", reasons)
        if key == "accounting_sources":
            for row in rows:
                if not _valid_id(row.get("source_type")) or not _valid_sha256(row.get("content_sha256")):
                    reasons.append("coverage_manifest_accounting_source_invalid")
        if key == "logical_paid_tasks":
            for row in rows:
                if not _valid_id(row.get("cohort_id")):
                    reasons.append("coverage_manifest_logical_task_invalid")
        if key == "retries":
            for row in rows:
                if not _valid_id(row.get("logical_task_id")) or type(row.get("attempt_number")) is not int or row.get("attempt_number", 0) < 1:
                    reasons.append("coverage_manifest_retry_invalid")
                physical_ids = row.get("physical_attempt_ids")
                if not isinstance(physical_ids, list) or any(not _valid_id(item) for item in physical_ids):
                    reasons.append("coverage_manifest_retry_physical_attempts_invalid")
        if key == "physical_attempts":
            for row in rows:
                if not _valid_id(row.get("cohort_id")) or not isinstance(row.get("logical_task_ids"), list) or not row.get("logical_task_ids") or any(not _valid_id(item) for item in row.get("logical_task_ids", [])):
                    reasons.append("coverage_manifest_physical_attempt_invalid")
    for key in ("reservation_ids", "cost_entry_ids"):
        values = manifest.get(key)
        if not isinstance(values, list) or any(not _valid_id(item) for item in values) or len(set(values)) != len(values):
            reasons.append(f"coverage_manifest_{key}_invalid")
        else:
            result[key] = sorted(values)
    return result


def _evidence_shape(evidence: Mapping[str, object], project_id: str, reasons: list[str]) -> dict[str, object]:
    required = {"schema_id", "evidence_id", "evidence_version", "project_id", "as_of", "source_provenance", "runs", *(_RECORD_KEYS.keys())}
    missing = sorted(required - set(evidence))
    if missing:
        reasons.append("accounting_evidence_fields_missing:" + ",".join(missing))
    if evidence.get("schema_id") != ACCOUNTING_EVIDENCE_SCHEMA:
        reasons.append("accounting_evidence_schema_invalid")
    if evidence.get("project_id") != project_id:
        reasons.append("accounting_evidence_project_mismatch")
    if not _valid_id(evidence.get("evidence_id")) or not _valid_id(evidence.get("evidence_version")):
        reasons.append("accounting_evidence_identity_invalid")
    _require_provenance(evidence, "accounting_evidence", reasons)
    runs = _records(evidence.get("runs"), "accounting_evidence_runs", "run_id", reasons)
    for row in runs:
        _require_fields(row, {"run_id", "cohort_id", "scope", "source_provenance"}, "accounting_evidence_run", reasons)
        _require_provenance(row, "accounting_evidence_run", reasons)
    result = dict(evidence)
    result["runs"] = runs
    for key, id_key in _RECORD_KEYS.items():
        result[key] = _records(evidence.get(key), f"accounting_evidence_{key}", id_key, reasons)
    return result


def _normalised_records(value: object, id_key: str) -> list[dict[str, object]]:
    rows = value if isinstance(value, list) else []
    return sorted((dict(row) for row in rows if isinstance(row, Mapping)), key=lambda row: str(row.get(id_key)))


def _reconcile(
    evidence: Mapping[str, object], manifest: Mapping[str, object], project_id: str, reasons: list[str]
) -> tuple[Decimal | None, Decimal | None, tuple[str, ...], tuple[str, ...]]:
    runs = {row.get("run_id"): row for row in _normalised_records(evidence.get("runs"), "run_id")}
    cohorts = {row.get("cohort_id"): row for row in _normalised_records(evidence.get("cohorts"), "cohort_id")}
    tasks = {row.get("model_task_id"): row for row in _normalised_records(evidence.get("logical_tasks"), "model_task_id")}
    attempts = _normalised_records(evidence.get("task_attempts"), "task_run_id")
    reservations = {row.get("reservation_id"): row for row in _normalised_records(evidence.get("reservations"), "reservation_id")}
    costs = {row.get("entry_key"): row for row in _normalised_records(evidence.get("cost_entries"), "entry_key")}
    physical = {row.get("physical_attempt_id"): row for row in _normalised_records(evidence.get("physical_attempts"), "physical_attempt_id")}
    provider_attempts = _normalised_records(evidence.get("provider_request_attempts"), "delivery_attempt_id")

    manifest_cohorts = {row.get("cohort_id"): row for row in _normalised_records(manifest.get("cohorts"), "cohort_id")}
    manifest_tasks = {row.get("logical_task_id"): row for row in _normalised_records(manifest.get("logical_paid_tasks"), "logical_task_id")}
    manifest_retries = {row.get("task_run_id"): row for row in _normalised_records(manifest.get("retries"), "task_run_id")}
    manifest_physical = {row.get("physical_attempt_id"): row for row in _normalised_records(manifest.get("physical_attempts"), "physical_attempt_id")}
    manifest_sources = {row.get("source_id"): row for row in _normalised_records(manifest.get("accounting_sources"), "source_id")}

    if set(cohorts) != set(manifest_cohorts):
        reasons.append("cohort_coverage_mismatch")
    if set(tasks) != set(manifest_tasks):
        reasons.append("logical_task_coverage_mismatch")
    if {row.get("task_run_id") for row in attempts} != set(manifest_retries):
        reasons.append("retry_coverage_mismatch")
    if set(physical) != set(manifest_physical):
        reasons.append("physical_attempt_coverage_mismatch")
    if set(reservations) != set(manifest.get("reservation_ids", [])):
        reasons.append("reservation_coverage_mismatch")
    if set(costs) != set(manifest.get("cost_entry_ids", [])):
        reasons.append("actual_cost_coverage_mismatch")
    evidence_sources = {item.get("source_id") for item in evidence.get("source_provenance", []) if isinstance(item, Mapping)}
    if not manifest_sources or not set(manifest_sources).issubset(evidence_sources):
        reasons.append("accounting_source_coverage_mismatch")

    task_cohorts: dict[object, object] = {}
    for task_id, row in tasks.items():
        run = runs.get(row.get("run_id"))
        cohort_id = row.get("cohort_id") or (run or {}).get("cohort_id")
        if not _valid_id(cohort_id) or row.get("run_id") not in runs:
            reasons.append(f"logical_task_run_or_cohort_invalid:{task_id}")
            continue
        task_cohorts[task_id] = cohort_id
        if manifest_tasks.get(task_id, {}).get("cohort_id") != cohort_id:
            reasons.append(f"logical_task_cross_cohort_mismatch:{task_id}")

    for attempt in attempts:
        task_id = attempt.get("model_task_id")
        if task_id not in tasks or type(attempt.get("attempt_number")) is not int or attempt.get("attempt_number", 0) < 1:
            reasons.append(f"task_attempt_identity_invalid:{attempt.get('task_run_id')}")
        retry = manifest_retries.get(attempt.get("task_run_id"))
        if retry is not None and (retry.get("logical_task_id") != task_id or retry.get("attempt_number") != attempt.get("attempt_number")):
            reasons.append(f"retry_identity_mismatch:{attempt.get('task_run_id')}")

    for reservation_id, row in reservations.items():
        cohort_id = row.get("cohort_id")
        if cohort_id not in cohorts or row.get("accounting_currency") != "AUD":
            reasons.append(f"reservation_identity_invalid:{reservation_id}")
        _parse_amount(row, "reserved_amount", reasons)

    actual_by_reservation: dict[object, Decimal] = {}
    releases_by_reservation: dict[object, Decimal] = {}
    actual_total = Decimal("0")
    credits = Decimal("0")
    adjustment_debits = Decimal("0")
    adjustment_credits = Decimal("0")
    cost_seen_physical: set[object] = set()
    for entry_id, row in costs.items():
        if row.get("cohort_id") not in cohorts or row.get("accounting_currency") != "AUD" or row.get("entry_type") not in {"actual", "reservation_release", "credit", "adjustment"}:
            reasons.append(f"cost_entry_identity_invalid:{entry_id}")
        amount = _parse_amount(row, "accounting_amount", reasons)
        if amount is None:
            continue
        reservation_id = row.get("reservation_id")
        if reservation_id not in reservations:
            reasons.append(f"cost_entry_reservation_missing:{entry_id}")
        elif reservations[reservation_id].get("cohort_id") != row.get("cohort_id"):
            reasons.append(f"cost_entry_cross_cohort_mismatch:{entry_id}")
        if row.get("entry_type") == "actual":
            actual_total += amount
            if reservation_id in reservations:
                actual_by_reservation[reservation_id] = actual_by_reservation.get(reservation_id, Decimal("0")) + amount
            if not _valid_id(row.get("pricing_snapshot_id")) or not _valid_id(row.get("fx_snapshot_id")):
                physical_id = row.get("physical_attempt_id")
                if _valid_id(physical_id):
                    cost_seen_physical.add(physical_id)
                reasons.append(f"unpriced_actual_cost:{entry_id}")
        elif row.get("entry_type") == "reservation_release":
            releases_by_reservation[reservation_id] = releases_by_reservation.get(reservation_id, Decimal("0")) + amount
        elif row.get("entry_type") == "credit":
            credits += amount
        elif row.get("adjustment_direction") == "debit":
            adjustment_debits += amount
        elif row.get("adjustment_direction") == "credit":
            adjustment_credits += amount

    outstanding = Decimal("0")
    for reservation_id, row in reservations.items():
        amount = _parse_amount(row, "reserved_amount", reasons)
        if amount is None or row.get("status") == "expired":
            continue
        consumed = min(actual_by_reservation.get(reservation_id, Decimal("0")), amount)
        released = releases_by_reservation.get(reservation_id, Decimal("0"))
        remaining = amount - consumed - released
        if remaining < 0:
            reasons.append(f"reservation_reconciliation_negative:{reservation_id}")
        else:
            outstanding += remaining
    net_actual = actual_total + adjustment_debits - credits - adjustment_credits

    physical_to_attempts: dict[object, list[dict[str, object]]] = {}
    for attempt in provider_attempts:
        physical_id = attempt.get("physical_attempt_id")
        physical_to_attempts.setdefault(physical_id, []).append(attempt)
        if physical_id not in physical:
            reasons.append(f"provider_attempt_physical_missing:{attempt.get('delivery_attempt_id')}")
    pending: set[str] = set()
    ambiguous: set[str] = set()
    unpriced: set[str] = set(cost_seen_physical)
    for physical_id, row in physical.items():
        if not _valid_id(row.get("cohort_id")) or row.get("cohort_id") not in cohorts or row.get("run_id") not in runs:
            reasons.append(f"physical_attempt_identity_invalid:{physical_id}")
        run = runs.get(row.get("run_id"))
        if run is not None and row.get("cohort_id") != run.get("cohort_id"):
            reasons.append(f"physical_attempt_cross_cohort_mismatch:{physical_id}")
        if physical_id not in physical_to_attempts:
            reasons.append(f"physical_attempt_retry_identity_missing:{physical_id}")
            pending.add(str(physical_id))
        status = row.get("status")
        statuses = {status} | {attempt.get("status") for attempt in physical_to_attempts.get(physical_id, [])}
        if statuses & _AMBIGUOUS_STATUSES:
            ambiguous.add(str(physical_id))
        elif statuses & _PENDING_STATUSES:
            pending.add(str(physical_id))
        elif status not in _TERMINAL_PHYSICAL_STATUSES:
            reasons.append(f"physical_attempt_status_unknown:{physical_id}")
        if status in {"receipt_persisted", "validated"} and not any(
            entry.get("entry_type") == "actual"
            and entry.get("physical_attempt_id") == physical_id
            and _valid_id(entry.get("pricing_snapshot_id"))
            and _valid_id(entry.get("fx_snapshot_id"))
            for entry in costs.values()
        ):
            unpriced.add(str(physical_id))
    if not physical:
        reasons.append("physical_attempt_evidence_empty")
    if not reservations:
        reasons.append("reservation_evidence_empty")
    if not costs:
        reasons.append("actual_cost_evidence_empty")
    if not physical_to_attempts and physical:
        reasons.append("provider_attempt_evidence_empty")
    return net_actual, outstanding if reservations else None, tuple(sorted(pending | ambiguous)), tuple(sorted(unpriced))


def build_project_budget_snapshot(
    accounting_evidence: Mapping[str, object] | bytes | None,
    coverage_manifest: Mapping[str, object] | bytes | None,
    *,
    project_id: str,
    now: datetime,
    max_evidence_age: timedelta = DEFAULT_MAX_EVIDENCE_AGE,
) -> ProjectBudgetSnapshotCandidate:
    """Build a deterministic candidate from immutable evidence and a manifest.

    Inputs are normalized to canonical UTF-8 JSON for replay.  A complete
    candidate is still ``CANDIDATE_NOT_ATTESTED`` because this function has no
    independent authority for the input claims or its own output hash.
    """

    reasons: list[str] = []
    if not _valid_id(project_id):
        reasons.append("project_id_missing_or_invalid")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        reasons.append("verification_now_not_timezone_aware")
    if not isinstance(max_evidence_age, timedelta) or max_evidence_age <= timedelta(0):
        reasons.append("max_evidence_age_invalid")
    evidence, evidence_hash, load_reasons = _load_object(accounting_evidence, "accounting_evidence")
    reasons.extend(load_reasons)
    manifest, manifest_hash, load_reasons = _load_object(coverage_manifest, "coverage_manifest")
    reasons.extend(load_reasons)
    if evidence is None or manifest is None:
        return ProjectBudgetSnapshotCandidate(status="INCOMPLETE_OR_UNKNOWN", reasons=_unique_reasons(reasons))

    evidence = _evidence_shape(evidence, project_id, reasons)
    manifest = _manifest_shape(manifest, project_id, reasons)
    try:
        evidence_hash = _sha256(canonical_json_bytes(evidence))
        manifest_hash = _sha256(canonical_json_bytes(manifest))
    except (TypeError, ValueError) as exc:
        reasons.append(f"input_canonicalisation_failed:{exc}")
    evidence_as_of = _parse_time(evidence.get("as_of"), "accounting_evidence_as_of", reasons)
    manifest_as_of = _parse_time(manifest.get("as_of"), "coverage_manifest_as_of", reasons)
    now_utc = now.astimezone(timezone.utc) if isinstance(now, datetime) and now.tzinfo else now
    if evidence_as_of is not None and manifest_as_of is not None and isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None and isinstance(max_evidence_age, timedelta) and max_evidence_age > timedelta(0):
        if evidence_as_of != manifest_as_of:
            reasons.append("evidence_manifest_as_of_mismatch")
        if evidence_as_of > now_utc:
            reasons.append("evidence_as_of_in_future")
        elif now_utc - evidence_as_of > max_evidence_age:
            reasons.append("accounting_evidence_stale")
    if evidence_hash is None or manifest_hash is None:
        reasons.append("input_provenance_hash_missing")

    actual, outstanding, pending_or_ambiguous, unpriced = _reconcile(evidence, manifest, project_id, reasons)
    as_of_text = _time_text(evidence_as_of) if evidence_as_of is not None else None
    coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), Mapping) else {}
    candidate = {
        "schema_id": PROJECT_BUDGET_SNAPSHOT_SCHEMA,
        "project_id": project_id,
        "as_of": as_of_text,
        "currency": "AUD",
        "actual_aud": None if actual is None else str(actual),
        "outstanding_reservations_aud": None if outstanding is None else str(outstanding),
        "pending_or_ambiguous_physical_attempts": [
            {"physical_attempt_id": item, "state": "pending_or_ambiguous"}
            for item in pending_or_ambiguous
        ],
        "unpriced_physical_attempts": [
            {"physical_attempt_id": item, "state": "unpriced"}
            for item in unpriced
        ],
        "coverage": dict(coverage),
        "manifest_identity": {
            "manifest_id": manifest.get("manifest_id"),
            "manifest_version": manifest.get("manifest_version"),
            "manifest_sha256": manifest_hash,
            "authority": manifest.get("authority"),
        },
        "accounting_evidence_identity": {
            "evidence_id": evidence.get("evidence_id"),
            "evidence_version": evidence.get("evidence_version"),
            "evidence_sha256": evidence_hash,
            "source_provenance": evidence.get("source_provenance"),
        },
        "deduplication": {
            "logical_task_ids": sorted(str(item) for item in manifest.get("logical_paid_tasks", []) if isinstance(item, Mapping) for item in [item.get("logical_task_id")]),
            "retry_ids": sorted(str(item) for item in manifest.get("retries", []) if isinstance(item, Mapping) for item in [item.get("task_run_id")]),
            "physical_attempt_ids": sorted(str(item) for item in manifest.get("physical_attempts", []) if isinstance(item, Mapping) for item in [item.get("physical_attempt_id")]),
            "reservation_ids": sorted(str(item) for item in manifest.get("reservation_ids", [])),
            "cost_entry_ids": sorted(str(item) for item in manifest.get("cost_entry_ids", [])),
        },
        "attestation": {
            "state": "CANDIDATE_NOT_ATTESTED",
            "independent_trust": "NOT_SUPPLIED",
            "request_ticket": None,
            "send_authorization": "not_authorized_for_send",
        },
    }
    try:
        snapshot_bytes = canonical_json_bytes(candidate)
    except (TypeError, ValueError) as exc:
        reasons.append(f"candidate_canonicalisation_failed:{exc}")
        return ProjectBudgetSnapshotCandidate(status="INCOMPLETE_OR_UNKNOWN", reasons=_unique_reasons(reasons))
    snapshot_hash = _sha256(snapshot_bytes)
    status: SnapshotStatus = "CANDIDATE_NOT_ATTESTED" if not reasons and not pending_or_ambiguous and not unpriced else "INCOMPLETE_OR_UNKNOWN"
    if pending_or_ambiguous:
        reasons.append("unresolved_physical_attempts_present")
    if unpriced:
        reasons.append("unpriced_physical_attempts_present")
    return ProjectBudgetSnapshotCandidate(
        status=status,
        snapshot_bytes=snapshot_bytes,
        snapshot_sha256=snapshot_hash,
        as_of=as_of_text,
        actual_aud=actual,
        outstanding_reservations_aud=outstanding,
        pending_or_ambiguous_physical_attempt_ids=pending_or_ambiguous,
        unpriced_physical_attempt_ids=unpriced,
        reasons=_unique_reasons(reasons),
    )


reconcile_project_budget_snapshot = build_project_budget_snapshot


__all__ = [
    "ACCOUNTING_EVIDENCE_SCHEMA",
    "COVERAGE_MANIFEST_SCHEMA",
    "DEFAULT_MAX_EVIDENCE_AGE",
    "PROJECT_BUDGET_SNAPSHOT_SCHEMA",
    "ProjectBudgetSnapshotCandidate",
    "build_project_budget_snapshot",
    "reconcile_project_budget_snapshot",
]
