"""Pure, provider-free diagnostics for caller-supplied Phase 5 evidence.

This module is deliberately a projection seam, not a runner.  It accepts an
existing run result and an existing durable-ledger snapshot, derives a small
allowlisted diagnostic document, and never opens a database, schedules work,
contacts a provider, or persists state.

The public representation is ``charitygraph.phase5.run-diagnostics/v1``.  The
SHA-256 returned by :func:`project_run_diagnostics` is the hash of the exact
canonical JSON bytes returned alongside it.  The document contains identity
and provenance references, but never raw prompts, source text, credentials,
or provider response bodies.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


SCHEMA_ID = "charitygraph.phase5.run-diagnostics"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"
NOT_OBSERVED = "NOT_OBSERVED"


class RunDiagnosticsError(ValueError):
    """Raised when diagnostic evidence is malformed, incomplete, or conflicting."""


@dataclass(frozen=True)
class DiagnosticProjection:
    """The immutable diagnostic document and its canonical content identity."""

    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        """Return a caller-owned copy of the projection envelope."""

        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "prompt",
    "secret",
    "source_text",
    "raw_prompt",
    "raw_response",
    "response_body",
)


def _reject_sensitive_keys(value: Any, *, path: str = "input") -> None:
    """Guard the diagnostic boundary against accidental material disclosure."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
                raise RunDiagnosticsError(f"sensitive field is not admissible at {path}")
            _reject_sensitive_keys(child, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_sensitive_keys(child, path=f"{path}[{index}]")
    elif isinstance(value, float):
        raise RunDiagnosticsError(f"binary floating-point value is not admissible at {path}")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunDiagnosticsError(f"{field} must be an object")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RunDiagnosticsError(f"{field} is required")
    return value


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RunDiagnosticsError(f"{field} must be an integer >= {minimum}")
    return value


def _canonical_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise RunDiagnosticsError(f"{field} must use an exact decimal value")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise RunDiagnosticsError(f"{field} must be a decimal value") from None
    if not amount.is_finite() or amount < 0:
        raise RunDiagnosticsError(f"{field} must be a finite non-negative decimal")
    return amount


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _amount(row: Mapping[str, Any], field: str) -> tuple[Decimal, str]:
    raw = row.get(field)
    currency = row.get("currency", row.get("accounting_currency"))
    if raw is None and field == "amount":
        raw = row.get("accounting_amount", row.get("aud_amount"))
    if isinstance(raw, Mapping):
        currency = raw.get("currency", currency)
        raw = raw.get("amount")
    if raw is None:
        raise RunDiagnosticsError(f"{field} is required for accounting evidence")
    if currency is None and field in {"aud_amount", "accounting_amount"}:
        currency = "AUD"
    if not isinstance(currency, str) or len(currency) != 3 or currency != currency.upper() or not currency.isalpha():
        raise RunDiagnosticsError(f"{field} currency is invalid")
    return _canonical_decimal(raw, field), currency


def _rows(value: Any, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise RunDiagnosticsError(f"{field} must be a list")
    rows = []
    for index, row in enumerate(value):
        rows.append(_mapping(row, f"{field}[{index}]") )
    return rows


def _first(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RunDiagnosticsError(f"{field} must be boolean")
    return value


def _identity(row: Mapping[str, Any], index: int) -> dict[str, str | None]:
    item_id = _first(row, "item_id", "request_item_id", "provider_request_item_id", "logical_task_id", "task_id")
    subject_id = _first(row, "subject_id", "durable_subject_id")
    scope_id = _first(row, "scope_id", "durable_scope_id")
    return {
        "item_id": _text(item_id, f"results[{index}].item_id"),
        "subject_id": _text(subject_id, f"results[{index}].subject_id"),
        "scope_id": _text(scope_id, f"results[{index}].scope_id"),
    }


def _status_summary(results: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], Counter[str], int, int]:
    allowed: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    provider_posts = 0
    stop_items = 0
    seen: set[str] = set()
    for index, row in enumerate(results):
        identity = _identity(row, index)
        item_id = identity["item_id"]
        if item_id in seen:
            raise RunDiagnosticsError("run results contain duplicate item identity")
        seen.add(item_id)
        status = _text(row.get("status"), f"results[{index}].status")
        posts = _integer(_first(row, "provider_posts", "new_provider_posts"), f"results[{index}].provider_posts")
        stop = row.get("stop_campaign", row.get("stop", False))
        stop = _bool(stop, f"results[{index}].stop_campaign")
        item = {**identity, "status": status, "provider_posts": posts, "stop_campaign": stop}
        counts[status] += 1
        provider_posts += posts
        stop_items += int(stop)
        allowed.append(item)
    allowed.sort(key=lambda row: (row["item_id"], row["subject_id"], row["scope_id"]))
    return allowed, counts, provider_posts, stop_items


def _compare_optional_integer(run: Mapping[str, Any], names: tuple[str, ...], derived: int, field: str) -> int:
    supplied = _first(run, *names)
    if supplied is None:
        return derived
    supplied_int = _integer(supplied, field)
    if supplied_int != derived:
        raise RunDiagnosticsError(f"{field} conflicts with item evidence")
    return supplied_int


def _accounting(ledger: Mapping[str, Any]) -> dict[str, Any]:
    reservations = _rows(ledger.get("reservations"), "ledger.reservations")
    entries = _rows(ledger.get("cost_entries"), "ledger.cost_entries")
    attempts = _rows(ledger.get("attempts"), "ledger.attempts")
    receipts = _rows(ledger.get("receipts"), "ledger.receipts")
    tasks = _rows(ledger.get("tasks"), "ledger.tasks")

    reservation_totals: dict[str, tuple[Decimal, str]] = {}
    reservation_status: dict[str, str] = {}
    for index, row in enumerate(reservations):
        reservation_id = _text(_first(row, "reservation_id", "id"), f"ledger.reservations[{index}].reservation_id")
        if reservation_id in reservation_totals:
            raise RunDiagnosticsError("duplicate reservation identity")
        amount, currency = _amount(row, "reserved_aud" if "reserved_aud" in row else "amount")
        reservation_totals[reservation_id] = (amount, currency)
        reservation_status[reservation_id] = str(row.get("status", "unknown"))

    entry_keys: set[str] = set()
    actual: defaultdict[str, Decimal] = defaultdict(Decimal)
    releases: defaultdict[str, Decimal] = defaultdict(Decimal)
    other: defaultdict[str, Decimal] = defaultdict(Decimal)
    currencies: dict[str, str] = {}
    for index, row in enumerate(entries):
        key = _text(_first(row, "entry_key", "id"), f"ledger.cost_entries[{index}].entry_key")
        if key in entry_keys:
            raise RunDiagnosticsError("duplicate cost-entry identity would double count accounting")
        entry_keys.add(key)
        reservation_id = _text(row.get("reservation_id"), f"ledger.cost_entries[{index}].reservation_id")
        if reservation_id not in reservation_totals:
            raise RunDiagnosticsError("cost entry refers to an unknown reservation")
        amount, currency = _amount(row, "accounting_amount" if "accounting_amount" in row else ("aud_amount" if "aud_amount" in row else "amount"))
        prior_currency = currencies.setdefault(reservation_id, currency)
        if prior_currency != currency or reservation_totals[reservation_id][1] != currency:
            raise RunDiagnosticsError("reservation accounting currencies conflict")
        entry_type = _text(row.get("entry_type"), f"ledger.cost_entries[{index}].entry_type")
        if entry_type in {"actual", "provider_actual"}:
            actual[reservation_id] += amount
        elif entry_type in {"reservation_release", "release"}:
            releases[reservation_id] += amount
        elif entry_type in {"credit", "adjustment_credit", "debit", "adjustment_debit"}:
            other[reservation_id] += amount if "credit" in entry_type else -amount
        else:
            raise RunDiagnosticsError("unsupported accounting entry type")

    accounting_currencies = {currency for _, currency in reservation_totals.values()}
    if len(accounting_currencies) > 1:
        raise RunDiagnosticsError("multiple accounting currencies require a currency-separated projection")

    positions: list[dict[str, Any]] = []
    discrepancy = Decimal(0)
    for reservation_id in sorted(reservation_totals):
        reserved, currency = reservation_totals[reservation_id]
        actual_amount = actual[reservation_id]
        release_amount = releases[reservation_id]
        balance = reserved - actual_amount - release_amount
        discrepancy += abs(balance)
        if actual_amount + release_amount > reserved:
            raise RunDiagnosticsError("accounting actuals and releases exceed reservation")
        positions.append({
            "reservation_id": reservation_id,
            "status": reservation_status[reservation_id],
            "currency": currency,
            "reserved": _decimal_text(reserved),
            "actual": _decimal_text(actual_amount),
            "released": _decimal_text(release_amount),
            "unreconciled": _decimal_text(balance),
            "reconciled": balance == 0,
        })
    if any(position["reconciled"] is False for position in positions):
        reconciliation_state = "INCOMPLETE_OR_DISCREPANT"
    else:
        reconciliation_state = "RECONCILED" if positions else NOT_OBSERVED
    return {
        "record_counts": {
            "tasks": len(tasks),
            "attempts": len(attempts),
            "receipts": len(receipts),
            "reservations": len(reservations),
            "cost_entries": len(entries),
        },
        "provider_receipts": len(receipts),
        "attempts": len(attempts),
        "reservations": len(reservations),
        "cost_entries": len(entries),
        "actuals": _decimal_text(sum(actual.values(), Decimal(0))),
        "releases": _decimal_text(sum(releases.values(), Decimal(0))),
        "adjustments_net": _decimal_text(sum(other.values(), Decimal(0))),
        "reconciliation": {
            "state": reconciliation_state,
            "discrepancy": _decimal_text(discrepancy),
            "positions": positions,
        },
    }


def _grouped(items: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item[field])].append(item)
    output = []
    for key in sorted(grouped):
        rows = grouped[key]
        counts = Counter(row["status"] for row in rows)
        output.append({"id": key, "item_count": len(rows), "status_counts": dict(sorted(counts.items()))})
    return output


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def project_run_diagnostics(run_record: Mapping[str, Any], ledger_snapshot: Mapping[str, Any]) -> DiagnosticProjection:
    """Project existing run and ledger records into a stable diagnostic artifact.

    Required run fields are ``run_id``, ``provenance`` (with
    ``run_record_ref`` and ``ledger_snapshot_ref``), and ``results``.  Each
    result requires ``item_id``, ``subject_id``, ``scope_id``, ``status`` and
    ``provider_posts``.  Required ledger lists are ``tasks``, ``attempts``,
    ``receipts``, ``reservations`` and ``cost_entries``; they may be empty.
    Monetary fields accept exact decimal strings/integers/Decimals only.
    """

    run = _mapping(run_record, "run_record")
    ledger = _mapping(ledger_snapshot, "ledger_snapshot")
    _reject_sensitive_keys(run)
    _reject_sensitive_keys(ledger)
    run_id = _text(run.get("run_id"), "run_record.run_id")
    provenance = _mapping(run.get("provenance"), "run_record.provenance")
    run_ref = _text(provenance.get("run_record_ref"), "run_record.provenance.run_record_ref")
    ledger_ref = _text(provenance.get("ledger_snapshot_ref"), "run_record.provenance.ledger_snapshot_ref")
    results = _rows(run.get("results"), "run_record.results")
    required_ledger_keys = ("tasks", "attempts", "receipts", "reservations", "cost_entries")
    if any(key not in ledger for key in required_ledger_keys):
        raise RunDiagnosticsError("ledger snapshot is missing a required durable-record list")

    items, counts, derived_posts, stop_items = _status_summary(results)
    provider_posts = _compare_optional_integer(run, ("provider_posts", "new_provider_posts"), derived_posts, "run_record.provider_posts")
    planned_count = _first(run, "planned_item_count")
    if planned_count is not None:
        planned_count = _integer(planned_count, "run_record.planned_item_count")
        if planned_count < len(items):
            raise RunDiagnosticsError("planned item count is smaller than observed results")
    explicit_unattempted = _first(run, "unattempted", "unattempted_count")
    if explicit_unattempted is not None:
        unattempted = _integer(explicit_unattempted, "run_record.unattempted")
        if planned_count is not None and unattempted != planned_count - len(items):
            raise RunDiagnosticsError("unattempted count conflicts with planned/results evidence")
    elif planned_count is not None:
        unattempted = planned_count - len(items)
    else:
        unattempted = NOT_OBSERVED

    configured = _first(run, "configured_concurrency", "max_concurrency")
    observed = _first(run, "observed_concurrency", "max_observed_concurrency")
    if configured is None:
        configured_value: int | str = NOT_OBSERVED
    else:
        configured_value = _integer(configured, "run_record.configured_concurrency", minimum=1)
    if observed is None:
        observed_value: int | str = NOT_OBSERVED
    else:
        observed_value = _integer(observed, "run_record.observed_concurrency")
    if isinstance(configured_value, int) and isinstance(observed_value, int) and observed_value > configured_value:
        raise RunDiagnosticsError("observed concurrency exceeds configured cap")

    stop = run.get("stop")
    if stop is None:
        stop = {}
    stop = _mapping(stop, "run_record.stop")
    campaign_stopped = _first(stop, "campaign_stopped", "stop_campaign")
    if campaign_stopped is None:
        campaign_stopped = run.get("stop_campaign", False)
    campaign_stopped = _bool(campaign_stopped, "run_record.stop_campaign")
    classification = _first(stop, "classification", "reason")
    if classification is None:
        classification = NOT_OBSERVED if campaign_stopped else "none"
    classification = _text(classification, "run_record.stop.classification")
    if classification not in {"none", "item_failure", "ambiguous", "systemic", "requested", "unknown", NOT_OBSERVED}:
        raise RunDiagnosticsError("run stop classification is not recognised")
    if not campaign_stopped and classification not in {"none", NOT_OBSERVED}:
        raise RunDiagnosticsError("non-none stop classification without a stopped run")
    ambiguous_count = sum(1 for item in items if item["status"] == "ambiguous")
    terminal_failure_count = sum(1 for item in items if item["status"] in {"failed_terminal", "completed_parse_failed", "completed_accounting_failed"})
    accounting = _accounting(ledger)

    document = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "diagnostic_identity": {"run_id": run_id, "projection": "phase5-run-diagnostics"},
        "provenance": {
            "evidence_kind": "caller_supplied_existing_run_and_durable_ledger_records",
            "run_record_ref": run_ref,
            "ledger_snapshot_ref": ledger_ref,
        },
        "summary": {
            "status_counts": dict(sorted(counts.items())),
            "items_observed": len(items),
            "unattempted": unattempted,
            "provider_posts": provider_posts,
            "new_provider_posts": provider_posts,
            "restart_no_resend": (
                _bool(run["restart_no_resend"], "run_record.restart_no_resend")
                if "restart_no_resend" in run
                else (True if any(item["status"] == "replayed_terminal" for item in items) else NOT_OBSERVED)
            ),
            "concurrency": {
                "configured": configured_value,
                "observed_max": observed_value,
                "cap_respected": (observed_value <= configured_value if isinstance(configured_value, int) and isinstance(observed_value, int) else NOT_OBSERVED),
            },
            "stop": {
                "campaign_stopped": campaign_stopped,
                "classification": classification,
                "stop_item_count": stop_items,
                "ambiguous_crossings": ambiguous_count,
                "terminal_item_failures": terminal_failure_count,
            },
        },
        "items": items,
        "scopes": _grouped(items, "scope_id"),
        "subjects": _grouped(items, "subject_id"),
        "ledger": accounting,
        "limitations": [
            "This projection observes caller-supplied records only; it does not prove provider-side exactly-once effects.",
            "Live scheduling, multiworker SLOs, alerts, rights acceptance, source authorization and production health are not observed.",
            "Provider request bodies, prompts, source text, credentials and response bodies are intentionally excluded.",
        ],
    }
    canonical_json = _canonical_bytes(document)
    return DiagnosticProjection(document=document, canonical_json=canonical_json, sha256=hashlib.sha256(canonical_json).hexdigest())


def canonical_diagnostics_json(projection: DiagnosticProjection | Mapping[str, Any]) -> bytes:
    """Return canonical bytes for a projection or document."""

    document = projection.document if isinstance(projection, DiagnosticProjection) else projection
    return _canonical_bytes(_mapping(document, "projection"))


def diagnostics_sha256(projection: DiagnosticProjection | Mapping[str, Any]) -> str:
    """Hash the canonical JSON representation of a projection or document."""

    return hashlib.sha256(canonical_diagnostics_json(projection)).hexdigest()


build_run_diagnostics = project_run_diagnostics


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCHEMA",
    "NOT_OBSERVED",
    "RunDiagnosticsError",
    "DiagnosticProjection",
    "project_run_diagnostics",
    "build_run_diagnostics",
    "canonical_diagnostics_json",
    "diagnostics_sha256",
]
