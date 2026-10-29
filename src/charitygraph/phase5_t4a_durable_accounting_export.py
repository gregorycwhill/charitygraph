"""Read-only, source-bound accounting export over durable runtime records.

This is an adapter boundary, not a ledger and not a catalogue query.  The
caller supplies an already-open read-only view of the durable runtime rows and
binds that view to its source authority, retention identity and coverage
authority.  The adapter never opens a database, reads a file, contacts a
provider, mutates a record, or treats its candidate hash as an attestation.

Candidate bytes deliberately reuse the T4A6 canonical candidate format.  The
T4A5/T4A7 verifier remains a separate step requiring an independently supplied
trusted pin.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .contracts.canonical import canonical_json_bytes
from .phase5_t4a_project_budget_snapshot import (
    DEFAULT_MAX_EVIDENCE_AGE,
    ProjectBudgetSnapshotCandidate,
    build_project_budget_snapshot,
)


DURABLE_ACCOUNTING_EXPORT_SCHEMA = "charitygraph.durable-accounting-source-export/1"
SourceExportStatus = Literal["CANDIDATE_NOT_ATTESTED", "NOT_ATTESTABLE", "BLOCKED"]

_SOURCE_AUTHORITY_FIELDS = {
    "source_id",
    "source_kind",
    "source_version",
    "content_sha256",
    "authority_id",
    "authority_version",
    "retention_id",
    "retention_version",
    "retention_status",
}
_RECORD_CLASSES = (
    ("cohorts", "cohort_id"),
    ("runs", "run_id"),
    ("logical_tasks", "model_task_id"),
    ("task_attempts", "task_run_id"),
    ("reservations", "reservation_id"),
    ("cost_entries", "entry_key"),
    ("physical_attempts", "physical_attempt_id"),
    ("provider_request_attempts", "delivery_attempt_id"),
)
_COVERAGE_CLASSES = (
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
_BLOCKING_REASONS = (
    "unresolved_physical_attempts_present",
    "unpriced_physical_attempts_present",
    "physical_attempt_status_unknown:",
    "physical_attempt_cross_cohort_mismatch:",
    "logical_task_cross_cohort_mismatch:",
    "retry_identity_mismatch:",
    "provider_attempt_physical_missing:",
)


@dataclass(frozen=True)
class ReadOnlyDurableAccountingView:
    """Caller-bound, already-open read-only views of durable records.

    ``accounting_evidence`` and ``coverage_manifest`` use the exact T4A6
    shapes.  Mapping inputs are treated as immutable by this function; bytes
    must already be canonical UTF-8 JSON.  The caller, not this adapter, owns
    the authority and retention assertions in ``source_authority``.
    """

    source_authority: Mapping[str, object]
    accounting_evidence: Mapping[str, object] | bytes
    coverage_manifest: Mapping[str, object] | bytes


@dataclass(frozen=True)
class DurableAccountingSourceExport:
    """Candidate plus explicit source/coverage diagnostics; never send-ready."""

    status: SourceExportStatus
    candidate: ProjectBudgetSnapshotCandidate | None = None
    candidate_bytes: bytes | None = None
    candidate_sha256: str | None = None
    source_authority: Mapping[str, object] | None = None
    source_inventory: tuple[Mapping[str, object], ...] = ()
    coverage_diagnostics: tuple[Mapping[str, object], ...] = ()
    pricing_fx_identity_ids: tuple[tuple[str, str], ...] = ()
    reasons: tuple[str, ...] = ()
    independent_trust: Literal["NOT_SUPPLIED"] = "NOT_SUPPLIED"
    request_ticket: None = None
    send_authorization: Literal["not_authorized_for_send"] = "not_authorized_for_send"


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(
        char in "0123456789abcdef" for char in value
    )


def _unique_reasons(reasons: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(reasons)))


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _load_object(value: Mapping[str, object] | bytes | None, label: str) -> tuple[dict[str, object] | None, list[str]]:
    if isinstance(value, bytes):
        try:
            loaded = json.loads(value.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
            if not isinstance(loaded, Mapping) or value != canonical_json_bytes(loaded):
                raise ValueError("non_canonical")
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return None, [f"{label}_invalid:{str(exc) or 'invalid'}"]
        return dict(loaded), []
    if not isinstance(value, Mapping):
        return None, [f"{label}_missing_or_invalid"]
    try:
        encoded = canonical_json_bytes(value)
        loaded = json.loads(encoded.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return None, [f"{label}_invalid:{str(exc) or 'invalid'}"]
    return dict(loaded), []


def _has_source_provenance(value: object, authority: Mapping[str, object]) -> bool:
    if not isinstance(value, list):
        return False
    expected = {
        "source_id": authority.get("source_id"),
        "source_kind": authority.get("source_kind"),
        "content_sha256": authority.get("content_sha256"),
    }
    return any(isinstance(item, Mapping) and all(item.get(key) == expected[key] for key in expected) for item in value)


def _source_diagnostics(
    authority: Mapping[str, object] | None,
    evidence: Mapping[str, object] | None,
    manifest: Mapping[str, object] | None,
) -> list[str]:
    reasons: list[str] = []
    if not isinstance(authority, Mapping):
        return ["source_authority_missing_or_invalid"]
    missing = sorted(_SOURCE_AUTHORITY_FIELDS - set(authority))
    reasons.extend(f"source_authority_field_missing:{item}" for item in missing)
    for field in ("source_id", "source_kind", "source_version", "authority_id", "authority_version", "retention_id", "retention_version"):
        if field in authority and not _valid_id(authority.get(field)):
            reasons.append(f"source_authority_{field}_invalid")
    if not _valid_sha256(authority.get("content_sha256")):
        reasons.append("source_authority_content_sha256_invalid")
    if authority.get("retention_status") != "authorized":
        reasons.append("source_retention_not_authorized")
    if evidence is None or manifest is None:
        return reasons
    if not _has_source_provenance(evidence.get("source_provenance"), authority):
        reasons.append("accounting_evidence_source_binding_missing")
    manifest_authority = manifest.get("authority")
    if not isinstance(manifest_authority, Mapping) or not _has_source_provenance(manifest_authority.get("source_provenance"), authority):
        reasons.append("coverage_manifest_source_binding_missing")
    sources = manifest.get("accounting_sources")
    if not isinstance(sources, list) or not any(
        isinstance(item, Mapping)
        and item.get("source_id") == authority.get("source_id")
        and item.get("source_type") == authority.get("source_kind")
        and item.get("content_sha256") == authority.get("content_sha256")
        for item in sources
    ):
        reasons.append("coverage_manifest_accounting_source_binding_missing")
    return reasons


def _inventory(evidence: Mapping[str, object] | None, authority: Mapping[str, object] | None) -> tuple[Mapping[str, object], ...]:
    rows: list[Mapping[str, object]] = []
    source_id = authority.get("source_id") if isinstance(authority, Mapping) else None
    source_hash = authority.get("content_sha256") if isinstance(authority, Mapping) else None
    for record_class, id_key in _RECORD_CLASSES:
        value = evidence.get(record_class) if isinstance(evidence, Mapping) else None
        if not isinstance(value, list):
            rows.append({"record_class": record_class, "state": "missing_or_invalid", "row_count": None, "record_ids": (), "source_id": source_id, "source_content_sha256": source_hash})
            continue
        ids = tuple(sorted(str(item.get(id_key)) for item in value if isinstance(item, Mapping) and _valid_id(item.get(id_key))))
        rows.append({"record_class": record_class, "state": "present", "row_count": len(value), "record_ids": ids, "source_id": source_id, "source_content_sha256": source_hash})
    return tuple(rows)


def _coverage_diagnostics(manifest: Mapping[str, object] | None) -> tuple[Mapping[str, object], ...]:
    coverage = manifest.get("coverage") if isinstance(manifest, Mapping) else None
    result: list[Mapping[str, object]] = []
    for key in _COVERAGE_CLASSES:
        value = coverage.get(key) if isinstance(coverage, Mapping) else None
        result.append({"coverage_class": key, "state": "complete" if value is True else "incomplete" if value is False else "unavailable", "asserted": value})
    return tuple(result)


def _pricing_fx_ids(evidence: Mapping[str, object] | None) -> tuple[tuple[str, str], ...]:
    pairs = {
        (str(row.get("pricing_snapshot_id")), str(row.get("fx_snapshot_id")))
        for row in (evidence.get("cost_entries", []) if isinstance(evidence, Mapping) else [])
        if isinstance(row, Mapping) and row.get("entry_type") == "actual" and _valid_id(row.get("pricing_snapshot_id")) and _valid_id(row.get("fx_snapshot_id"))
    }
    return tuple(sorted(pairs))


def _source_record_reasons(evidence: Mapping[str, object] | None) -> list[str]:
    reasons: list[str] = []
    if evidence is None:
        return reasons
    for record_class, id_key in _RECORD_CLASSES:
        value = evidence.get(record_class)
        if not isinstance(value, list):
            reasons.append(f"source_record_class_missing:{record_class}")
            continue
        if not value:
            reasons.append(f"source_record_class_empty:{record_class}")
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, Mapping) or not _valid_id(item.get(id_key)):
                reasons.append(f"source_record_identity_invalid:{record_class}")
                continue
            record_id = str(item[id_key])
            if record_id in seen:
                reasons.append(f"source_record_duplicate:{record_class}:{record_id}")
            seen.add(record_id)
    for row in evidence.get("cost_entries", []) if isinstance(evidence.get("cost_entries"), list) else []:
        if isinstance(row, Mapping) and row.get("entry_type") == "actual":
            if not _valid_id(row.get("pricing_snapshot_id")) or not _valid_id(row.get("fx_snapshot_id")):
                reasons.append(f"source_actual_pricing_fx_identity_missing:{row.get('entry_key')}")
    return reasons


def build_durable_accounting_source_export(
    source_view: ReadOnlyDurableAccountingView,
    *,
    project_id: str,
    now,
    max_evidence_age=DEFAULT_MAX_EVIDENCE_AGE,
) -> DurableAccountingSourceExport:
    """Build a source-bound candidate from already-open durable record views.

    The function never supplies a trusted pin.  ``CANDIDATE_NOT_ATTESTED``
    means the source-bound facts reconciled mechanically; it does not mean the
    source, retention identity or coverage authority is independently trusted.
    """

    authority = source_view.source_authority if isinstance(source_view, ReadOnlyDurableAccountingView) else None
    evidence, evidence_reasons = _load_object(
        source_view.accounting_evidence if isinstance(source_view, ReadOnlyDurableAccountingView) else None,
        "accounting_evidence",
    )
    manifest, manifest_reasons = _load_object(
        source_view.coverage_manifest if isinstance(source_view, ReadOnlyDurableAccountingView) else None,
        "coverage_manifest",
    )
    reasons = evidence_reasons + manifest_reasons + _source_diagnostics(authority, evidence, manifest) + _source_record_reasons(evidence)
    inventory = _inventory(evidence, authority)
    coverage = _coverage_diagnostics(manifest)
    pricing_fx = _pricing_fx_ids(evidence)
    if evidence is None or manifest is None:
        return DurableAccountingSourceExport(
            status="NOT_ATTESTABLE",
            source_authority=authority if isinstance(authority, Mapping) else None,
            source_inventory=inventory,
            coverage_diagnostics=coverage,
            pricing_fx_identity_ids=pricing_fx,
            reasons=_unique_reasons(reasons),
        )

    candidate = build_project_budget_snapshot(
        evidence,
        manifest,
        project_id=project_id,
        now=now,
        max_evidence_age=max_evidence_age,
    )
    reasons.extend(candidate.reasons)
    blocking = any(any(reason == prefix or reason.startswith(prefix) for prefix in _BLOCKING_REASONS) for reason in reasons)
    status: SourceExportStatus
    if blocking:
        status = "BLOCKED"
    elif reasons or candidate.status != "CANDIDATE_NOT_ATTESTED":
        status = "NOT_ATTESTABLE"
    else:
        status = "CANDIDATE_NOT_ATTESTED"
    return DurableAccountingSourceExport(
        status=status,
        candidate=candidate,
        candidate_bytes=candidate.snapshot_bytes,
        candidate_sha256=candidate.snapshot_sha256,
        source_authority=authority,
        source_inventory=inventory,
        coverage_diagnostics=coverage,
        pricing_fx_identity_ids=pricing_fx,
        reasons=_unique_reasons(reasons),
    )


__all__ = [
    "DURABLE_ACCOUNTING_EXPORT_SCHEMA",
    "DurableAccountingSourceExport",
    "ReadOnlyDurableAccountingView",
    "build_durable_accounting_source_export",
]
