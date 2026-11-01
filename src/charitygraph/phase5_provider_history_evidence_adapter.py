"""Provider-neutral, read-only evidence adapter for later provider history.

The adapter accepts one explicitly supplied immutable JSON export and metadata.
It never acquires bytes, opens a catalogue, contacts a provider, writes state,
or treats a caller assertion as host authentication.  Its useful output is an
SHA-bound observed subset and mechanical relationship/missingness diagnostics.
The authority fields are deliberately permanent fail-closed values until a
separately trusted host ingress exists.

The accepted envelope is intentionally small and provider-neutral.  A
provider-specific export parser, if one is ever approved, must produce this
envelope and retain the original bytes privately; unsupported native formats
are reported rather than guessed.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .contracts.canonical import canonical_json_bytes
from .phase5_run_inventory_audit import audit_phase5_run_inventory


SCHEMA_ID = "charitygraph.phase5.provider-history-evidence"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"
RAW_EXPORT_SCHEMA = "charitygraph.phase5.provider-history-export/1"

STATUS_PARTIAL = "PARTIAL"
STATUS_FAIL_CLOSED = "FAIL_CLOSED"
EVIDENCE_OBSERVED = "OBSERVED"
EVIDENCE_NOT_OBSERVED = "NOT_OBSERVED"
AUTHORITY_FAIL_CLOSED = "FAIL_CLOSED"
NOT_AUTHORITATIVE = "NOT_AUTHORITATIVE"

_RUN_INDEX_KINDS = frozenset({"run_index", "cumulative_run_index"})
_RECEIPT_KINDS = frozenset({"billing_receipt", "billing_receipts", "receipt_export"})
_SUPPORTED_KINDS = _RUN_INDEX_KINDS | _RECEIPT_KINDS
_SOURCE_IDENTITY_ALIASES = {
    "source_id": "source_id",
    "identity_id": "source_id",
    "provider_id": "provider_id",
    "provider": "provider_id",
    "account_id": "account_id",
    "project_id": "account_id",
    "identity_version": "identity_version",
    "version": "identity_version",
}
_SOURCE_IDENTITY_FIELDS = ("source_id", "provider_id", "account_id", "identity_version")
_FATAL_REASONS = frozenset(
    {
        "RAW_EXPORT_BYTES_MISSING",
        "RAW_EXPORT_NOT_UTF8_JSON",
        "RAW_EXPORT_TOP_LEVEL_INVALID",
        "UNSUPPORTED_PROVIDER_NATIVE_FORMAT",
        "STALE_OR_UNKNOWN_EXPORT_SCHEMA",
        "MISSING_EXPORT_SCOPE",
        "MALFORMED_EXPORT_SCOPE",
        "MISSING_EXPORT_WINDOW",
        "MALFORMED_EXPORT_WINDOW",
        "MISSING_SOURCE_IDENTITY",
        "MALFORMED_SOURCE_IDENTITY",
        "MISSING_ACQUISITION_METADATA",
        "MALFORMED_ACQUISITION_METADATA",
        "SOURCE_BYTE_SHA256_MISMATCH",
        "EXPORT_SOURCE_IDENTITY_CONTRADICTION",
        "MISSING_RUN_PHYSICAL_ATTEMPT_ID",
    }
)


class ProviderHistoryEvidenceAdapterError(ValueError):
    """Raised only when the adapter call itself cannot be formed."""


@dataclass(frozen=True)
class ProviderHistoryEvidenceProjection:
    """Canonical observed evidence and its content identity."""

    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    @property
    def status(self) -> str:
        return str(self.document["status"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(
        character in "0123456789abcdef" for character in value
    )


def _timestamp(value: Any) -> tuple[str | None, datetime | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value, None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return value, None
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat(timespec="microseconds").replace("+00:00", "Z"), utc


def _unique(values: Iterable[str]) -> list[str]:
    return sorted(set(values))


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(child) for child in value]
    return value


def _safe_text_fields(value: Mapping[str, Any], names: Sequence[str]) -> dict[str, str | None]:
    return {name: _text(value.get(name)) for name in names}


def _safe_source_identity(
    value: Any,
    reasons: list[str],
    *,
    diagnostic_prefix: str = "SOURCE_IDENTITY",
) -> dict[str, str | None]:
    empty = {field: None for field in _SOURCE_IDENTITY_FIELDS}
    if not isinstance(value, Mapping):
        reasons.append(f"MISSING_{diagnostic_prefix}" if value is None else f"MALFORMED_{diagnostic_prefix}")
        return empty

    if any(not isinstance(key, str) or key not in _SOURCE_IDENTITY_ALIASES for key in value):
        reasons.append(f"{diagnostic_prefix}_UNKNOWN_FIELDS_OMITTED")

    result: dict[str, str | None] = {}
    malformed = False
    for field in _SOURCE_IDENTITY_FIELDS:
        candidates = [key for key, canonical in _SOURCE_IDENTITY_ALIASES.items() if canonical == field and key in value]
        selected: str | None = None
        for key in candidates:
            candidate = value[key]
            candidate_text = _text(candidate)
            if candidate is not None and candidate_text is None:
                malformed = True
            if selected is None and candidate_text is not None:
                selected = candidate_text
        result[field] = selected
    if malformed:
        reasons.append(f"{diagnostic_prefix}_MALFORMED_FIELDS_OMITTED")
    if result["source_id"] is None or result["provider_id"] is None:
        reasons.append("MALFORMED_SOURCE_IDENTITY" if diagnostic_prefix == "SOURCE_IDENTITY" else f"MALFORMED_{diagnostic_prefix}")
    return result


def _safe_acquisition(value: Any, raw_sha: str, reasons: list[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        reasons.append("MISSING_ACQUISITION_METADATA" if value is None else "MALFORMED_ACQUISITION_METADATA")
        return {
            "acquisition_id": None,
            "acquired_at": None,
            "observed_at": None,
            "source_locator": None,
            "transport": None,
            "collector_version": None,
            "source_byte_sha256": raw_sha,
        }
    acquired_text, _ = _timestamp(value.get("acquired_at"))
    observed_text, _ = _timestamp(value.get("observed_at", value.get("acquisition_time")))
    supplied_sha = value.get("source_byte_sha256") or value.get("content_sha256")
    if supplied_sha is not None and supplied_sha != raw_sha:
        reasons.append("SOURCE_BYTE_SHA256_MISMATCH")
    if supplied_sha is not None and not _valid_sha256(supplied_sha):
        reasons.append("MALFORMED_SOURCE_BYTE_SHA256")
    result = {
        "acquisition_id": _text(value.get("acquisition_id") or value.get("capture_id")),
        "acquired_at": acquired_text,
        "observed_at": observed_text,
        "source_locator": _text(value.get("source_locator") or value.get("locator")),
        "transport": _text(value.get("transport")),
        "collector_version": _text(value.get("collector_version")),
        "source_byte_sha256": raw_sha,
    }
    if result["acquisition_id"] is None or result["acquired_at"] is None or result["observed_at"] is None:
        reasons.append("MALFORMED_ACQUISITION_METADATA")
    return result


def _safe_scope(value: Any, reasons: list[str], *, label: str) -> dict[str, str | None]:
    if not isinstance(value, Mapping):
        reasons.append("MISSING_EXPORT_SCOPE" if value is None else "MALFORMED_EXPORT_SCOPE")
        return {"scope_id": None, "kind": None}
    result = {"scope_id": _text(value.get("scope_id") or value.get("id")), "kind": _text(value.get("kind"))}
    if result["scope_id"] is None or result["kind"] is None:
        reasons.append("MALFORMED_EXPORT_SCOPE")
    return result


def _safe_window(value: Any, reasons: list[str]) -> tuple[dict[str, Any], datetime | None, datetime | None]:
    if not isinstance(value, Mapping):
        reasons.append("MISSING_EXPORT_WINDOW" if value is None else "MALFORMED_EXPORT_WINDOW")
        return {"start": None, "end": None, "coverage_state": "unknown"}, None, None
    start_text, start = _timestamp(value.get("start") or value.get("window_start"))
    end_text, end = _timestamp(value.get("end") or value.get("window_end"))
    coverage_state = _text(value.get("coverage_state") or value.get("state")) or "unknown"
    result = {"start": start_text, "end": end_text, "coverage_state": coverage_state}
    if start is None or end is None:
        reasons.append("MALFORMED_EXPORT_WINDOW")
    elif start > end:
        reasons.append("MALFORMED_EXPORT_WINDOW")
    if coverage_state in {"partial", "bounded_partial", "unknown"}:
        reasons.append("PARTIAL_OR_UNKNOWN_TIME_WINDOW")
    if value.get("complete") is True or coverage_state == "complete":
        reasons.append("CALLER_ASSERTED_WINDOW_COMPLETENESS_UNVERIFIED")
    return result, start, end


def _safe_missingness(value: Any, reasons: list[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        reasons.append("MISSING_MISSINGNESS_DECLARATION")
        return {"state": "unknown", "missing_ids": [], "reason": "missingness not supplied"}
    state = _text(value.get("state")) or "unknown"
    raw_ids = value.get("missing_ids", ())
    if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes, bytearray)):
        reasons.append("MALFORMED_MISSINGNESS_IDS")
        raw_ids = ()
    missing_ids = _unique(str(item).strip() for item in raw_ids if _text(item) is not None)
    if state in {"silent", "source_silence", "empty"}:
        reasons.append("SOURCE_SILENCE_OR_EMPTY")
    return {"state": state, "missing_ids": missing_ids, "reason": _text(value.get("reason"))}


def _record_identifier(record: Mapping[str, Any], kind: str) -> str | None:
    if kind in _RUN_INDEX_KINDS:
        return _text(record.get("run_id"))
    return _text(record.get("receipt_id") or record.get("provider_receipt_id"))


def _normalise_record(
    record: Any,
    *,
    kind: str,
    scope: Mapping[str, Any],
    window_start: datetime | None,
    window_end: datetime | None,
    reasons: list[str],
) -> dict[str, Any] | None:
    if not isinstance(record, Mapping):
        reasons.append("MALFORMED_EXPORT_RECORD")
        return None
    identifier = _record_identifier(record, kind)
    if identifier is None:
        reasons.append("MISSING_EXPORT_RECORD_IDENTITY")
        return None
    record_scope_id = _text(record.get("scope_id")) or scope.get("scope_id")
    record_scope_kind = _text(record.get("scope_kind")) or scope.get("kind")
    observed_text, observed = _timestamp(record.get("observed_at") or record.get("received_at"))
    normalised: dict[str, Any] = {
        "record_id": identifier,
        "scope_id": record_scope_id,
        "scope_kind": record_scope_kind,
        "observed_at": observed_text,
        "schema_version": record.get("schema_version", 1),
    }
    if kind in _RUN_INDEX_KINDS:
        normalised["run_id"] = identifier
        normalised["physical_attempt_id"] = _text(record.get("physical_attempt_id"))
        if normalised["physical_attempt_id"] is None:
            reasons.append("MISSING_RUN_PHYSICAL_ATTEMPT_ID")
    else:
        normalised.update(
            {
                "receipt_id": identifier,
                "run_id": _text(record.get("run_id")),
                "physical_attempt_id": _text(record.get("physical_attempt_id")),
                "provider_request_id": _text(record.get("provider_request_id") or record.get("request_id")),
                "accounting_amount": _text(record.get("accounting_amount") or record.get("amount")),
                "accounting_currency": _text(record.get("accounting_currency") or record.get("currency")),
                "provider_amount": _text(record.get("provider_amount")),
                "provider_currency": _text(record.get("provider_currency")),
                "pricing_snapshot_id": _text(record.get("pricing_snapshot_id")),
                "fx_snapshot_id": _text(record.get("fx_snapshot_id")),
            }
        )
    if record.get("schema_version") not in (None, 1):
        reasons.append("STALE_OR_UNSUPPORTED_RECORD_SCHEMA")
    if observed is not None and ((window_start is not None and observed < window_start) or (window_end is not None and observed > window_end)):
        reasons.append("MIXED_TIME_WINDOWS")
    if kind in _RECEIPT_KINDS:
        if normalised["run_id"] is None:
            reasons.append("BROKEN_RECEIPT_RUN_FOREIGN_KEY")
        if normalised["physical_attempt_id"] is None:
            reasons.append("MISSING_RECEIPT_PHYSICAL_ATTEMPT_ID")
        for field, code in (
            ("accounting_amount", "MISSING_COST_AMOUNT"),
            ("accounting_currency", "MISSING_COST_CURRENCY"),
            ("pricing_snapshot_id", "MISSING_PRICING_SNAPSHOT"),
            ("fx_snapshot_id", "MISSING_FX_SNAPSHOT"),
        ):
            if normalised[field] is None:
                reasons.append(code)
    return normalised


def _record_diagnostics(records: Sequence[Mapping[str, Any]], kind: str, reasons: list[str]) -> dict[str, Any]:
    by_id: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_id[str(record["record_id"])].append(record)
    duplicate_ids: list[str] = []
    conflicting_ids: list[str] = []
    for identifier, rows in sorted(by_id.items()):
        if len(rows) > 1:
            if len({_canonical(json.dumps(row, sort_keys=True, separators=(",", ":"))) for row in rows}) == 1:
                duplicate_ids.append(identifier)
                reasons.append("DUPLICATE_EXPORT_RECORDS")
            else:
                conflicting_ids.append(identifier)
                reasons.append("CONFLICTING_EXPORT_RECORDS")
    physical_to_runs: defaultdict[str, set[str]] = defaultdict(set)
    for row in records:
        physical_id = _text(row.get("physical_attempt_id"))
        run_id = _text(row.get("run_id"))
        if physical_id and run_id:
            physical_to_runs[physical_id].add(run_id)
    conflicting_physical = sorted(identifier for identifier, run_ids in physical_to_runs.items() if len(run_ids) > 1)
    if conflicting_physical:
        reasons.append("CONFLICTING_PHYSICAL_ATTEMPT_IDENTITY")
    missing_physical_attempt_record_ids = sorted(
        str(record["record_id"])
        for record in records
        if kind in _RUN_INDEX_KINDS and _text(record.get("physical_attempt_id")) is None
    )
    return {
        "duplicate_record_ids": sorted(duplicate_ids),
        "conflicting_record_ids": sorted(conflicting_ids),
        "conflicting_physical_attempt_ids": conflicting_physical,
        "missing_physical_attempt_record_ids": missing_physical_attempt_record_ids,
        "record_count": len(records),
    }


def _safe_assertion(value: Any, *, label: str, reasons: list[str]) -> dict[str, Any]:
    if value is None:
        reasons.append(f"MISSING_{label.upper()}")
        return {"state": "MISSING", "verified": False, "reference": None}
    if not isinstance(value, Mapping):
        reasons.append(f"MALFORMED_{label.upper()}")
        return {"state": "UNVERIFIED_CALLER_INPUT", "verified": False, "reference": None}
    if any(value.get(name) is True for name in ("authenticated", "verified", "complete", "source_owned")):
        reasons.append(f"CALLER_ASSERTED_{label.upper()}_UNVERIFIED")
    reference = _text(value.get("attestation_id") or value.get("reference") or value.get("proof_ref"))
    return {"state": "UNVERIFIED_CALLER_INPUT", "verified": False, "reference": reference}


def _build_projection(document: dict[str, Any]) -> ProviderHistoryEvidenceProjection:
    canonical = canonical_json_bytes(document)
    return ProviderHistoryEvidenceProjection(document=document, canonical_json=canonical, sha256=_sha256(canonical))


def adapt_phase5_provider_history_evidence(
    raw_export_bytes: bytes,
    *,
    source_identity: Mapping[str, Any],
    acquisition_metadata: Mapping[str, Any],
    host_attestation: Mapping[str, Any] | None = None,
    source_owned_completeness: Mapping[str, Any] | None = None,
    reconciliation_inputs: Mapping[str, Any] | None = None,
) -> ProviderHistoryEvidenceProjection:
    """Normalize one supplied export without granting provider authority.

    ``host_attestation`` and ``source_owned_completeness`` are accepted only as
    traceable caller observations.  This bounded adapter has no trusted host
    verifier, so neither can make the result authoritative.
    """

    if not isinstance(raw_export_bytes, bytes):
        raise ProviderHistoryEvidenceAdapterError("raw_export_bytes must be immutable bytes")
    reasons: list[str] = []
    raw_sha = _sha256(raw_export_bytes)
    identity = _safe_source_identity(source_identity, reasons)
    acquisition = _safe_acquisition(acquisition_metadata, raw_sha, reasons)
    host = _safe_assertion(host_attestation, label="host_attestation", reasons=reasons)
    completeness = _safe_assertion(source_owned_completeness, label="source_owned_completeness", reasons=reasons)

    parsed: Mapping[str, Any] | None = None
    parse_error: str | None = None
    if not raw_export_bytes:
        reasons.append("RAW_EXPORT_BYTES_MISSING")
    else:
        try:
            decoded = json.loads(raw_export_bytes.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
            if not isinstance(decoded, Mapping):
                reasons.append("RAW_EXPORT_TOP_LEVEL_INVALID")
            else:
                parsed = decoded
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            parse_error = str(exc) or "invalid JSON"
            reasons.append("RAW_EXPORT_NOT_UTF8_JSON")

    export: dict[str, Any] = {
        "schema": None,
        "schema_version": None,
        "kind": None,
        "export_id": None,
        "raw_export_sha256": raw_sha,
        "source_identity": None,
    }
    scope: dict[str, Any] = {"scope_id": None, "kind": None}
    window: dict[str, Any] = {"start": None, "end": None, "coverage_state": "unknown"}
    missingness = {"state": "unknown", "missing_ids": [], "reason": "export not parsed"}
    records: list[dict[str, Any]] = []
    record_diagnostics: dict[str, Any] = {
        "duplicate_record_ids": [],
        "conflicting_record_ids": [],
        "conflicting_physical_attempt_ids": [],
        "missing_physical_attempt_record_ids": [],
        "record_count": 0,
    }
    kind: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None

    if parsed is not None:
        raw_schema = parsed.get("schema_id", parsed.get("schema"))
        raw_version = parsed.get("schema_version", parsed.get("version", 1))
        export.update(
            {
                "schema": _text(raw_schema),
                "schema_version": raw_version if isinstance(raw_version, int) and not isinstance(raw_version, bool) else None,
                "kind": _text(parsed.get("export_kind") or parsed.get("format")),
                "export_id": _text(parsed.get("export_id") or parsed.get("capture_id")),
            }
        )
        if raw_schema != RAW_EXPORT_SCHEMA or raw_version != 1:
            reasons.append("STALE_OR_UNKNOWN_EXPORT_SCHEMA")
        kind = export["kind"] if export["kind"] in _SUPPORTED_KINDS else None
        if kind is None:
            reasons.append("UNSUPPORTED_PROVIDER_NATIVE_FORMAT")
        raw_identity = parsed.get("source_identity")
        if raw_identity is not None:
            if isinstance(raw_identity, Mapping):
                export["source_identity"] = _safe_source_identity(
                    raw_identity,
                    reasons,
                    diagnostic_prefix="EXPORT_SOURCE_IDENTITY",
                )
                for key in ("source_id", "provider_id", "account_id"):
                    actual = export["source_identity"][key]
                    expected = identity[key]
                    if actual is not None and expected is not None and actual != expected:
                        reasons.append("EXPORT_SOURCE_IDENTITY_CONTRADICTION")
            else:
                export["source_identity"] = None
                reasons.append("MALFORMED_EXPORT_SOURCE_IDENTITY")
        scope = _safe_scope(parsed.get("scope"), reasons, label="export")
        window, window_start, window_end = _safe_window(parsed.get("window"), reasons)
        missingness = _safe_missingness(parsed.get("missingness"), reasons)
        raw_records = parsed.get("records")
        if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes, bytearray)):
            reasons.append("MALFORMED_EXPORT_RECORDS")
            raw_records = ()
        if kind is not None:
            for raw_record in raw_records:
                normalised = _normalise_record(
                    raw_record,
                    kind=kind,
                    scope=scope,
                    window_start=window_start,
                    window_end=window_end,
                    reasons=reasons,
                )
                if normalised is not None:
                    records.append(normalised)
            records.sort(key=canonical_json_bytes)
            record_diagnostics = _record_diagnostics(records, kind, reasons)
        if not records:
            reasons.append("SOURCE_SILENCE_OR_EMPTY")

    run_ids = _unique(row["run_id"] for row in records if _text(row.get("run_id")))
    physical_ids = _unique(row["physical_attempt_id"] for row in records if _text(row.get("physical_attempt_id")))
    receipt_ids = _unique(row["receipt_id"] for row in records if _text(row.get("receipt_id")))
    receipt_run_ids = _unique(row["run_id"] for row in records if kind in _RECEIPT_KINDS and _text(row.get("run_id")))
    receipt_physical_ids = _unique(row["physical_attempt_id"] for row in records if kind in _RECEIPT_KINDS and _text(row.get("physical_attempt_id")))
    known_run_ids = set(run_ids)
    known_physical_ids = set(physical_ids)
    reference_run_ids: set[str] = set()
    reference_physical_ids: set[str] = set()
    if parsed is not None:
        raw_known_run_ids = parsed.get("known_run_ids", ())
        raw_known_physical_ids = parsed.get("known_physical_attempt_ids", ())
        if isinstance(raw_known_run_ids, Sequence) and not isinstance(raw_known_run_ids, (str, bytes, bytearray)):
            reference_run_ids = {str(value).strip() for value in raw_known_run_ids if _text(value) is not None}
        if isinstance(raw_known_physical_ids, Sequence) and not isinstance(raw_known_physical_ids, (str, bytes, bytearray)):
            reference_physical_ids = {str(value).strip() for value in raw_known_physical_ids if _text(value) is not None}
    if kind in _RECEIPT_KINDS:
        if not reference_run_ids:
            reasons.append("RUN_INDEX_NOT_PRESENT_FOR_RECEIPT_EXPORT")
        if not reference_physical_ids:
            reasons.append("PHYSICAL_ATTEMPT_INDEX_NOT_PRESENT_FOR_RECEIPT_EXPORT")
    unknown_receipt_run_ids = sorted(set(receipt_run_ids) - (reference_run_ids or known_run_ids)) if kind in _RECEIPT_KINDS else []
    unknown_receipt_physical_ids = sorted(set(receipt_physical_ids) - (reference_physical_ids or known_physical_ids)) if kind in _RECEIPT_KINDS else []
    if unknown_receipt_run_ids:
        reasons.append("UNKNOWN_ORPHAN_RECEIPT_RUN_IDS")
    if unknown_receipt_physical_ids:
        reasons.append("UNKNOWN_ORPHAN_RECEIPT_PHYSICAL_ATTEMPT_IDS")

    cost_missingness = {
        "state": "not_applicable" if kind in _RUN_INDEX_KINDS or kind is None else "observed",
        "receipt_ids": receipt_ids,
        "missing_amount_receipt_ids": sorted(row["receipt_id"] for row in records if kind in _RECEIPT_KINDS and row.get("accounting_amount") is None),
        "missing_currency_receipt_ids": sorted(row["receipt_id"] for row in records if kind in _RECEIPT_KINDS and row.get("accounting_currency") is None),
        "missing_pricing_receipt_ids": sorted(row["receipt_id"] for row in records if kind in _RECEIPT_KINDS and row.get("pricing_snapshot_id") is None),
        "missing_fx_receipt_ids": sorted(row["receipt_id"] for row in records if kind in _RECEIPT_KINDS and row.get("fx_snapshot_id") is None),
    }
    if any(cost_missingness[name] for name in ("missing_amount_receipt_ids", "missing_currency_receipt_ids", "missing_pricing_receipt_ids", "missing_fx_receipt_ids")):
        cost_missingness["state"] = "partial"

    run_inventory_audit: dict[str, Any] | None = None
    if parsed is not None and kind is not None:
        source_role = "run_index" if kind in _RUN_INDEX_KINDS else "provider_receipt_population"
        audit_source = {
            "source_id": identity["source_id"],
            "source_identity": f"{identity['provider_id']}|{identity['account_id'] or 'unknown-account'}",
            "source_role": source_role,
            "source_byte_sha256": raw_sha,
            "observed_at": acquisition.get("observed_at"),
            "scope": scope,
            "schema_version": 1,
            "run_ids": run_ids if kind in _RUN_INDEX_KINDS else receipt_run_ids,
            "provider_receipt_run_ids": receipt_run_ids,
            "missingness": missingness,
            "provenance": {"acquisition_id": acquisition.get("acquisition_id"), "source_id": identity["source_id"]},
            "run_records": records,
        }
        extra_sources = []
        if isinstance(reconciliation_inputs, Mapping):
            supplied = reconciliation_inputs.get("run_inventory_sources", ())
            if isinstance(supplied, Sequence) and not isinstance(supplied, (str, bytes, bytearray)):
                extra_sources = [item for item in supplied if isinstance(item, Mapping)]
        audit_sources = [audit_source, *extra_sources]
        audit_as_of = acquisition.get("observed_at")
        if isinstance(audit_as_of, str):
            try:
                run_inventory_audit = audit_phase5_run_inventory(audit_sources, as_of=audit_as_of).document
            except (TypeError, ValueError):
                reasons.append("RUN_INVENTORY_RECONCILIATION_UNAVAILABLE")

    if isinstance(reconciliation_inputs, Mapping):
        external_ids = reconciliation_inputs.get("known_run_ids")
        if isinstance(external_ids, Sequence) and not isinstance(external_ids, (str, bytes, bytearray)):
            external_run_ids = {str(value) for value in external_ids if _text(value) is not None}
            if external_run_ids - set(run_ids) and kind in _RUN_INDEX_KINDS:
                reasons.append("OMITTED_KNOWN_RUN_IDS")
        if reconciliation_inputs.get("cost_reconciliation") is not None:
            reasons.append("COST_RECONCILIATION_INPUT_REFERENCE_ONLY")

    reason_codes = _unique(reasons)
    structural_failure = bool(set(reason_codes) & _FATAL_REASONS)
    evidence_state = EVIDENCE_OBSERVED if records and not structural_failure else EVIDENCE_NOT_OBSERVED
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_FAIL_CLOSED if structural_failure else STATUS_PARTIAL,
        "evidence_state": evidence_state,
        "source": {
            "identity": identity,
            "acquisition": acquisition,
            "raw_export_sha256": raw_sha,
            "raw_export_retained_by_adapter": False,
        },
        "export": export,
        "scope": scope,
        "window": window,
        "missingness": missingness,
        "observed": {
            "run_ids": run_ids,
            "physical_attempt_ids": physical_ids,
            "receipt_ids": receipt_ids,
            "records": records,
            "record_diagnostics": record_diagnostics,
        },
        "relationships": {
            "receipt_run_ids": receipt_run_ids,
            "receipt_physical_attempt_ids": receipt_physical_ids,
            "unknown_orphan_receipt_run_ids": unknown_receipt_run_ids,
            "unknown_orphan_receipt_physical_attempt_ids": unknown_receipt_physical_ids,
            "duplicate_or_conflicting_record_ids": sorted(set(record_diagnostics["duplicate_record_ids"]) | set(record_diagnostics["conflicting_record_ids"])),
        },
        "cost_missingness": cost_missingness,
        "host_attestation": host,
        "source_owned_completeness": completeness,
        "authority": {
            "status": AUTHORITY_FAIL_CLOSED,
            "basis": "no trusted host-authenticated provider provenance and source-owned completeness verifier is available in this bounded adapter",
            "project_wide_authoritative": False,
            "authoritative_total": None,
            "remaining_spend": None,
            "send_authorization": "not_authorized_for_send",
        },
        "reconciliation": {
            "run_inventory_audit": run_inventory_audit,
            "cost_reconciliation": "input-reference-only; existing project-cost contract remains authoritative for its own supplied snapshot",
        },
        "reason_codes": reason_codes,
        "limitations": [
            "Raw export bytes are represented only by SHA-256 and are not retained or emitted by this adapter.",
            "Caller-provided authentication, completeness, signatures, matching IDs and timestamps do not establish host provenance.",
            "Observed records are a bounded subset; no project-wide total, remainder, invoice, FX authority or exactly-once provider effect is established.",
        ],
    }
    if parse_error is not None:
        document["parse_error_class"] = "invalid_utf8_or_json"
    return _build_projection(document)


def ingest_phase5_provider_history_evidence(*args: Any, **kwargs: Any) -> ProviderHistoryEvidenceProjection:
    """Alias emphasizing that this is ingestion/normalisation, not authority."""

    return adapt_phase5_provider_history_evidence(*args, **kwargs)


def project_phase5_provider_history_evidence(*args: Any, **kwargs: Any) -> ProviderHistoryEvidenceProjection:
    """Compatibility spelling for the pure evidence projection."""

    return adapt_phase5_provider_history_evidence(*args, **kwargs)


def canonical_provider_history_evidence_json(
    projection: ProviderHistoryEvidenceProjection | Mapping[str, Any],
) -> bytes:
    document = projection.document if isinstance(projection, ProviderHistoryEvidenceProjection) else projection
    return canonical_json_bytes(document)


def provider_history_evidence_sha256(projection: ProviderHistoryEvidenceProjection | Mapping[str, Any]) -> str:
    return _sha256(canonical_provider_history_evidence_json(projection))


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCHEMA",
    "RAW_EXPORT_SCHEMA",
    "STATUS_PARTIAL",
    "STATUS_FAIL_CLOSED",
    "EVIDENCE_OBSERVED",
    "EVIDENCE_NOT_OBSERVED",
    "AUTHORITY_FAIL_CLOSED",
    "NOT_AUTHORITATIVE",
    "ProviderHistoryEvidenceAdapterError",
    "ProviderHistoryEvidenceProjection",
    "adapt_phase5_provider_history_evidence",
    "ingest_phase5_provider_history_evidence",
    "project_phase5_provider_history_evidence",
    "canonical_provider_history_evidence_json",
    "provider_history_evidence_sha256",
]
