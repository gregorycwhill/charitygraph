"""Provider-free comparison of independently supplied Phase-5 run inventories.

This module is an evidence comparison seam, not a source adapter.  It accepts
small, already-captured source records and returns observed run-ID coverage
without opening SQLite, reading bridge state, contacting a provider, or
asserting that any caller-controlled manifest is complete.  In particular,
the local catalogue and bridge instruction ledger are never promoted to
project history by this module.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SCHEMA_ID = "charitygraph.phase5.run-inventory-audit"
SCHEMA_VERSION = 1
SCHEMA = f"{SCHEMA_ID}/v{SCHEMA_VERSION}"
NOT_AUTHORITATIVE = "NOT_AUTHORITATIVE"
UNVERIFIED = "UNVERIFIED"


class RunInventoryAuditError(ValueError):
    """Raised when the top-level audit request cannot be formed."""


@dataclass(frozen=True)
class RunInventoryAuditProjection:
    """Immutable diagnostic document and its canonical content identity."""

    document: dict[str, Any]
    canonical_json: bytes
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "document": json.loads(self.canonical_json.decode("utf-8")),
            "canonical_json": self.canonical_json,
            "sha256": self.sha256,
        }


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(child) for child in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and value == value.lower() and all(
        char in "0123456789abcdef" for char in value
    )


_FORBIDDEN_PROVENANCE_PARTS = (
    "payload",
    "prompt",
    "response",
    "credential",
    "authorization",
    "secret",
    "source_text",
    "raw",
)


def _safe_provenance(value: Mapping[str, Any]) -> dict[str, Any]:
    """Retain provenance metadata while excluding payload-like material."""

    safe: dict[str, Any] = {}
    for key, child in value.items():
        key_text = str(key)
        if any(part in key_text.lower() for part in _FORBIDDEN_PROVENANCE_PARTS):
            continue
        if child is None or isinstance(child, (str, int, bool)):
            safe[key_text] = child
        elif isinstance(child, Mapping):
            safe[key_text] = _safe_provenance(child)
    return safe


def _source_key(source: Mapping[str, Any]) -> str:
    identity = _text(source.get("source_id")) or _text(source.get("source_identity")) or "unidentified"
    role = _text(source.get("source_role")) or "untyped"
    digest = source.get("source_byte_sha256") or source.get("content_sha256") or source.get("evidence_digest")
    if isinstance(digest, Mapping):
        digest = digest.get("value")
    return f"{identity}|{role}|{_text(digest) or 'missing-digest'}"


def _run_values(source: Mapping[str, Any], field: str, issues: list[str]) -> list[str]:
    raw = source.get(field, ())
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        issues.append(f"MALFORMED_{field.upper()}")
        return []
    result: list[str] = []
    for value in raw:
        item = _text(value)
        if item is None:
            issues.append(f"MALFORMED_{field.upper()}")
        else:
            result.append(item)
    return result


def _normalise_source(source: Mapping[str, Any], as_of: datetime) -> dict[str, Any]:
    issues: list[str] = []
    source_id = _text(source.get("source_id"))
    source_identity = _text(source.get("source_identity")) or source_id
    role = _text(source.get("source_role"))
    observed_at_text = source.get("observed_at", source.get("acquisition_time", source.get("acquired_at")))
    observed_at = _timestamp(observed_at_text)
    if source_id is None:
        issues.append("MISSING_SOURCE_ID")
    if source_identity is None:
        issues.append("MISSING_SOURCE_IDENTITY")
    if role is None:
        issues.append("MISSING_SOURCE_ROLE")
    if observed_at is None:
        issues.append("MISSING_OR_MALFORMED_OBSERVATION_TIME")

    digest_kind: str | None = None
    digest_value: str | None = None
    if source.get("source_byte_sha256") is not None or source.get("content_sha256") is not None:
        digest_kind = "sha256"
        digest_value = source.get("source_byte_sha256") or source.get("content_sha256")
        if not _valid_sha256(digest_value):
            issues.append("MALFORMED_SOURCE_SHA256")
    else:
        digest = source.get("evidence_digest")
        if isinstance(digest, Mapping):
            digest_kind = _text(digest.get("kind")) or "stable_evidence"
            digest_value = _text(digest.get("value"))
        elif isinstance(digest, str):
            digest_kind = "stable_evidence"
            digest_value = _text(digest)
        if digest_value is None:
            issues.append("MISSING_SOURCE_DIGEST")

    scope = source.get("scope")
    if not isinstance(scope, Mapping):
        issues.append("MISSING_OR_MALFORMED_SCOPE")
        safe_scope: dict[str, Any] = {"scope_id": None, "kind": None}
    else:
        scope_id = _text(scope.get("scope_id") or scope.get("id"))
        scope_kind = _text(scope.get("kind"))
        safe_scope = {"scope_id": scope_id, "kind": scope_kind}
        if scope_id is None or scope_kind is None:
            issues.append("MISSING_OR_MALFORMED_SCOPE")

    schema_version = source.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version < 1:
        issues.append("MALFORMED_SOURCE_SCHEMA_VERSION")
    elif schema_version != SCHEMA_VERSION:
        issues.append("STALE_OR_UNSUPPORTED_SOURCE_SCHEMA_VERSION")

    run_ids = _run_values(source, "run_ids", issues)
    duplicate_run_ids = sorted({run_id for run_id in run_ids if run_ids.count(run_id) > 1})
    if duplicate_run_ids:
        issues.append("DUPLICATE_RUN_IDS")
    unique_run_ids = sorted(set(run_ids))

    receipt_run_ids = _run_values(source, "provider_receipt_run_ids", issues) if "provider_receipt_run_ids" in source else []
    duplicate_receipt_run_ids = sorted({run_id for run_id in receipt_run_ids if receipt_run_ids.count(run_id) > 1})
    if duplicate_receipt_run_ids:
        issues.append("DUPLICATE_PROVIDER_RECEIPT_RUN_IDS")

    missingness = source.get("missingness")
    if not isinstance(missingness, Mapping):
        missingness = {"state": "unknown", "missing_ids": [], "reason": "missingness not supplied"}
        issues.append("MISSING_MISSINGNESS_DECLARATION")
    else:
        missing_state = _text(missingness.get("state")) or "unknown"
        missing_ids = missingness.get("missing_ids", ())
        if not isinstance(missing_ids, Sequence) or isinstance(missing_ids, (str, bytes, bytearray)):
            issues.append("MALFORMED_MISSINGNESS_IDS")
            missing_ids = []
        missingness = {
            "state": missing_state,
            "missing_ids": sorted({str(value) for value in missing_ids if _text(value) is not None}),
            "reason": _text(missingness.get("reason")),
        }
        if missing_state in {"silent", "source_silence", "empty"} or not unique_run_ids:
            issues.append("SOURCE_SILENCE_OR_EMPTY")

    source_owned_claim = source.get("source_owned")
    if source_owned_claim is True:
        issues.append("SELF_DECLARED_SOURCE_OWNERSHIP_UNVERIFIED")
    elif source_owned_claim not in (None, False):
        issues.append("MALFORMED_SOURCE_OWNED_FLAG")

    if source.get("authenticated") is True or source.get("complete") is True:
        issues.append("CALLER_ASSERTED_PROVENANCE_UNVERIFIED")

    stale_after = _timestamp(source.get("stale_after"))
    if stale_after is not None and as_of > stale_after:
        issues.append("STALE_SOURCE_EVIDENCE")
    max_age = source.get("max_age_seconds", source.get("stale_after_seconds"))
    if observed_at is not None and isinstance(max_age, int) and not isinstance(max_age, bool) and max_age >= 0:
        if (as_of - observed_at).total_seconds() > max_age:
            issues.append("STALE_SOURCE_EVIDENCE")
    if max_age is not None and not (isinstance(max_age, int) and not isinstance(max_age, bool) and max_age >= 0):
        issues.append("MALFORMED_STALENESS_BOUND")

    provenance = source.get("provenance")
    if not isinstance(provenance, Mapping):
        issues.append("MISSING_OR_MALFORMED_PROVENANCE")
        safe_provenance: dict[str, Any] = {}
    else:
        safe_provenance = _safe_provenance(provenance)

    records: list[dict[str, Any]] = []
    raw_records = source.get("run_records", ())
    if raw_records is not None:
        if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes, bytearray)):
            issues.append("MALFORMED_RUN_RECORDS")
        else:
            for record in raw_records:
                if not isinstance(record, Mapping) or _text(record.get("run_id")) is None:
                    issues.append("MALFORMED_RUN_RECORDS")
                    continue
                records.append({
                    "run_id": _text(record.get("run_id")),
                    "scope_id": _text(record.get("scope_id")) or safe_scope["scope_id"],
                    "scope_kind": _text(record.get("scope_kind")) or safe_scope["kind"],
                    "schema_version": record.get("schema_version", schema_version),
                    "source_identity": _text(record.get("source_identity")) or source_identity,
                })
    record_ids = {str(record["run_id"]) for record in records}
    if record_ids and record_ids != set(unique_run_ids):
        issues.append("RUN_RECORD_SET_MISMATCH")

    if role in {"bridge_instruction_ledger", "bridge_ledger", "local_sqlite_runs", "persisted_schema29_runs"}:
        issues.append("NON_SOURCE_HISTORY_BOUNDARY")

    source_key = _source_key(source)
    return {
        "source_key": source_key,
        "source_id": source_id,
        "source_identity": source_identity,
        "source_role": role,
        "source_byte_sha256": digest_value if digest_kind == "sha256" and _valid_sha256(digest_value) else None,
        "evidence_digest": {"kind": digest_kind, "value": digest_value} if digest_value is not None else None,
        "observed_at": observed_at_text if isinstance(observed_at_text, str) else None,
        "scope": safe_scope,
        "schema_version": schema_version if isinstance(schema_version, int) and not isinstance(schema_version, bool) else None,
        "run_ids": unique_run_ids,
        "provider_receipt_run_ids": sorted(set(receipt_run_ids)),
        "duplicate_run_ids": duplicate_run_ids,
        "duplicate_provider_receipt_run_ids": duplicate_receipt_run_ids,
        "missingness": missingness,
        "provenance": safe_provenance,
        "source_owned_claimed": source_owned_claim is True,
        "records": records,
        "issues": sorted(set(issues)),
    }


def _role_is_index(role: str | None) -> bool:
    return role in {"run_index", "source_owned_run_index", "project_run_index"} or bool(role and role.endswith("_run_index"))


def audit_phase5_run_inventory(
    sources: Sequence[Mapping[str, Any]],
    *,
    as_of: str,
) -> RunInventoryAuditProjection:
    """Compare captured run-ID populations without creating project authority."""

    if isinstance(sources, (str, bytes, bytearray)) or not isinstance(sources, Sequence) or not sources:
        raise RunInventoryAuditError("sources must be a non-empty sequence of source records")
    as_of_dt = _timestamp(as_of)
    if as_of_dt is None:
        raise RunInventoryAuditError("as_of must be a timezone-aware ISO-8601 timestamp")
    if any(not isinstance(source, Mapping) for source in sources):
        raise RunInventoryAuditError("each source record must be an object")

    normalised = [_normalise_source(source, as_of_dt) for source in sources]
    normalised.sort(key=lambda source: (source["source_key"], source["source_role"] or ""))
    source_keys = [source["source_key"] for source in normalised]
    if len(source_keys) != len(set(source_keys)):
        for index, source in enumerate(normalised):
            source["source_key"] = f"{source['source_key']}#{index + 1}"

    union_ids = sorted({run_id for source in normalised for run_id in source["run_ids"]})
    index_ids = sorted({run_id for source in normalised if _role_is_index(source["source_role"]) for run_id in source["run_ids"]})
    if not index_ids:
        index_ids = union_ids
    intersection_ids = sorted(set(union_ids).intersection(*(set(source["run_ids"]) for source in normalised)))

    omitted_by_source: dict[str, list[str]] = {}
    orphaned_by_source: dict[str, list[str]] = {}
    duplicate_by_source: dict[str, list[str]] = {}
    for source in normalised:
        key = source["source_key"]
        omitted_by_source[key] = sorted(set(union_ids) - set(source["run_ids"]))
        orphaned_by_source[key] = sorted(set(source["run_ids"]) - set(index_ids)) if not _role_is_index(source["source_role"]) else []
        duplicate_by_source[key] = source["duplicate_run_ids"]

    run_signatures: defaultdict[str, set[tuple[Any, ...]]] = defaultdict(set)
    run_source_identities: defaultdict[str, set[str]] = defaultdict(set)
    for source in normalised:
        fallback = (
            source["scope"].get("scope_id"),
            source["scope"].get("kind"),
            source["schema_version"],
        )
        records_by_id = {record["run_id"]: record for record in source["records"]}
        for run_id in source["run_ids"]:
            record = records_by_id.get(run_id)
            signature = fallback if record is None else (
                record.get("scope_id"), record.get("scope_kind"), record.get("schema_version")
            )
            run_signatures[run_id].add(signature)
            identity = (record or {}).get("source_identity") or source["source_identity"]
            if identity:
                run_source_identities[run_id].add(identity)
    conflicting_ids = sorted(run_id for run_id, signatures in run_signatures.items() if len(signatures) > 1)
    source_mismatch_ids = sorted(run_id for run_id, identities in run_source_identities.items() if len(identities) > 1)

    independence_groups: defaultdict[str, list[str]] = defaultdict(list)
    for source in normalised:
        group = source["source_identity"] or f"unidentified:{source['source_key']}"
        independence_groups[group].append(source["source_key"])
    same_source_groups = {
        group: sorted(keys) for group, keys in sorted(independence_groups.items()) if len(keys) > 1
    }

    reason_codes = {
        "NO_AUTHENTICATED_SOURCE_OWNED_COMPLETENESS_ADAPTER",
        "PROJECT_WIDE_COMPLETENESS_UNVERIFIED",
    }
    for source in normalised:
        reason_codes.update(source["issues"])
    if conflicting_ids:
        reason_codes.add("CONFLICTING_RUN_METADATA")
    if source_mismatch_ids:
        reason_codes.add("SOURCE_IDENTITY_MISMATCH")
    if same_source_groups:
        reason_codes.add("SAME_SOURCE_FALSE_INDEPENDENCE")
    if any(orphaned_by_source.values()):
        reason_codes.add("ORPHANED_RUN_IDS")
    if any(omitted_by_source.values()):
        reason_codes.add("OMITTED_RUN_IDS")
    if any(source["provider_receipt_run_ids"] and set(source["provider_receipt_run_ids"]) - set(index_ids) for source in normalised):
        reason_codes.add("UNKNOWN_PROVIDER_RECEIPT_RUN_IDS")

    sources_document = []
    for source in normalised:
        source_document = {key: value for key, value in source.items() if key != "records"}
        sources_document.append(source_document)

    document: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "status": NOT_AUTHORITATIVE,
        "authority": {
            "status": UNVERIFIED,
            "project_wide_authoritative": False,
            "authoritative_total": None,
            "remaining_spend": None,
            "basis": "no authenticated source-owned project-wide completeness adapter is present",
        },
        "as_of": as_of,
        "sources": sources_document,
        "coverage": {
            "observed_run_ids": union_ids,
            "known_observed_subset": union_ids,
            "intersection_run_ids": intersection_ids,
            "index_run_ids": index_ids,
            "omitted_run_ids_by_source": omitted_by_source,
            "orphaned_run_ids_by_source": orphaned_by_source,
            "duplicate_run_ids_by_source": duplicate_by_source,
            "conflicting_run_ids": conflicting_ids,
            "source_identity_mismatch_run_ids": source_mismatch_ids,
            "same_source_groups": same_source_groups,
            "independent_source_count": len(independence_groups),
        },
        "reason_codes": sorted(reason_codes),
        "limitations": [
            "Caller-controlled source_owned, authenticated and complete fields are observations, not authentication.",
            "The local SQLite runs table and bridge instruction ledger are not project history.",
            "No provider receipts, invoices, pricing, FX or AUD 10 remaining-spend claim is established.",
        ],
    }
    canonical_json = _canonical_bytes(document)
    return RunInventoryAuditProjection(
        document=document,
        canonical_json=canonical_json,
        sha256=hashlib.sha256(canonical_json).hexdigest(),
    )


def project_phase5_run_inventory_audit(*args: Any, **kwargs: Any) -> RunInventoryAuditProjection:
    """Compatibility spelling for the pure audit projection."""

    return audit_phase5_run_inventory(*args, **kwargs)


def canonical_run_inventory_audit_json(projection: RunInventoryAuditProjection | Mapping[str, Any]) -> bytes:
    document = projection.document if isinstance(projection, RunInventoryAuditProjection) else projection
    return _canonical_bytes(document)


def run_inventory_audit_sha256(projection: RunInventoryAuditProjection | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_run_inventory_audit_json(projection)).hexdigest()


__all__ = [
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SCHEMA",
    "NOT_AUTHORITATIVE",
    "UNVERIFIED",
    "RunInventoryAuditError",
    "RunInventoryAuditProjection",
    "audit_phase5_run_inventory",
    "project_phase5_run_inventory_audit",
    "canonical_run_inventory_audit_json",
    "run_inventory_audit_sha256",
]
