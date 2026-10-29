"""Pure, caller-bound migration-29 accounting and receipt linkage contract.

This module validates already-materialised mapping views.  It is deliberately
not a catalogue reader, ledger, source export, authority verifier, or send
path.  Amounts are checked for the persisted AUD compatibility relationship,
but no balance or positive total is calculated.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from .contracts.canonical import canonical_json_bytes


CONTRACT_SCHEMA = "charitygraph.sqlite-accounting-contract/1"
CONTRACT_MIGRATION_VERSION = 29
ContractStatus = Literal["CANDIDATE_NOT_ATTESTED", "NOT_ATTESTABLE"]

_AUTHORITY_FIELDS = (
    "source_id",
    "source_kind",
    "source_version",
    "content_sha256",
    "authority_id",
    "authority_version",
    "retention_id",
    "retention_version",
    "retention_status",
)
_VIEW_IDS = {
    "delivery_jobs": "delivery_job_id",
    "tasks": "model_task_id",
    "task_attempts": "task_run_id",
    "cost_entries": "entry_key",
    "physical_attempts": "physical_attempt_id",
    "physical_attempt_members": ("physical_attempt_id", "model_task_id"),
    "provider_request_items": "provider_request_item_id",
    "provider_request_attempts": "delivery_attempt_id",
    "provider_receipts": "provider_receipt_id",
}
_REQUIRED_VIEWS = tuple(_VIEW_IDS)
_REQUIRED_COLUMNS = {
    # These names and joins are the columns in migrations 1, 10, 11, 13 and
    # 20 as present in the current migration-29 catalogue.
    "delivery_jobs": (
        "delivery_job_id", "run_id", "provider_id", "model_route",
        "status", "pricing_snapshot_id",
    ),
    "tasks": ("model_task_id", "run_id", "subject_id"),
    "task_attempts": (
        "task_run_id", "model_task_id", "attempt_number", "status",
        "provider_request_id", "pricing_snapshot_id", "fx_snapshot_id",
        "reservation_id",
    ),
    "cost_entries": (
        "entry_key", "run_id", "task_run_id", "entry_type", "provider_amount",
        "provider_currency", "aud_amount", "pricing_snapshot_id",
        "fx_snapshot_id", "usage_json", "accounting_amount",
        "accounting_currency",
    ),
    "physical_attempts": (
        "physical_attempt_id", "run_id", "subject_id", "status",
        "provider_request_id", "reservation_id",
    ),
    "physical_attempt_members": ("physical_attempt_id", "model_task_id"),
    "provider_request_items": (
        "provider_request_item_id", "run_id", "model_task_id",
        "physical_attempt_id", "delivery_job_id", "provider_id",
        "model_route", "status", "provider_request_id", "provider_receipt_id",
    ),
    "provider_request_attempts": (
        "delivery_attempt_id", "provider_request_item_id", "physical_attempt_id",
        "delivery_job_id", "provider_receipt_id", "status", "provider_request_id",
    ),
    "provider_receipts": (
        "provider_receipt_id", "physical_attempt_id", "provider_request_id",
    ),
}
_TERMINAL_PHYSICAL = {"receipt_persisted", "validated", "failed"}
_TERMINAL_PROVIDER = {"receipt_persisted", "completed", "failed", "expired", "cancelled"}
_KNOWN_DELIVERY_JOB_STATUSES = {"prepared", "submitted", "in_progress", "completed", "expired", "cancelled", "failed", "held"}


@dataclass(frozen=True)
class SQLiteAccountingContractResult:
    """Deterministic validation output; never an independent attestation."""

    status: ContractStatus
    diagnostics: tuple[str, ...] = ()
    linkage: tuple[Mapping[str, str], ...] = ()
    canonical_bytes: bytes | None = None
    canonical_sha256: str | None = None
    independent_trust: Literal["NOT_SUPPLIED"] = "NOT_SUPPLIED"
    request_ticket: None = None
    send_authorization: Literal["NO_SEND_TICKET"] = "NO_SEND_TICKET"


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.lower()
        and all(char in "0123456789abcdef" for char in value)
    )


def _unique_diagnostics(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _rows(value: object, name: str, reasons: list[str]) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        reasons.append(f"view_missing_or_invalid:{name}")
        return []
    result: list[dict[str, object]] = []
    for ordinal, row in enumerate(value):
        if not isinstance(row, Mapping):
            reasons.append(f"row_invalid:{name}:{ordinal}")
            continue
        result.append(dict(row))
    return result


def _authority_diagnostics(authority: object) -> list[str]:
    if not isinstance(authority, Mapping):
        return ["source_authority_missing_or_invalid"]
    reasons = [f"source_authority_field_missing:{field}" for field in _AUTHORITY_FIELDS if field not in authority]
    for field in ("source_id", "source_kind", "source_version", "authority_id", "authority_version", "retention_id", "retention_version"):
        if field in authority and not _valid_id(authority.get(field)):
            reasons.append(f"source_authority_{field}_invalid")
    if not _valid_sha256(authority.get("content_sha256")):
        reasons.append("source_authority_content_sha256_invalid")
    if authority.get("retention_status") != "authorized":
        reasons.append("source_retention_not_authorized")
    return reasons


def _same_provenance(value: object, authority: Mapping[str, object]) -> bool:
    expected = {
        "source_id": authority.get("source_id"),
        "source_kind": authority.get("source_kind"),
        "content_sha256": authority.get("content_sha256"),
    }
    if isinstance(value, Mapping):
        return all(value.get(key) == expected[key] for key in expected)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(isinstance(item, Mapping) and all(item.get(key) == expected[key] for key in expected) for item in value)
    return False


def _coverage_diagnostics(coverage: object, authority: object, present: Mapping[str, list[dict[str, object]]]) -> list[str]:
    if not isinstance(coverage, Mapping):
        return ["coverage_missing_or_invalid"]
    if not isinstance(authority, Mapping):
        return ["coverage_source_binding_missing"]
    reasons: list[str] = []
    requested = coverage.get("requested_population")
    if not isinstance(requested, Sequence) or isinstance(requested, (str, bytes, bytearray)):
        reasons.append("requested_population_missing_or_invalid")
        requested_names: list[str] = []
    else:
        requested_names = [str(value) for value in requested]
    for name in _REQUIRED_VIEWS:
        if name not in requested_names:
            reasons.append(f"requested_population_missing:{name}")
    unknown = sorted(set(requested_names) - set(_REQUIRED_VIEWS))
    reasons.extend(f"requested_population_unknown:{name}" for name in unknown)
    if coverage.get("population_complete") is not True or coverage.get("project_wide") is not True:
        reasons.append("project_wide_population_not_asserted")
    flags = coverage.get("flags")
    if not isinstance(flags, Mapping):
        flags = coverage
    for name in _REQUIRED_VIEWS:
        if flags.get(name) is not True:
            reasons.append(f"coverage_not_complete:{name}")
        if name in requested_names and not present.get(name):
            reasons.append(f"coverage_empty_view_not_complete:{name}")
    if not _valid_id(coverage.get("scope")):
        reasons.append("coverage_scope_missing_or_invalid")
    if not _same_provenance(coverage.get("source_provenance"), authority):
        reasons.append("coverage_source_binding_missing")
    return reasons


def _check_columns(rows_by_view: Mapping[str, list[dict[str, object]]], reasons: list[str]) -> None:
    for view, columns in _REQUIRED_COLUMNS.items():
        rows = rows_by_view[view]
        if rows:
            for column in columns:
                if any(column not in row for row in rows):
                    reasons.append(f"missing_column:{view}.{column}")


def _index(rows: Sequence[Mapping[str, object]], view: str, reasons: list[str]) -> dict[str, dict[str, object]]:
    key = _VIEW_IDS[view]
    result: dict[str, dict[str, object]] = {}
    if isinstance(key, tuple):
        for row in rows:
            identity = tuple(str(row.get(part)) for part in key)
            if any(not _valid_id(row.get(part)) for part in key):
                reasons.append(f"missing_identifier:{view}:{identity}")
            if identity in result:
                reasons.append(f"duplicate_identity:{view}:{':'.join(identity)}")
            result[identity] = dict(row)
        return result
    for row in rows:
        identity = row.get(key)
        if not _valid_id(identity):
            reasons.append(f"missing_identifier:{view}:{identity}")
            continue
        text = str(identity)
        if text in result:
            reasons.append(f"duplicate_identity:{view}:{text}")
        result[text] = dict(row)
    return result


def _decimal(value: object, label: str, reasons: list[str]) -> Decimal | None:
    if not isinstance(value, str):
        reasons.append(f"amount_invalid:{label}")
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        reasons.append(f"amount_invalid:{label}")
        return None
    if not amount.is_finite():
        reasons.append(f"amount_invalid:{label}")
        return None
    return amount


def _json_object(value: object, label: str, reasons: list[str]) -> Mapping[str, object] | None:
    if not isinstance(value, str):
        reasons.append(f"usage_json_invalid:{label}")
        return None
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        reasons.append(f"usage_json_invalid:{label}")
        return None
    if not isinstance(loaded, Mapping):
        reasons.append(f"usage_json_invalid:{label}")
        return None
    return loaded


def _validate_links(rows: Mapping[str, list[dict[str, object]]], reasons: list[str]) -> tuple[Mapping[str, str], ...]:
    jobs = _index(rows["delivery_jobs"], "delivery_jobs", reasons)
    tasks = _index(rows["tasks"], "tasks", reasons)
    attempts = _index(rows["task_attempts"], "task_attempts", reasons)
    costs = _index(rows["cost_entries"], "cost_entries", reasons)
    physical = _index(rows["physical_attempts"], "physical_attempts", reasons)
    members = _index(rows["physical_attempt_members"], "physical_attempt_members", reasons)
    items = _index(rows["provider_request_items"], "provider_request_items", reasons)
    provider_attempt_physical_ids: set[str] = set()
    for row in rows["provider_request_attempts"]:
        physical_id = row.get("physical_attempt_id")
        if _valid_id(physical_id):
            physical_text = str(physical_id)
            if physical_text in provider_attempt_physical_ids:
                reasons.append(f"duplicate_provider_request_attempts_physical_attempt_id:{physical_text}")
            provider_attempt_physical_ids.add(physical_text)
    provider_attempts = _index(rows["provider_request_attempts"], "provider_request_attempts", reasons)
    receipt_physical_ids: set[str] = set()
    for row in rows["provider_receipts"]:
        physical_id = row.get("physical_attempt_id")
        if _valid_id(physical_id):
            physical_text = str(physical_id)
            if physical_text in receipt_physical_ids:
                reasons.append(f"duplicate_provider_receipts_physical_attempt_id:{physical_text}")
            receipt_physical_ids.add(physical_text)
    receipts = _index(rows["provider_receipts"], "provider_receipts", reasons)

    item_ids_by_physical: dict[str, list[str]] = {}
    for item_id, row in items.items():
        physical_id = row.get("physical_attempt_id")
        if _valid_id(physical_id):
            item_ids_by_physical.setdefault(str(physical_id), []).append(item_id)
    provider_attempt_ids_by_physical: dict[str, list[str]] = {}
    for delivery_id, row in provider_attempts.items():
        physical_id = row.get("physical_attempt_id")
        if _valid_id(physical_id):
            provider_attempt_ids_by_physical.setdefault(str(physical_id), []).append(delivery_id)
    receipt_ids_by_physical: dict[str, list[str]] = {}
    for receipt_id, row in receipts.items():
        physical_id = row.get("physical_attempt_id")
        if _valid_id(physical_id):
            receipt_ids_by_physical.setdefault(str(physical_id), []).append(receipt_id)

    physical_by_request: dict[str, dict[str, object]] = {}
    for job_id, row in jobs.items():
        for field in ("run_id", "provider_id", "model_route"):
            if not _valid_id(row.get(field)):
                reasons.append(f"missing_relationship:delivery_jobs.{field}:{job_id}")
        if row.get("status") not in _KNOWN_DELIVERY_JOB_STATUSES:
            reasons.append(f"delivery_job_unresolved:{job_id}")
    for physical_id, row in physical.items():
        request_id = row.get("provider_request_id")
        if not _valid_id(request_id):
            reasons.append(f"missing_relationship:physical_attempts.provider_request_id:{physical_id}")
        elif str(request_id) in physical_by_request:
            reasons.append(f"duplicate_physical_provider_request_id:{request_id}")
        else:
            physical_by_request[str(request_id)] = row
        if row.get("status") not in _TERMINAL_PHYSICAL:
            reasons.append(f"physical_attempt_unresolved:{physical_id}")

    member_ids: dict[str, set[str]] = {}
    for (physical_id, task_id), row in members.items():
        del row
        member_ids.setdefault(physical_id, set()).add(task_id)
        if physical_id not in physical:
            reasons.append(f"orphaned_physical_attempt_member:{physical_id}:{task_id}")
        if task_id not in tasks:
            reasons.append(f"orphaned_physical_attempt_member_task:{task_id}")

    provider_by_physical: dict[str, dict[str, object]] = {}
    for delivery_id, row in provider_attempts.items():
        physical_id = row.get("physical_attempt_id")
        item_id = row.get("provider_request_item_id")
        if not _valid_id(physical_id):
            reasons.append(f"missing_relationship:provider_request_attempts.physical_attempt_id:{delivery_id}")
        elif str(physical_id) in provider_by_physical:
            reasons.append(f"duplicate_provider_request_attempts_physical_attempt_id:{physical_id}")
        else:
            provider_by_physical[str(physical_id)] = row
        if physical_id not in physical:
            reasons.append(f"orphaned_provider_request_attempt:{delivery_id}")
        if item_id not in items:
            reasons.append(f"orphaned_provider_request_attempt_item:{delivery_id}")
        if row.get("status") not in _TERMINAL_PROVIDER:
            reasons.append(f"provider_attempt_unresolved:{delivery_id}")

    for item_id, row in items.items():
        task_id = row.get("model_task_id")
        physical_id = row.get("physical_attempt_id")
        receipt_id = row.get("provider_receipt_id")
        if task_id not in tasks:
            reasons.append(f"orphaned_provider_request_item_task:{item_id}")
        if physical_id not in physical:
            reasons.append(f"orphaned_provider_request_item_physical:{item_id}")
        if not _valid_id(receipt_id):
            reasons.append(f"missing_relationship:provider_request_items.provider_receipt_id:{item_id}")
        elif receipt_id not in receipts:
            reasons.append(f"orphaned_provider_request_item_receipt:{item_id}")
        if physical_id in physical:
            prow = physical[physical_id]
            if row.get("run_id") != prow.get("run_id") or row.get("provider_request_id") != prow.get("provider_request_id"):
                reasons.append(f"contradictory_item_physical_identity:{item_id}")
            if item_id not in {str(provider.get("provider_request_item_id")) for provider in provider_attempts.values()}:
                reasons.append(f"missing_relationship:provider_request_items.provider_request_attempts:{item_id}")
            if task_id in tasks and tasks[task_id].get("run_id") != row.get("run_id"):
                reasons.append(f"contradictory_item_task_identity:{item_id}")
            if task_id not in member_ids.get(str(physical_id), set()):
                reasons.append(f"missing_relationship:provider_request_items.physical_attempt_members:{item_id}")
        job_id = row.get("delivery_job_id")
        if not _valid_id(job_id) or job_id not in jobs:
            reasons.append(f"orphaned_provider_request_item_delivery_job:{item_id}")
        else:
            job = jobs[str(job_id)]
            if row.get("run_id") != job.get("run_id"):
                reasons.append(f"contradictory_item_delivery_job_run_identity:{item_id}")
            if row.get("provider_id") != job.get("provider_id") or row.get("model_route") != job.get("model_route"):
                reasons.append(f"contradictory_item_delivery_job_route_identity:{item_id}")

    for receipt_id, row in receipts.items():
        physical_id = row.get("physical_attempt_id")
        if physical_id not in physical:
            reasons.append(f"orphaned_provider_receipt:{receipt_id}")
        elif row.get("provider_request_id") != physical[physical_id].get("provider_request_id"):
            reasons.append(f"contradictory_receipt_physical_identity:{receipt_id}")
        if not any(item.get("provider_receipt_id") == receipt_id for item in items.values()):
            reasons.append(f"orphaned_provider_receipt_item_link:{receipt_id}")

    for delivery_id, row in provider_attempts.items():
        physical_id = row.get("physical_attempt_id")
        item_id = row.get("provider_request_item_id")
        receipt_id = row.get("provider_receipt_id")
        if physical_id in physical and row.get("provider_request_id") != physical[physical_id].get("provider_request_id"):
            reasons.append(f"contradictory_provider_attempt_physical_identity:{delivery_id}")
        job_id = row.get("delivery_job_id")
        if not _valid_id(job_id) or job_id not in jobs:
            reasons.append(f"orphaned_provider_request_attempt_delivery_job:{delivery_id}")
        if item_id in items:
            item = items[item_id]
            if item.get("delivery_job_id") != job_id:
                reasons.append(f"contradictory_provider_attempt_delivery_job_identity:{delivery_id}")
            if item.get("physical_attempt_id") != physical_id or item.get("provider_request_id") != row.get("provider_request_id"):
                reasons.append(f"contradictory_provider_attempt_item_identity:{delivery_id}")
            if receipt_id != item.get("provider_receipt_id"):
                reasons.append(f"contradictory_provider_attempt_receipt_identity:{delivery_id}")
        if receipt_id not in receipts:
            reasons.append(f"orphaned_provider_request_attempt_receipt:{delivery_id}")

    for physical_id, row in physical.items():
        if row.get("status") not in _TERMINAL_PHYSICAL:
            continue
        item_ids = item_ids_by_physical.get(physical_id, [])
        if not item_ids:
            reasons.append(f"missing_reverse_link:physical_attempts.provider_request_item:{physical_id}")
        elif len(item_ids) != 1:
            reasons.append(f"ambiguous_reverse_link:physical_attempts.provider_request_item:{physical_id}")
        provider_ids = provider_attempt_ids_by_physical.get(physical_id, [])
        if not provider_ids:
            reasons.append(f"missing_reverse_link:physical_attempts.provider_request_attempt:{physical_id}")
        elif len(provider_ids) != 1:
            reasons.append(f"ambiguous_reverse_link:physical_attempts.provider_request_attempt:{physical_id}")
        receipt_ids = receipt_ids_by_physical.get(physical_id, [])
        if not receipt_ids:
            reasons.append(f"missing_reverse_link:physical_attempts.provider_receipt:{physical_id}")
        elif len(receipt_ids) != 1:
            reasons.append(f"ambiguous_reverse_link:physical_attempts.provider_receipt:{physical_id}")

    linkage: list[Mapping[str, str]] = []
    for entry_id, cost in costs.items():
        if cost.get("entry_type") != "actual":
            continue
        task_run_id = cost.get("task_run_id")
        if not _valid_id(task_run_id) or task_run_id not in attempts:
            reasons.append(f"missing_relationship:cost_entries.task_attempts:{entry_id}")
            continue
        attempt = attempts[task_run_id]
        task_id = attempt.get("model_task_id")
        if task_id not in tasks:
            reasons.append(f"orphaned_task_attempt_task:{task_run_id}")
            continue
        task = tasks[task_id]
        if cost.get("run_id") != task.get("run_id"):
            reasons.append(f"contradictory_cost_task_identity:{entry_id}")
        request_id = attempt.get("provider_request_id")
        physical_row = physical_by_request.get(str(request_id)) if _valid_id(request_id) else None
        if physical_row is None:
            reasons.append(f"missing_relationship:task_attempts.physical_attempts:{task_run_id}")
            continue
        physical_id = str(physical_row["physical_attempt_id"])
        if task_id not in member_ids.get(physical_id, set()):
            reasons.append(f"contradictory_task_physical_identity:{task_run_id}")
        usage = _json_object(cost.get("usage_json"), entry_id, reasons)
        if usage is None:
            continue
        item_id = usage.get("provider_request_item_id")
        receipt_id = usage.get("provider_receipt_id")
        if not _valid_id(item_id) or item_id not in items:
            reasons.append(f"missing_relationship:cost_entries.provider_request_item_id:{entry_id}")
            continue
        item = items[item_id]
        if item.get("physical_attempt_id") != physical_id or item.get("model_task_id") != task_id:
            reasons.append(f"contradictory_cost_request_item_identity:{entry_id}")
        if not _valid_id(receipt_id) or receipt_id not in receipts:
            reasons.append(f"missing_relationship:cost_entries.provider_receipt_id:{entry_id}")
        elif item.get("provider_receipt_id") != receipt_id:
            reasons.append(f"contradictory_cost_receipt_identity:{entry_id}")
        linkage.append({
            "entry_key": str(entry_id),
            "task_run_id": str(task_run_id),
            "model_task_id": str(task_id),
            "provider_request_item_id": str(item_id),
            "provider_receipt_id": str(receipt_id),
            "physical_attempt_id": physical_id,
            "delivery_job_id": str(item.get("delivery_job_id")),
            "provider_id": str(item.get("provider_id")),
            "model_route": str(item.get("model_route")),
            "pricing_snapshot_id": str(cost.get("pricing_snapshot_id")),
            "fx_snapshot_id": str(cost.get("fx_snapshot_id")),
        })

    return tuple(sorted(linkage, key=lambda row: (row["entry_key"], row["physical_attempt_id"])))


def _validate_accounting(rows: Mapping[str, list[dict[str, object]]], reasons: list[str]) -> None:
    attempts = {str(row.get("task_run_id")): row for row in rows["task_attempts"] if _valid_id(row.get("task_run_id"))}
    for entry_id, row in ((str(item.get("entry_key")), item) for item in rows["cost_entries"]):
        accounting = _decimal(row.get("accounting_amount"), f"accounting_amount:{entry_id}", reasons)
        aud = _decimal(row.get("aud_amount"), f"aud_amount:{entry_id}", reasons)
        if row.get("accounting_currency") != "AUD":
            reasons.append(f"accounting_currency_not_aud:{entry_id}")
        if accounting is not None and aud is not None and accounting != aud:
            reasons.append(f"accounting_aud_amount_mismatch:{entry_id}")
        if row.get("entry_type") != "actual":
            continue
        if not _valid_id(row.get("pricing_snapshot_id")) or not _valid_id(row.get("fx_snapshot_id")):
            reasons.append(f"unpriced_cost_or_fx:{entry_id}")
        attempt = attempts.get(str(row.get("task_run_id")))
        if attempt is None:
            continue
        if row.get("pricing_snapshot_id") != attempt.get("pricing_snapshot_id") or row.get("fx_snapshot_id") != attempt.get("fx_snapshot_id"):
            reasons.append(f"pricing_fx_identity_conflict:{entry_id}")
        provider_currency = row.get("provider_currency")
        if not _valid_id(provider_currency):
            reasons.append(f"provider_currency_missing:{entry_id}")
        elif not isinstance(provider_currency, str) or len(provider_currency) != 3 or provider_currency != provider_currency.upper():
            reasons.append(f"provider_currency_invalid:{entry_id}")
        provider_amount = row.get("provider_amount")
        if provider_amount is None:
            reasons.append(f"provider_amount_missing:{entry_id}")
            provider = None
        else:
            provider = _decimal(provider_amount, f"provider_amount:{entry_id}", reasons)
        if provider_currency == "AUD" and provider is not None and accounting is not None:
            if provider is not None and provider != accounting:
                reasons.append(f"provider_accounting_amount_mismatch:{entry_id}")


def validate_sqlite_accounting_contract(
    views: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    source_authority: Mapping[str, object] | None,
    coverage: Mapping[str, object] | None,
) -> SQLiteAccountingContractResult:
    """Validate caller-supplied migration-29 mapping views without I/O."""

    reasons = _authority_diagnostics(source_authority)
    if not isinstance(views, Mapping):
        reasons.append("views_missing_or_invalid")
        return SQLiteAccountingContractResult(status="NOT_ATTESTABLE", diagnostics=_unique_diagnostics(reasons))
    rows = {name: _rows(views.get(name), name, reasons) for name in _REQUIRED_VIEWS}
    _check_columns(rows, reasons)
    if isinstance(source_authority, Mapping):
        reasons.extend(_coverage_diagnostics(coverage, source_authority, rows))
    else:
        reasons.append("coverage_source_binding_missing")
    _validate_accounting(rows, reasons)
    linkage = _validate_links(rows, reasons)
    if reasons:
        return SQLiteAccountingContractResult(status="NOT_ATTESTABLE", diagnostics=_unique_diagnostics(reasons))

    authority = dict(source_authority or {})
    coverage_map = dict(coverage or {})
    payload = {
        "schema_id": CONTRACT_SCHEMA,
        "migration_version": CONTRACT_MIGRATION_VERSION,
        "source_authority": authority,
        "coverage": {
            "scope": coverage_map["scope"],
            "requested_population": sorted(str(value) for value in coverage_map["requested_population"]),
            "flags": {name: True for name in _REQUIRED_VIEWS},
        },
        "linkage": list(linkage),
    }
    encoded = canonical_json_bytes(payload)
    return SQLiteAccountingContractResult(
        status="CANDIDATE_NOT_ATTESTED",
        linkage=linkage,
        canonical_bytes=encoded,
        canonical_sha256=hashlib.sha256(encoded).hexdigest(),
    )


__all__ = [
    "CONTRACT_MIGRATION_VERSION",
    "CONTRACT_SCHEMA",
    "SQLiteAccountingContractResult",
    "validate_sqlite_accounting_contract",
]
