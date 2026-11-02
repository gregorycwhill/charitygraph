"""Deterministic local retention for one exact ACNC source record.

This module is intentionally an intake adapter, not a discovery or acquisition
client.  The caller supplies already acquired official ACNC bytes, the exact
durable CharityGraph subject and scope, and a separately materialised
representation.  The adapter records source/representation lineage and can
lower the result into the existing provider-free T3 binder without changing
that binder.

Local retention is represented separately from provider processing and public
redistribution.  The latter are ``blocked``/``not_assessed`` until a caller
supplies an exact, real authority record; no permission is inferred from local
retention or public accessibility.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .contracts.canonical import canonical_json_bytes
from .phase5_t3_source_evidence_binding import (
    LOCAL_RETENTION_POLICY_ID,
    LOCAL_RETENTION_POLICY_VERSION,
    SourceEvidenceBindingResult,
    bind_acnc_source_evidence,
)


RETENTION_SCHEMA = "charitygraph.gate4.t3.acnc-real-evidence-retention/v1"
REPRESENTATION_SCHEMA = "charitygraph.gate4.t3.acnc-source-native-representation/v1"
_ACNC_FAMILIES = frozenset({"acnc_register", "acnc_ais_bundle"})
_RIGHTS_AXES = ("private_provider_processing", "public_redistribution")


class RetentionInputError(ValueError):
    """Raised when the supplied durable identity or evidence shape is unsafe."""


def _text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetentionInputError(f"{field_name} must be nonblank text")
    return value.strip()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _typed_id(prefix: str, digest: str) -> str:
    return f"{prefix}{digest}"


def _utc_receipt(value: datetime | str) -> tuple[datetime, str]:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RetentionInputError("acquired_at must be an ISO-8601 datetime") from exc
    else:
        parsed = value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RetentionInputError("acquired_at must be timezone-aware")
    utc = parsed.astimezone(timezone.utc)
    return utc, utc.isoformat(timespec="seconds").replace("+00:00", "Z")


def _record_identity(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get("id") or record.get(f"{field_name}_id")
    return _text(value, f"{field_name}.id")


def _validate_url(value: Any) -> str:
    url = _text(value, "source_url")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RetentionInputError("source_url must be an absolute HTTPS URL")
    return url


def _normalise_authority(
    authority: Mapping[str, Mapping[str, Any]] | None,
    *,
    source_artifact_id: str,
    source_record_id: str,
    representation_artifact_id: str,
    representation_sha256: str,
    scope_id: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return exact authority records and explicit status for every restricted axis."""
    statuses: dict[str, dict[str, Any]] = {
        "private_provider_processing": {
            "status": "blocked",
            "reason": "no real provider authority record supplied",
            "authority_record_id": None,
        },
        "public_redistribution": {
            "status": "not_assessed",
            "reason": "public redistribution is outside this private retention task",
            "authority_record_id": None,
        },
    }
    decisions: dict[str, dict[str, Any]] = {}
    if authority is None:
        return decisions, statuses
    if not isinstance(authority, Mapping):
        raise RetentionInputError("rights_authority must be a mapping by rights axis")
    for axis, raw in authority.items():
        if axis not in _RIGHTS_AXES:
            raise RetentionInputError(f"unsupported rights authority axis: {axis}")
        if not isinstance(raw, Mapping):
            raise RetentionInputError(f"rights authority for {axis} must be a mapping")
        item = dict(raw)
        item["axis"] = axis
        item.setdefault("source_artifact_id", source_artifact_id)
        item.setdefault("source_record_id", source_record_id)
        item.setdefault("representation_artifact_id", representation_artifact_id)
        item.setdefault("representation_sha256", representation_sha256)
        item.setdefault("scope_id", scope_id)
        decision_id = _text(item.get("decision_id"), f"{axis}.decision_id")
        item["decision_id"] = decision_id
        decisions[decision_id] = item
        statuses[axis] = {
            "status": item.get("status", "blocked"),
            "reason": "authority record supplied by caller",
            "authority_record_id": decision_id,
        }
    return decisions, statuses


@dataclass(frozen=True)
class AcncRetentionRecord:
    """One immutable-in-memory retained ACNC source and its derived metadata."""

    subject_id: str
    scope_id: str
    subject: Mapping[str, Any]
    scope: Mapping[str, Any]
    source_family: str
    source_role: str
    source_definition_id: str
    source_record_id: str
    source_artifact_id: str
    source_sha256: str
    representation_artifact_id: str
    representation_sha256: str
    acquisition_receipt_id: str
    evidence_locator_id: str
    source_url: str
    acquired_at_utc: str
    source_bytes: bytes = field(repr=False)
    representation_bytes: bytes = field(repr=False)
    source_record: Mapping[str, Any]
    acquisition_receipt: Mapping[str, Any]
    representation: Mapping[str, Any]
    local_retention_decision: Mapping[str, Any]
    rights_status: Mapping[str, Mapping[str, Any]]
    rights_decisions: Mapping[str, Mapping[str, Any]]

    @property
    def provider_processing_status(self) -> str:
        return str(self.rights_status["private_provider_processing"]["status"])

    @property
    def public_redistribution_status(self) -> str:
        return str(self.rights_status["public_redistribution"]["status"])

    def retained_bytes(self) -> dict[str, bytes]:
        return {
            self.source_artifact_id: self.source_bytes,
            self.representation_artifact_id: self.representation_bytes,
        }

    def binder_row(self, *, ordinal: int = 1) -> dict[str, Any]:
        return {
            "ordinal": ordinal,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "evidence_scope": dict(self.source_record["evidence_scope"]),
            "source_family": self.source_family,
            "source_role": self.source_role,
            "source_definition_id": self.source_definition_id,
            "source_record_id": self.source_record_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "acquisition_receipt_id": self.acquisition_receipt_id,
            "representation_artifact_id": self.representation_artifact_id,
            "representation_sha256": self.representation_sha256,
            "citation_locator": self.source_url,
            "date_or_period": self.acquired_at_utc[:10],
            "observation_kind": "observation",
        }

    def binder_existing(self) -> dict[str, Any]:
        return {
            "subjects": [dict(self.subject)],
            "scopes": [dict(self.scope)],
            "source_definitions": [{
                "id": self.source_definition_id,
                "source_definition_id": self.source_definition_id,
                "source_family": self.source_family,
                "source_role": self.source_role,
            }],
            "source_records": [dict(self.source_record)],
            "acquisition_receipts": [dict(self.acquisition_receipt)],
            "representations": [dict(self.representation)],
            "rights_decisions": [
                dict(self.local_retention_decision),
                *[dict(item) for item in self.rights_decisions.values()],
            ],
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe private retention record, including exact bytes as base64."""
        return {
            "schema": RETENTION_SCHEMA,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_family": self.source_family,
            "source_role": self.source_role,
            "source_definition_id": self.source_definition_id,
            "source_record_id": self.source_record_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "representation_artifact_id": self.representation_artifact_id,
            "representation_sha256": self.representation_sha256,
            "acquisition_receipt_id": self.acquisition_receipt_id,
            "evidence_locator_id": self.evidence_locator_id,
            "source_url": self.source_url,
            "acquired_at_utc": self.acquired_at_utc,
            "source_bytes_base64": base64.b64encode(self.source_bytes).decode("ascii"),
            "representation_bytes_base64": base64.b64encode(self.representation_bytes).decode("ascii"),
            "source_record": dict(self.source_record),
            "acquisition_receipt": dict(self.acquisition_receipt),
            "representation": dict(self.representation),
            "local_retention_decision": dict(self.local_retention_decision),
            "rights_status": {key: dict(value) for key, value in self.rights_status.items()},
            "rights_decisions": {key: dict(value) for key, value in self.rights_decisions.items()},
        }


def retain_acnc_source_evidence(
    *,
    subject_id: str,
    scope_id: str,
    subject: Mapping[str, Any],
    scope: Mapping[str, Any],
    source_family: str,
    source_role: str,
    source_url: str,
    raw_bytes: bytes,
    representation: Mapping[str, Any] | bytes,
    acquired_at: datetime | str,
    source_definition_id: str | None = None,
    source_record_id: str | None = None,
    rights_authority: Mapping[str, Mapping[str, Any]] | None = None,
) -> AcncRetentionRecord:
    """Retain one already-acquired ACNC source for one exact subject and scope.

    No network access, identity discovery, model call or rights inference occurs.
    ``representation`` is either already-materialised bytes or a structured
    value that is canonicalised into a separate representation object.
    """
    subject_id = _text(subject_id, "subject_id")
    scope_id = _text(scope_id, "scope_id")
    if not isinstance(subject, Mapping) or not isinstance(scope, Mapping):
        raise RetentionInputError("subject and scope must be durable record mappings")
    if _record_identity(subject, "subject") != subject_id:
        raise RetentionInputError("subject record does not match the exact subject_id")
    if _record_identity(scope, "scope") != scope_id:
        raise RetentionInputError("scope record does not match the exact scope_id")
    scope_subject_id = scope.get("subject_id")
    if scope_subject_id != subject_id:
        raise RetentionInputError("scope record is bound to a different durable subject")
    source_family = _text(source_family, "source_family")
    if source_family not in _ACNC_FAMILIES:
        raise RetentionInputError("source_family must be acnc_register or acnc_ais_bundle")
    source_role = _text(source_role, "source_role")
    source_url = _validate_url(source_url)
    received_at, acquired_at_utc = _utc_receipt(acquired_at)
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise RetentionInputError("raw_bytes must be non-empty bytes")
    if isinstance(representation, Mapping):
        representation_bytes = canonical_json_bytes({
            "schema": REPRESENTATION_SCHEMA,
            "source_family": source_family,
            "source_role": source_role,
            "source_subject_id": subject_id,
            "source_scope_id": scope_id,
            "value": dict(representation),
        })
        materialisation = "canonical_json_v1"
    elif isinstance(representation, bytes) and representation:
        representation_bytes = representation
        materialisation = "caller_materialised_bytes"
    else:
        raise RetentionInputError("representation must be a non-empty mapping or bytes")
    source_sha256 = _sha256(raw_bytes)
    representation_sha256 = _sha256(representation_bytes)
    if source_sha256 == representation_sha256:
        raise RetentionInputError("source and representation identities must remain distinct")
    source_artifact_id = _typed_id("srcblob:", source_sha256)
    representation_artifact_id = _typed_id("artifact:", representation_sha256)
    source_definition_id = source_definition_id or _typed_id(
        "srcdef:", _sha256(canonical_json_bytes({"family": source_family, "role": source_role}))
    )
    source_definition_id = _text(source_definition_id, "source_definition_id")
    source_record_identity = {
        "subject_id": subject_id,
        "scope_id": scope_id,
        "source_family": source_family,
        "source_role": source_role,
        "source_artifact_id": source_artifact_id,
        "source_url": source_url,
    }
    source_record_id = source_record_id or _typed_id(
        "srcrec:", _sha256(canonical_json_bytes(source_record_identity))
    )
    source_record_id = _text(source_record_id, "source_record_id")
    evidence_locator_id = _typed_id(
        "locator:", _sha256(canonical_json_bytes({"source_record_id": source_record_id, "url": source_url}))
    )
    acquisition_receipt_id = _typed_id(
        "acq:", _sha256(canonical_json_bytes({
            "source_definition_id": source_definition_id,
            "source_artifact_id": source_artifact_id,
            "source_sha256": source_sha256,
            "source_url": source_url,
            "acquired_at_utc": acquired_at_utc,
        }))
    )
    evidence_scope = {"scope_id": scope_id, "scope_kind": scope.get("scope_kind", "organisation"), "subject_id": subject_id}
    source_record = {
        "id": source_record_id,
        "source_record_id": source_record_id,
        "source_family": source_family,
        "source_role": source_role,
        "about_subject_ids": [subject_id],
        "subject_id": subject_id,
        "payload_ref": source_artifact_id,
        "payload_hash": source_sha256,
        "source_locator": source_url,
        "evidence_scope": evidence_scope,
        "acquired_at": acquired_at_utc,
        "provenance": {
            "source_url": source_url,
            "acquisition_receipt_id": acquisition_receipt_id,
            "source_artifact_id": source_artifact_id,
            "source_sha256": source_sha256,
        },
    }
    acquisition_receipt = {
        "id": acquisition_receipt_id,
        "acquisition_receipt_id": acquisition_receipt_id,
        "source_definition_id": source_definition_id,
        "artifact_id": source_artifact_id,
        "content_hash": source_sha256,
        "source_url": source_url,
        "received_at_utc": acquired_at_utc,
        "outcome": "available",
        "method": "caller_supplied_official_acnc_bytes",
    }
    representation_record = {
        "id": representation_artifact_id,
        "artifact_id": representation_artifact_id,
        "content_hash": representation_sha256,
        "source_artifact_id": source_artifact_id,
        "source_record_id": source_record_id,
        "subject_id": subject_id,
        "scope_id": scope_id,
        "representation_class": "structured_factual",
        "materialisation": materialisation,
        "evidence_locator_ids": [evidence_locator_id],
        "citation_locator": source_url,
        "date_or_period": acquired_at_utc[:10],
    }
    local_retention_decision = {
        "id": f"rights:local:{representation_sha256}",
        "axis": "local_retention",
        "decision_id": f"rights:local:{representation_sha256}",
        "source_artifact_id": source_artifact_id,
        "source_record_id": source_record_id,
        "representation_artifact_id": representation_artifact_id,
        "representation_sha256": representation_sha256,
        "scope_id": scope_id,
        "decision_version": "1",
        "status": "authorized",
        "assessed_on": acquired_at_utc[:10],
        "review_deadline": (received_at.date() + timedelta(days=365)).isoformat(),
        "lawful_public_access": True,
        "circumvention_used": False,
        "explicit_prohibition_found": False,
        "authority_kind": "governed_policy",
        "policy_id": LOCAL_RETENTION_POLICY_ID,
        "policy_version": LOCAL_RETENTION_POLICY_VERSION,
    }
    rights_decisions, rights_status = _normalise_authority(
        rights_authority,
        source_artifact_id=source_artifact_id,
        source_record_id=source_record_id,
        representation_artifact_id=representation_artifact_id,
        representation_sha256=representation_sha256,
        scope_id=scope_id,
    )
    return AcncRetentionRecord(
        subject_id=subject_id,
        scope_id=scope_id,
        subject=dict(subject),
        scope=dict(scope),
        source_family=source_family,
        source_role=source_role,
        source_definition_id=source_definition_id,
        source_record_id=source_record_id,
        source_artifact_id=source_artifact_id,
        source_sha256=source_sha256,
        representation_artifact_id=representation_artifact_id,
        representation_sha256=representation_sha256,
        acquisition_receipt_id=acquisition_receipt_id,
        evidence_locator_id=evidence_locator_id,
        source_url=source_url,
        acquired_at_utc=acquired_at_utc,
        source_bytes=raw_bytes,
        representation_bytes=representation_bytes,
        source_record=source_record,
        acquisition_receipt=acquisition_receipt,
        representation=representation_record,
        local_retention_decision=local_retention_decision,
        rights_status=rights_status,
        rights_decisions={axis: item for item in _RIGHTS_AXES for item in [rights_decisions.get(next((key for key, value in rights_decisions.items() if value.get("axis") == axis), ""))] if item is not None},
    )


def bind_retained_acnc_source_evidence(
    retained: AcncRetentionRecord,
    *,
    existing: Mapping[str, Any] | None = None,
    retained_bytes: Mapping[str, bytes] | Callable[[str], bytes] | None = None,
    ordinal: int = 1,
    as_of: date = date(2026, 11, 1),
) -> SourceEvidenceBindingResult:
    """Call the existing T3 binder using this module's retained material."""
    catalogue = retained.binder_existing()
    if existing is not None:
        catalogue.update({key: value for key, value in existing.items()})
    return bind_acnc_source_evidence(
        [retained.binder_row(ordinal=ordinal)],
        existing=catalogue,
        retained_bytes=retained.retained_bytes() if retained_bytes is None else retained_bytes,
        as_of=as_of,
    )


bind_t3_acnc_real_evidence = bind_retained_acnc_source_evidence


__all__ = [
    "AcncRetentionRecord",
    "RETENTION_SCHEMA",
    "REPRESENTATION_SCHEMA",
    "RetentionInputError",
    "bind_retained_acnc_source_evidence",
    "bind_t3_acnc_real_evidence",
    "retain_acnc_source_evidence",
]
