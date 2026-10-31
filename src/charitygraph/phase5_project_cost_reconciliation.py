"""Read-only, project-wide reconciliation of persisted Phase-5 costs.

This module is deliberately a projection over the existing catalogue export.
It does not create a ledger, migrate SQLite, acquire evidence, call a
provider, reserve money, or persist a result.  The catalogue adapter supplies
the allow-listed rows; this module only performs exact identifier joins,
Decimal arithmetic, and fail-closed accounting classification.

The persisted schema records a cost entry's task attempt and reservation, but
not a direct provider-receipt column.  Receipt/request identity is therefore
joined through the existing task -> request item -> physical attempt ->
receipt relationships.  A missing or contradictory relationship is an
unreconciled charge, never a guessed zero or a project-complete total.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from .phase5_operator_health_catalogue import (
    Phase5CatalogueSnapshot,
    Phase5OperatorHealthCatalogueAdapter,
)


SCHEMA_ID = "charitygraph.phase5.project-cost-reconciliation"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"


class ProjectCostReconciliationError(ValueError):
    """Raised when the requested read-only projection cannot be formed."""


@dataclass(frozen=True)
class ProjectCostReconciliationProjection:
    """Canonical diagnostic document and content identity."""

    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


_SUPPORTED_CURRENCIES = {"AUD"}
_ACTUAL_TYPES = {"actual", "provider_actual"}
_ESTIMATE_TYPES = {"estimate", "forecast"}
_RESERVATION_TYPES = {"reservation"}
_RELEASE_TYPES = {"reservation_release", "release"}
_CREDIT_TYPES = {"credit", "adjustment_credit"}
_KNOWN_TYPES = _ACTUAL_TYPES | _ESTIMATE_TYPES | _RESERVATION_TYPES | _RELEASE_TYPES | _CREDIT_TYPES | {"adjustment", "adjustment_debit"}
_AMBIGUOUS_STATUSES = {"ambiguous", "send_ambiguous", "provider_crossing_ambiguous", "held"}


def _canonical(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, Mapping):
        return {str(key): _canonical(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(child) for child in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _decimal(value: Any, label: str) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (bool, float)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def _identifier(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return None


def _non_empty(value: Any) -> str | None:
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _currency_code(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 3 and value == value.upper() and value.isalpha()


def _row_map(rows: Sequence[Mapping[str, Any]], *names: str) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    duplicate_ids: list[str] = []
    for row in rows:
        identity = _identifier(row, *names)
        if identity is None:
            continue
        if identity in indexed and _canonical(indexed[identity]) != _canonical(row):
            duplicate_ids.append(identity)
        else:
            indexed.setdefault(identity, row)
    return indexed, sorted(set(duplicate_ids))


def _timestamp_is_valid(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _safe_provenance(row: Mapping[str, Any], snapshot: Phase5CatalogueSnapshot) -> dict[str, str]:
    return {
        "source_id": str(row.get("source_id") or snapshot.source_id),
        "source_version": str(row.get("source_version") or snapshot.source_version),
        "evidence_basis": str(row.get("evidence_basis") or snapshot.evidence_basis),
    }


def _usage_state(row: Mapping[str, Any]) -> str:
    marker = _non_empty(row.get("usage_coverage_state"))
    if marker in {"ambiguous", "invalid"}:
        return "ambiguous"
    if marker == "missing":
        return "missing"
    usage = row.get("usage")
    if not isinstance(usage, Mapping):
        return "missing"
    for name in ("input_tokens", "output_tokens"):
        value = usage.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return "ambiguous"
    return "observed"


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status") or "UNKNOWN")


def _is_ambiguous_crossing(
    request: Mapping[str, Any] | None,
    attempt: Mapping[str, Any] | None,
    physical: Mapping[str, Any] | None,
) -> bool:
    return any(
        row is not None and (
            _status(row) in _AMBIGUOUS_STATUSES
            or str(row.get("trace_status") or "").lower() in _AMBIGUOUS_STATUSES
        )
        for row in (request, attempt, physical)
    )


def _replayed(attempt: Mapping[str, Any] | None) -> bool:
    if attempt is None:
        return False
    ordinal = attempt.get("attempt_ordinal")
    try:
        return (int(ordinal) > 1) if ordinal is not None else bool(_identifier(attempt, "predecessor_attempt_id", "replayed_from", "recovery_of"))
    except (TypeError, ValueError):
        return True


def _amount_record(state: str, amount: Decimal | None, count: int, reason: str) -> dict[str, Any]:
    known = state in {"known", "observed", "estimate"}
    return {
        "state": state,
        "amount": _decimal_text(amount) if known else None,
        "currency": "AUD" if known else None,
        "entry_count": count,
        "reason": reason,
    }


def _blocker(code: str, count: int, *, severity: str = "error", identities: Sequence[str] = (), detail: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "count": count,
        "identifiers": sorted(set(str(value) for value in identities)),
    }
    if detail:
        result["detail"] = detail
    return result


def _boundary_diagnostic(
    boundary: Mapping[str, Any] | None,
    *,
    selected_run_ids: Sequence[str],
    found_run_ids: Sequence[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if boundary is None:
        return {
            "state": "absent",
            "authenticated": False,
            "complete": False,
            "boundary_id": None,
            "version": None,
            "as_of": None,
            "run_ids": [],
        }, [_blocker("MISSING_PROJECT_WIDE_LEDGER", 1, detail="No authenticated external project-wide coverage boundary was supplied.")]

    boundary_id = _non_empty(boundary.get("boundary_id") or boundary.get("source_id") or boundary.get("ledger_source_id"))
    version = _non_empty(boundary.get("version") or boundary.get("ledger_version"))
    as_of = boundary.get("as_of") or boundary.get("ledger_as_of")
    authenticated = boundary.get("authenticated") is True
    complete = boundary.get("complete") is True
    run_values = boundary.get("run_ids")
    run_ids = sorted(str(value) for value in run_values) if isinstance(run_values, Sequence) and not isinstance(run_values, (str, bytes, bytearray)) else []
    reasons: list[dict[str, Any]] = []
    if not boundary_id or not version or not _timestamp_is_valid(as_of):
        reasons.append(_blocker("INVALID_PROJECT_WIDE_LEDGER_PROVENANCE", 1))
    if not authenticated:
        reasons.append(_blocker("UNAUTHENTICATED_PROJECT_WIDE_LEDGER", 1))
    if not complete:
        reasons.append(_blocker("INCOMPLETE_PROJECT_WIDE_LEDGER", 1))
    if run_ids != sorted(set(str(value) for value in found_run_ids)):
        reasons.append(_blocker("PROJECT_LEDGER_RUN_SCOPE_MISMATCH", 1))
    state = "authenticated_complete" if not reasons else "unreconciled"
    return {
        "state": state,
        "authenticated": authenticated,
        "complete": complete,
        "boundary_id": boundary_id,
        "version": version,
        "as_of": as_of if isinstance(as_of, str) else None,
        "run_ids": run_ids,
    }, reasons


def reconcile_project_cost_snapshot(
    snapshot: Phase5CatalogueSnapshot,
    *,
    coverage_boundary: Mapping[str, Any] | None = None,
) -> ProjectCostReconciliationProjection:
    """Reconcile one explicit multi-run catalogue snapshot without I/O."""

    if not isinstance(snapshot, Phase5CatalogueSnapshot):
        raise ProjectCostReconciliationError("snapshot must be a Phase5CatalogueSnapshot from the existing runtime export")

    records = snapshot.records
    runs = tuple(records.get("runs", ()))
    tasks = tuple(records.get("tasks", ()))
    task_attempts = tuple(records.get("task_attempts", ()))
    requests = tuple(records.get("requests", ()))
    attempts = tuple(records.get("attempts", ()))
    physical = tuple(records.get("physical", ()))
    receipts = tuple(records.get("receipts", ()))
    reservations = tuple(records.get("reservations", ()))
    cost_entries = tuple(records.get("cost_entries", ()))

    run_map, duplicate_runs = _row_map(runs, "run_id")
    task_map, duplicate_tasks = _row_map(tasks, "model_task_id", "task_id")
    task_attempt_map, duplicate_task_attempts = _row_map(task_attempts, "task_run_id", "attempt_id")
    request_map, duplicate_requests = _row_map(requests, "provider_request_item_id", "request_item_id", "request_id")
    delivery_map, duplicate_delivery_attempts = _row_map(attempts, "delivery_attempt_id", "attempt_id")
    physical_map, duplicate_physical = _row_map(physical, "physical_attempt_id")
    receipt_map, duplicate_receipts = _row_map(receipts, "provider_receipt_id", "receipt_id")
    reservation_map, duplicate_reservations = _row_map(reservations, "reservation_id")

    request_by_task: dict[str, Mapping[str, Any]] = {}
    for request in requests:
        task_id = _identifier(request, "model_task_id", "task_id")
        if task_id:
            request_by_task.setdefault(task_id, request)
    attempt_by_request: dict[str, Mapping[str, Any]] = {}
    for attempt in attempts:
        request_id = _identifier(attempt, "provider_request_item_id", "request_item_id")
        if request_id:
            attempt_by_request.setdefault(request_id, attempt)

    blockers: list[dict[str, Any]] = []
    for code, values in (
        ("CONFLICTING_RUN_IDENTITY", duplicate_runs),
        ("CONFLICTING_TASK_IDENTITY", duplicate_tasks),
        ("CONFLICTING_TASK_ATTEMPT_IDENTITY", duplicate_task_attempts),
        ("CONFLICTING_REQUEST_IDENTITY", duplicate_requests),
        ("CONFLICTING_DELIVERY_ATTEMPT_IDENTITY", duplicate_delivery_attempts),
        ("CONFLICTING_PHYSICAL_ATTEMPT_IDENTITY", duplicate_physical),
        ("CONFLICTING_RECEIPT_IDENTITY", duplicate_receipts),
        ("CONFLICTING_RESERVATION_IDENTITY", duplicate_reservations),
    ):
        if values:
            blockers.append(_blocker(code, len(values), identities=values))

    schema = dict(snapshot.coverage.get("schema", {}))
    if schema.get("state") != "supported":
        blockers.append(_blocker("STALE_OR_UNSUPPORTED_SCHEMA", 1, detail="The existing runtime export did not attest the supported catalogue schema."))
    if snapshot.coverage.get("run_selection", {}).get("missing"):
        missing = snapshot.coverage["run_selection"]["missing"]
        blockers.append(_blocker("MISSING_REQUESTED_RUN", len(missing), identities=missing))

    found_run_ids = sorted(str(value) for value in snapshot.run_ids_found)
    boundary, boundary_blockers = _boundary_diagnostic(
        coverage_boundary,
        selected_run_ids=snapshot.run_ids_requested,
        found_run_ids=found_run_ids,
    )
    blockers.extend(boundary_blockers)

    cohort_ids = set()
    for row in reservations:
        cohort = _identifier(row, "cohort_id")
        if cohort:
            cohort_ids.add(cohort)
    charge_records: list[dict[str, Any]] = []
    reservation_records: list[dict[str, Any]] = []
    estimate_records: list[dict[str, Any]] = []
    unreconciled_records: list[dict[str, Any]] = []
    known_actual_total = Decimal(0)
    known_actual_keys: set[str] = set()
    actual_by_receipt: dict[str, tuple[tuple[Any, ...], str]] = {}
    actual_duplicate_ids: list[str] = []
    conflicting_receipt_ids: list[str] = []
    actual_count = 0
    unknown_cost_ids: list[str] = []
    missing_price_ids: list[str] = []
    missing_fx_ids: list[str] = []
    missing_usage_ids: list[str] = []
    ambiguous_crossing_ids: list[str] = []
    missing_receipt_ids: list[str] = []
    missing_link_ids: list[str] = []
    invalid_amount_ids: list[str] = []
    invalid_provider_amount_ids: list[str] = []
    accounting_mismatch_ids: list[str] = []
    estimate_total = Decimal(0)
    reservation_total = Decimal(0)
    reservation_unknown_ids: list[str] = []

    def linkage_for_cost(row: Mapping[str, Any]) -> dict[str, Any]:
        run_id = _identifier(row, "run_id")
        task_run_id = _identifier(row, "task_run_id")
        task_attempt = task_attempt_map.get(task_run_id or "")
        task_id = _identifier(task_attempt or {}, "model_task_id", "task_id")
        task = task_map.get(task_id or "")
        request = request_by_task.get(task_id or "")
        request_id = _identifier(request or {}, "provider_request_item_id", "request_item_id", "request_id")
        attempt = attempt_by_request.get(request_id or "")
        physical_id = _identifier(request or {}, "physical_attempt_id") or _identifier(attempt or {}, "physical_attempt_id")
        physical_row = physical_map.get(physical_id or "")
        receipt_id = _identifier(request or {}, "provider_receipt_id", "receipt_id")
        receipt = receipt_map.get(receipt_id or "")
        if receipt is None and physical_id:
            for candidate in receipts:
                if _identifier(candidate, "physical_attempt_id") == physical_id:
                    receipt = candidate
                    receipt_id = _identifier(candidate, "provider_receipt_id", "receipt_id")
                    break
        reservation_id = _identifier(row, "reservation_id")
        reservation = reservation_map.get(reservation_id or "")
        cohort_id = _identifier(row, "cohort_id") or _identifier(reservation or {}, "cohort_id")
        return {
            "run_id": run_id,
            "cohort_id": cohort_id,
            "task_run_id": task_run_id,
            "model_task_id": task_id,
            "provider_request_item_id": request_id,
            "provider_request_id": _identifier(request or {}, "provider_request_id") or _identifier(attempt or {}, "provider_request_id"),
            "provider_receipt_id": receipt_id,
            "physical_attempt_id": physical_id,
            "delivery_attempt_id": _identifier(attempt or {}, "delivery_attempt_id", "attempt_id"),
            "provider_id": _identifier(request or {}, "provider_id"),
            "model_route": _identifier(request or {}, "model_route"),
            "subject_id": _identifier(task or {}, "subject_id"),
            "scope_id": _identifier(task or {}, "scope_id"),
            "reservation_id": reservation_id,
            "request": request,
            "attempt": attempt,
            "physical": physical_row,
            "receipt": receipt,
            "reservation": reservation,
            "task": task,
        }

    def public_linkage(linkage: Mapping[str, Any]) -> dict[str, Any]:
        return {key: linkage.get(key) for key in (
            "run_id", "cohort_id", "task_run_id", "model_task_id", "provider_request_item_id",
            "provider_request_id", "provider_receipt_id", "physical_attempt_id", "delivery_attempt_id",
            "provider_id", "model_route", "subject_id", "scope_id", "reservation_id",
        )}

    for row in sorted(cost_entries, key=lambda item: str(_identifier(item, "entry_key", "entry_id") or "")):
        entry_id = _identifier(row, "entry_key", "entry_id")
        if entry_id is None:
            entry_id = f"missing-cost:{len(unreconciled_records)}"
        entry_type = str(row.get("entry_type") or "unknown")
        linkage = linkage_for_cost(row)
        accounting_amount = _decimal(row.get("accounting_amount"), entry_id + ".accounting_amount")
        aud_amount = _decimal(row.get("aud_amount"), entry_id + ".aud_amount")
        amount = accounting_amount if accounting_amount is not None else (aud_amount if aud_amount is not None else _decimal(row.get("amount"), entry_id))
        currency = _non_empty(row.get("accounting_currency") or row.get("currency"))
        provenance = _safe_provenance(row, snapshot)
        if entry_type in _ACTUAL_TYPES:
            actual_count += 1
            reasons: list[str] = []
            if amount is None or currency not in _SUPPORTED_CURRENCIES:
                invalid_amount_ids.append(entry_id)
                reasons.append("MISSING_OR_INVALID_AUD_AMOUNT")
            provider_amount = _decimal(row.get("provider_amount"), entry_id + ".provider_amount")
            provider_currency = _non_empty(row.get("provider_currency"))
            if provider_amount is None or not _currency_code(provider_currency):
                invalid_provider_amount_ids.append(entry_id)
                reasons.append("MISSING_OR_INVALID_PROVIDER_AMOUNT")
            if accounting_amount is not None and aud_amount is not None and accounting_amount != aud_amount:
                accounting_mismatch_ids.append(entry_id)
                reasons.append("ACCOUNTING_AMOUNT_MISMATCH")
            if _non_empty(row.get("pricing_snapshot_id")) is None:
                missing_price_ids.append(entry_id)
                reasons.append("MISSING_PRICING_SNAPSHOT")
            if _non_empty(row.get("fx_snapshot_id")) is None:
                missing_fx_ids.append(entry_id)
                reasons.append("MISSING_FX_SNAPSHOT")
            if linkage["provider_receipt_id"] is None or linkage["receipt"] is None:
                missing_receipt_ids.append(entry_id)
                reasons.append("MISSING_PROVIDER_RECEIPT_IDENTITY")
            if linkage["model_task_id"] is None or linkage["provider_request_item_id"] is None or linkage["subject_id"] is None:
                missing_link_ids.append(entry_id)
                reasons.append("INCOMPLETE_RUNTIME_LINKAGE")
            if _is_ambiguous_crossing(linkage["request"], linkage["attempt"], linkage["physical"]):
                ambiguous_crossing_ids.append(entry_id)
                reasons.append("AMBIGUOUS_PROVIDER_CROSSING")
            receipt = linkage["receipt"]
            if receipt is not None:
                usage_state = _usage_state(receipt)
                if usage_state != "observed":
                    receipt_id = linkage["provider_receipt_id"] or "missing-receipt"
                    missing_usage_ids.append(receipt_id)
            else:
                usage_state = "missing"
            signature = (
                _decimal_text(amount), currency, _decimal_text(provider_amount), provider_currency,
                _non_empty(row.get("pricing_snapshot_id")), _non_empty(row.get("fx_snapshot_id")),
                linkage["run_id"], linkage["task_run_id"], linkage["provider_receipt_id"],
            )
            receipt_id = linkage["provider_receipt_id"]
            if receipt_id and receipt_id in actual_by_receipt:
                prior_signature, prior_entry = actual_by_receipt[receipt_id]
                if receipt_id in conflicting_receipt_ids:
                    reasons.append("CONFLICTING_DUPLICATE_RECEIPT")
                elif prior_signature == signature:
                    actual_duplicate_ids.append(receipt_id)
                    blockers.append(_blocker("DUPLICATE_OR_REPLAYED_RECEIPT", 1, severity="warning", identities=[receipt_id]))
                    continue
                else:
                    conflicting_receipt_ids.append(receipt_id)
                    prior_record = next((item for item in charge_records if item["entry_key"] == prior_entry), None)
                    if prior_record is not None:
                        prior_amount = _decimal(prior_record.get("amount"), prior_entry)
                        if prior_amount is not None:
                            known_actual_total -= prior_amount
                        charge_records = [item for item in charge_records if item["entry_key"] != prior_entry]
                        known_actual_keys.discard(prior_entry)
                    blockers.append(_blocker("CONFLICTING_DUPLICATE_RECEIPT", 1, identities=[receipt_id]))
                    reasons.append("CONFLICTING_DUPLICATE_RECEIPT")
            elif receipt_id:
                actual_by_receipt[receipt_id] = (signature, entry_id)
            if not reasons and amount is not None:
                known_actual_total += amount
                known_actual_keys.add(entry_id)
                charge_records.append({
                    "entry_key": entry_id,
                    "entry_type": entry_type,
                    "amount": _decimal_text(amount),
                    "currency": currency,
                    "provider_amount": _decimal_text(provider_amount),
                    "provider_currency": provider_currency,
                    "pricing_snapshot_id": _non_empty(row.get("pricing_snapshot_id")),
                    "fx_snapshot_id": _non_empty(row.get("fx_snapshot_id")),
                    "usage_state": usage_state,
                    "replayed_attempt": _replayed(linkage["attempt"]),
                    "provenance": provenance,
                    "identity": public_linkage(linkage),
                })
            else:
                unreconciled_records.append({
                    "entry_key": entry_id,
                    "entry_type": entry_type,
                    "reasons": sorted(set(reasons)),
                    "provenance": provenance,
                    "identity": public_linkage(linkage),
                })
            continue

        if entry_type in _ESTIMATE_TYPES:
            if amount is not None and currency == "AUD":
                estimate_total += amount
                estimate_records.append({"entry_key": entry_id, "entry_type": entry_type, "amount": _decimal_text(amount), "currency": "AUD", "provenance": provenance, "identity": public_linkage(linkage)})
            else:
                unknown_cost_ids.append(entry_id)
            continue

        if entry_type in _RESERVATION_TYPES | _RELEASE_TYPES | _CREDIT_TYPES or entry_type in {"adjustment", "adjustment_debit"}:
            # These are retained as classified ledger rows, but never folded
            # into incurred provider charges.
            continue

        if entry_type not in _KNOWN_TYPES:
            unknown_cost_ids.append(entry_id)
            unreconciled_records.append({"entry_key": entry_id, "entry_type": entry_type, "reasons": ["UNKNOWN_COST_ENTRY_TYPE"], "provenance": provenance, "identity": public_linkage(linkage)})

    for row in sorted(reservations, key=lambda item: str(_identifier(item, "reservation_id") or "")):
        reservation_id = _identifier(row, "reservation_id") or f"missing-reservation:{len(reservation_records)}"
        amount = _decimal(row.get("reserved_amount", row.get("reserved_aud", row.get("amount"))), reservation_id)
        currency = _non_empty(row.get("accounting_currency") or row.get("currency"))
        state = "known" if amount is not None and currency == "AUD" else "unknown"
        if state == "known":
            reservation_total += amount or Decimal(0)
        else:
            reservation_unknown_ids.append(reservation_id)
        reservation_records.append({
            "reservation_id": reservation_id,
            "run_id": _identifier(row, "run_id"),
            "cohort_id": _identifier(row, "cohort_id"),
            "status": _status(row),
            "amount": _decimal_text(amount) if state == "known" else None,
            "currency": currency if state == "known" else None,
            "state": state,
            "provenance": _safe_provenance(row, snapshot),
        })

    usage_receipts = sorted(receipt_map)
    for receipt_id in usage_receipts:
        state = _usage_state(receipt_map[receipt_id])
        if state != "observed" and receipt_id not in missing_usage_ids:
            missing_usage_ids.append(receipt_id)

    # Provider crossings without an actual entry are still material unknowns.
    for request_id, request in sorted(request_map.items()):
        attempt = attempt_by_request.get(request_id)
        physical_row = physical_map.get(_identifier(request, "physical_attempt_id") or "")
        if _is_ambiguous_crossing(request, attempt, physical_row):
            if request_id not in ambiguous_crossing_ids:
                ambiguous_crossing_ids.append(request_id)
            task = task_map.get(_identifier(request, "model_task_id", "task_id") or "") or {}
            unreconciled_records.append({
                "entry_key": None,
                "entry_type": "provider_crossing",
                "reasons": ["AMBIGUOUS_PROVIDER_CROSSING"],
                "provenance": _safe_provenance(request, snapshot),
                "identity": {
                    "run_id": _identifier(request, "run_id"),
                    "cohort_id": None,
                    "task_run_id": None,
                    "model_task_id": _identifier(request, "model_task_id", "task_id"),
                    "provider_request_item_id": request_id,
                    "provider_request_id": _identifier(request, "provider_request_id"),
                    "provider_receipt_id": _identifier(request, "provider_receipt_id", "receipt_id"),
                    "physical_attempt_id": _identifier(request, "physical_attempt_id"),
                    "delivery_attempt_id": _identifier(attempt or {}, "delivery_attempt_id", "attempt_id"),
                    "provider_id": _identifier(request, "provider_id"),
                    "model_route": _identifier(request, "model_route"),
                    "subject_id": _identifier(task, "subject_id"),
                    "scope_id": _identifier(task, "scope_id"),
                    "reservation_id": None,
                },
            })

    if missing_price_ids:
        blockers.append(_blocker("MISSING_PRICING_SNAPSHOT", len(missing_price_ids), identities=missing_price_ids))
    if missing_fx_ids:
        blockers.append(_blocker("MISSING_FX_SNAPSHOT", len(missing_fx_ids), identities=missing_fx_ids))
    if missing_usage_ids:
        blockers.append(_blocker("MISSING_OR_AMBIGUOUS_USAGE", len(missing_usage_ids), identities=missing_usage_ids, severity="warning"))
    if missing_receipt_ids:
        blockers.append(_blocker("MISSING_PROVIDER_RECEIPT_IDENTITY", len(missing_receipt_ids), identities=missing_receipt_ids))
    if missing_link_ids:
        blockers.append(_blocker("INCOMPLETE_RUNTIME_LINKAGE", len(missing_link_ids), identities=missing_link_ids))
    if invalid_amount_ids:
        blockers.append(_blocker("MISSING_OR_INVALID_AUD_AMOUNT", len(invalid_amount_ids), identities=invalid_amount_ids))
    if invalid_provider_amount_ids:
        blockers.append(_blocker("MISSING_OR_INVALID_PROVIDER_AMOUNT", len(invalid_provider_amount_ids), identities=invalid_provider_amount_ids))
    if accounting_mismatch_ids:
        blockers.append(_blocker("ACCOUNTING_AMOUNT_MISMATCH", len(accounting_mismatch_ids), identities=accounting_mismatch_ids))
    if ambiguous_crossing_ids:
        blockers.append(_blocker("AMBIGUOUS_PROVIDER_CROSSING", len(ambiguous_crossing_ids), identities=ambiguous_crossing_ids))
    if unknown_cost_ids:
        blockers.append(_blocker("UNKNOWN_OR_UNRECONCILED_COST", len(unknown_cost_ids), identities=unknown_cost_ids))
    if reservation_unknown_ids:
        blockers.append(_blocker("UNKNOWN_RESERVATION_AMOUNT", len(reservation_unknown_ids), identities=reservation_unknown_ids))

    # Keep one deterministic diagnostic per blocker code while retaining all
    # identifiers.  Duplicate receipt warnings are intentionally merged too.
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in blockers:
        key = (str(item["code"]), str(item["severity"]))
        prior = merged.get(key)
        if prior is None:
            merged[key] = dict(item)
        else:
            prior["count"] += int(item["count"])
            prior["identifiers"] = sorted(set(prior["identifiers"]) | set(item["identifiers"]))
            if "detail" not in prior and item.get("detail"):
                prior["detail"] = item["detail"]
    blockers = sorted(merged.values(), key=lambda item: (item["severity"], item["code"]))

    known_charge_state = "known" if charge_records else "unknown"
    if not cost_entries:
        known_charge_state = "missing"
    schema_state = schema.get("state")
    coverage_state = "complete" if boundary["state"] == "authenticated_complete" and not blockers else "incomplete"
    if schema_state != "supported" or not found_run_ids:
        coverage_state = "unknown"

    actual = _amount_record(known_charge_state, known_actual_total if charge_records else None, len(charge_records), "auditable actual charges deduplicated by provider receipt identity" if charge_records else "no auditable actual provider charge evidence")
    reserved = _amount_record("known" if reservation_records and not reservation_unknown_ids else "unknown" if reservation_records else "missing", reservation_total if reservation_records and not reservation_unknown_ids else None, len(reservation_records), "persisted reservation rows; reservations are not incurred charges" if reservation_records else "no persisted reservations")
    estimates = _amount_record("estimate" if estimate_records else "missing", estimate_total if estimate_records else None, len(estimate_records), "explicit estimate/forecast rows only" if estimate_records else "no explicit estimate or forecast rows")

    document = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "diagnostic_identity": {
            "projection": "phase5-project-cost-reconciliation",
            "catalogue_id": snapshot.catalogue_id,
            "source_id": snapshot.source_id,
            "source_version": snapshot.source_version,
        },
        "scope": {
            "run_ids_requested": list(snapshot.run_ids_requested),
            "run_ids_found": found_run_ids,
            "cohort_ids_observed": sorted(cohort_ids),
            "subject_ids_observed": sorted({_identifier(row, "subject_id") for row in tasks if _identifier(row, "subject_id")}),
            "scope_ids_observed": sorted({_identifier(row, "scope_id") for row in tasks if _identifier(row, "scope_id")}),
            "provider_ids_observed": sorted({_identifier(row, "provider_id") for row in requests if _identifier(row, "provider_id")}),
            "bounded": True,
        },
        "source_lineage": {
            "source_id": snapshot.source_id,
            "source_version": snapshot.source_version,
            "evidence_basis": snapshot.evidence_basis,
            "basis": "existing Phase5OperatorHealthCatalogueAdapter read-only allowlist plus mechanical runtime joins",
        },
        "coverage": {
            "state": coverage_state,
            "runtime_export": snapshot.coverage,
            "schema": schema,
            "run_selection": snapshot.coverage.get("run_selection", {}),
            "project_wide_boundary": boundary,
            "project_wide_completeness_proven": boundary["state"] == "authenticated_complete" and not blockers,
        },
        "record_counts": {"runs": len(runs), "tasks": len(tasks), "requests": len(requests), "attempts": len(attempts), "receipts": len(receipts), "reservations": len(reservations), "cost_entries": len(cost_entries)},
        "totals": {
            "actual_incurred_charges": actual,
            "reservations": reserved,
            "estimates": estimates,
            "known_charge_basis": "only rows with exact Decimal AUD amount, pricing/FX identifiers, stable receipt identity, complete runtime linkage and non-ambiguous crossing are included",
        },
        "charges": charge_records,
        "reservations": reservation_records,
        "estimates": estimate_records,
        "unreconciled": {"count": len(unreconciled_records), "records": sorted(unreconciled_records, key=lambda item: (str(item.get("entry_key") or ""), _canonical_bytes(item["identity"])) )},
        "blockers": blockers,
        "limitations": [
            "The runtime schema has no direct cost_entries.provider_receipt_id; receipt identity is joined mechanically through existing task/request/physical/receipt records.",
            "Provider-side exactly-once effects, invoice truth, pricing/FX authority validity and any unpersisted external charges are not observed.",
            "No project-wide completeness is asserted without an authenticated, complete boundary covering the selected runs.",
            "Reservations and estimates are reported separately and are never treated as incurred expenditure.",
            "No raw provider payload, result body, prompt, credential or transport exception is retained.",
        ],
    }
    canonical_json = _canonical_bytes(document)
    return ProjectCostReconciliationProjection(document=document, canonical_json=canonical_json, sha256=hashlib.sha256(canonical_json).hexdigest())


def project_phase5_project_cost_reconciliation(
    catalogue: str,
    *,
    run_ids: Sequence[str],
    as_of: str,
    reporting_window_start: str,
    reporting_window_end: str,
    source_id: str | None = None,
    evidence_basis: str = "persisted Phase-5 runtime catalogue; provider evidence not claimed",
    coverage_boundary: Mapping[str, Any] | None = None,
    ledger: Mapping[str, Any] | None = None,
) -> ProjectCostReconciliationProjection:
    """Read selected persisted runs and project a project-wide diagnostic.

    ``ledger`` is a compatibility alias for callers already using the
    operator-health adapter.  It is not trusted unless it also supplies the
    explicit authenticated boundary fields validated by this module.
    """

    adapter = Phase5OperatorHealthCatalogueAdapter(
        catalogue,
        run_ids=run_ids,
        as_of=as_of,
        reporting_window_start=reporting_window_start,
        reporting_window_end=reporting_window_end,
        source_id=source_id,
        evidence_basis=evidence_basis,
        ledger=ledger,
    )
    return reconcile_project_cost_snapshot(adapter.read_snapshot(), coverage_boundary=coverage_boundary or ledger)


def project_phase5_cost_reconciliation(*args: Any, **kwargs: Any) -> ProjectCostReconciliationProjection:
    """Short compatibility spelling for the project reconciliation entrypoint."""

    return project_phase5_project_cost_reconciliation(*args, **kwargs)


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCHEMA",
    "ProjectCostReconciliationError",
    "ProjectCostReconciliationProjection",
    "reconcile_project_cost_snapshot",
    "project_phase5_project_cost_reconciliation",
    "project_phase5_cost_reconciliation",
]
