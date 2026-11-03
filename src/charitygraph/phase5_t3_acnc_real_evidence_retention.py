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
import json
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
PUBLICDATA_TRANSPORT_SCHEMA = "charitygraph.private-source-transport/v1"
PUBLICDATA_REGISTER_SOURCE_KIND = "independent_publicdata_au_api_representation_of_acnc_register"
PUBLICDATA_REGISTER_BODY_SHA256 = "07b83ca8f241b23445818c2079883924929ecc5c72dd0aed04b10c3f8b5372fc"
PUBLICDATA_REGISTER_BODY_BYTES = 4086
PUBLICDATA_REGISTER_VERSION = "2026-10-26"
PUBLICDATA_REGISTER_URL = "https://publicdata.au/api/v1/datasets/acnc-register/versions/2026-10-26/rows?abn=eq.52000399744"
PUBLICDATA_REGISTER_BATCH_TRANSPORT_SCHEMA = "charitygraph.g4-acnc-register-source-transport/v1"
PUBLICDATA_REGISTER_BATCH_UPSTREAM_SHA256 = "1ff76b510e8155d7ab35df4b45b8791315c1f0a15f43f9c3057dff16646f816d"
PUBLICDATA_REGISTER_BATCH_EXPECTATIONS = {
    "26164251245": (4173, "3ad023beed624de3ca5f1ed17f29b01a64141b70e3166eb6c6df99e7ebf1e357"),
    "52404606134": (4085, "7ae05d8b38a106663a28c4a70c1c573828519f5d9d64742da7c362f1d830cd93"),
    "33107782196": (4028, "d80552005dcafc554f978e1d863db141d6c9f3aa15c7f5bcc9d276668a741425"),
    "82147006639": (4219, "48750195040c4e829f82d9f0f7bb7584e9732d615d8fe343dfe9efffaab4b8f8"),
}
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


def _json_safe_metadata(value: Any, field_name: str) -> Any:
    """Reject private bytes from persisted provenance metadata."""
    if isinstance(value, bytes):
        raise RetentionInputError(f"{field_name} cannot contain raw bytes")
    if isinstance(value, Mapping):
        return {str(key): _json_safe_metadata(item, f"{field_name}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_metadata(item, f"{field_name}[]") for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise RetentionInputError(f"{field_name} contains unsupported metadata")


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
    source_provenance: Mapping[str, Any] | None = None,
    acquisition_method: str = "caller_supplied_official_acnc_bytes",
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
    acquisition_method = _text(acquisition_method, "acquisition_method")
    safe_source_provenance = {} if source_provenance is None else _json_safe_metadata(source_provenance, "source_provenance")
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
            **safe_source_provenance,
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
        "method": acquisition_method,
        "source_provenance": safe_source_provenance,
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
        "source_provenance": safe_source_provenance,
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
        rights_decisions={axis: item for axis in _RIGHTS_AXES for item in [rights_decisions.get(next((key for key, value in rights_decisions.items() if value.get("axis") == axis), ""))] if item is not None},
    )


def retain_publicdata_acnc_register_transport(
    transport: Mapping[str, Any],
    *,
    subject_id: str,
    scope_id: str,
    subject: Mapping[str, Any],
    scope: Mapping[str, Any],
    source_definition_id: str | None = None,
    source_record_id: str | None = None,
    rights_authority: Mapping[str, Mapping[str, Any]] | None = None,
) -> AcncRetentionRecord:
    """Validate and retain one supplied publicdata.au ACNC API transport.

    This is a bounded equivalent-register adapter.  It consumes a transport
    envelope already present on local disk; it never fetches the API and never
    relabels the third-party representation as ACNC publisher bytes.
    """
    if not isinstance(transport, Mapping):
        raise RetentionInputError("transport must be a mapping")
    if transport.get("schema") != PUBLICDATA_TRANSPORT_SCHEMA:
        raise RetentionInputError("unsupported private source transport schema")
    if transport.get("source_kind") != PUBLICDATA_REGISTER_SOURCE_KIND:
        raise RetentionInputError("transport is not the admitted publicdata.au ACNC register representation")
    if transport.get("subject_abn") != "52000399744":
        raise RetentionInputError("transport subject ABN does not match the bounded target")
    if transport.get("subject_name") != "Guide Dogs NSW/ACT":
        raise RetentionInputError("transport subject name does not match the bounded target")
    if transport.get("source_row_count") != 1:
        raise RetentionInputError("transport must contain exactly one source row")
    if transport.get("upstream_dataset_version") != PUBLICDATA_REGISTER_VERSION:
        raise RetentionInputError("transport dataset version is not the admitted 2026-10-26 version")
    if transport.get("source_url") != PUBLICDATA_REGISTER_URL:
        raise RetentionInputError("transport API locator does not match the admitted versioned query")
    rights = transport.get("rights")
    if rights != {
        "id": "CC-BY-3.0-AU",
        "title": "CC BY 3.0 AU",
        "url": "https://creativecommons.org/licenses/by/3.0/au/",
    }:
        raise RetentionInputError("transport rights are not the supplied CC-BY-3.0-AU record")
    body_text = transport.get("http_body_utf8")
    if not isinstance(body_text, str):
        raise RetentionInputError("transport http_body_utf8 must be text")
    raw_bytes = body_text.encode("utf-8")
    declared_hash = transport.get("http_body_sha256")
    if declared_hash != PUBLICDATA_REGISTER_BODY_SHA256 or _sha256(raw_bytes) != declared_hash:
        raise RetentionInputError("transport HTTP body SHA-256 does not match the admitted response")
    if len(raw_bytes) != PUBLICDATA_REGISTER_BODY_BYTES:
        raise RetentionInputError("transport HTTP body byte size does not match the admitted response")
    try:
        body = json.loads(body_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RetentionInputError("transport HTTP body is not valid JSON") from exc
    if not isinstance(body, Mapping) or not isinstance(body.get("rows"), list) or len(body["rows"]) != 1:
        raise RetentionInputError("transport HTTP body must contain exactly one row")
    row = body["rows"][0]
    if not isinstance(row, Mapping) or row.get("abn") != transport["subject_abn"] or row.get("charity_legal_name") != transport["subject_name"]:
        raise RetentionInputError("transport row identity does not match the bounded subject")
    publicdata = body.get("publicdata")
    if not isinstance(publicdata, Mapping) or publicdata.get("version") != PUBLICDATA_REGISTER_VERSION:
        raise RetentionInputError("transport body does not carry the admitted publicdata version")
    if body.get("this_version") != PUBLICDATA_REGISTER_URL:
        raise RetentionInputError("transport body query locator does not match the transport envelope")
    upstream_claim = transport.get("upstream_original_csv_claimed_sha256")
    upstream = publicdata.get("source")
    if not isinstance(upstream, Mapping) or upstream.get("sha256") != upstream_claim:
        raise RetentionInputError("upstream CSV SHA claim is not preserved consistently")
    if not isinstance(subject, Mapping):
        raise RetentionInputError("subject must be a durable record mapping")
    external_identifiers = subject.get("external_identifiers", ())
    identifier_values = {
        item.get("value") for item in external_identifiers
        if isinstance(item, Mapping) and item.get("scheme") == "ABN"
    }
    if subject.get("abn") != transport["subject_abn"] and transport["subject_abn"] not in identifier_values:
        raise RetentionInputError("durable subject does not carry the exact target ABN")

    representation = {
        "representation_kind": "third_party_api_register_row",
        "representation_origin": "publicdata.au independent republication; not ACNC publisher original bytes",
        "publisher": publicdata.get("publisher"),
        "republisher": publicdata.get("operator"),
        "dataset": publicdata.get("dataset"),
        "dataset_version": PUBLICDATA_REGISTER_VERSION,
        "api_locator": transport["source_url"],
        "api_response_sha256": declared_hash,
        "license": dict(rights),
        "row": dict(row),
        "upstream_original_csv_claim": {
            "sha256": upstream_claim,
            "bytes": transport.get("upstream_original_csv_claimed_bytes"),
            "verification_status": "mirror_claim_not_locally_verified",
        },
    }
    source_provenance = {
        "transport_schema": PUBLICDATA_TRANSPORT_SCHEMA,
        "source_kind": PUBLICDATA_REGISTER_SOURCE_KIND,
        "transport_capture_method": transport.get("capture_method"),
        "transport_captured_at": transport.get("captured_at"),
        "rights": dict(rights),
        "publisher_original_bytes": False,
        "upstream_original_csv_sha256_claim": upstream_claim,
        "upstream_original_csv_verification": "mirror_claim_not_locally_verified",
        "currentness": {
            "source_version": PUBLICDATA_REGISTER_VERSION,
            "source_version_url": body.get("version_page"),
            "captured_at": transport.get("captured_at"),
            "status": "versioned_source_currentness_observed",
        },
    }
    return retain_acnc_source_evidence(
        subject_id=subject_id,
        scope_id=scope_id,
        subject=subject,
        scope=scope,
        source_family="acnc_register",
        source_role="register_identity",
        source_url=transport["source_url"],
        raw_bytes=raw_bytes,
        representation=representation,
        acquired_at=transport["captured_at"],
        source_definition_id=source_definition_id,
        source_record_id=source_record_id,
        rights_authority=rights_authority,
        source_provenance=source_provenance,
        acquisition_method="caller_supplied_publicdata_api_transport",
    )


def retain_publicdata_acnc_register_batch_entry(
    transport: Mapping[str, Any],
    entry: Mapping[str, Any],
    *,
    subject_id: str,
    scope_id: str,
    subject: Mapping[str, Any],
    scope: Mapping[str, Any],
    source_definition_id: str | None = None,
    source_record_id: str | None = None,
    rights_authority: Mapping[str, Mapping[str, Any]] | None = None,
) -> AcncRetentionRecord:
    """Retain one exact entry from the four-row publicdata.au batch transport.

    The batch contains third-party API response bodies, never publisher-original
    CSV bytes.  This adapter verifies the envelope, independently hashes the
    selected UTF-8 body, and then delegates all identity/lineage/rights handling
    to the existing T3 retention seam.
    """
    if not isinstance(transport, Mapping) or transport.get("schema") != PUBLICDATA_REGISTER_BATCH_TRANSPORT_SCHEMA:
        raise RetentionInputError("unsupported publicdata.au batch transport schema")
    if transport.get("source_dataset") != "acnc-register" or transport.get("source_version") != PUBLICDATA_REGISTER_VERSION:
        raise RetentionInputError("batch transport dataset/version is not the admitted ACNC register")
    if transport.get("source_family") != "acnc_register":
        raise RetentionInputError("batch transport source family is not acnc_register")
    if transport.get("upstream_original_csv_sha256") != PUBLICDATA_REGISTER_BATCH_UPSTREAM_SHA256:
        raise RetentionInputError("batch transport upstream CSV claim is not preserved")
    if transport.get("upstream_original_csv_sha256_status") != "mirror_claim_not_locally_verified":
        raise RetentionInputError("batch transport upstream CSV claim is not explicitly unverified")
    if not isinstance(entry, Mapping):
        raise RetentionInputError("batch transport entry must be a mapping")
    abn = entry.get("abn")
    expected = PUBLICDATA_REGISTER_BATCH_EXPECTATIONS.get(abn)
    if expected is None:
        raise RetentionInputError("batch transport entry ABN is not one of the four admitted rows")
    body_text = entry.get("response_raw_utf8")
    if not isinstance(body_text, str):
        raise RetentionInputError("batch transport response must be raw UTF-8 text")
    raw_bytes = body_text.encode("utf-8")
    expected_bytes, expected_sha256 = expected
    if len(raw_bytes) != expected_bytes or _sha256(raw_bytes) != expected_sha256:
        raise RetentionInputError("batch transport response length or independently observed SHA-256 mismatches")
    if entry.get("response_body_chars") != len(body_text) or entry.get("rows") != 1:
        raise RetentionInputError("batch transport response metadata is inconsistent")
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise RetentionInputError("batch transport response is not valid JSON") from exc
    if not isinstance(body, Mapping) or not isinstance(body.get("rows"), list) or len(body["rows"]) != 1:
        raise RetentionInputError("batch transport response must contain one row")
    row = body["rows"][0]
    publicdata = body.get("publicdata")
    if not isinstance(row, Mapping) or row.get("abn") != abn:
        raise RetentionInputError("batch transport row ABN does not match entry")
    if not isinstance(publicdata, Mapping) or publicdata.get("version") != PUBLICDATA_REGISTER_VERSION or publicdata.get("fields") != 69:
        raise RetentionInputError("batch transport response is not the admitted 69-field register version")
    if body.get("this_version") != entry.get("api_url"):
        raise RetentionInputError("batch transport query URL does not match response lineage")
    if publicdata.get("source", {}).get("sha256") != PUBLICDATA_REGISTER_BATCH_UPSTREAM_SHA256:
        raise RetentionInputError("batch response does not preserve the unverified upstream CSV claim")
    licence = publicdata.get("licence")
    if licence != {"id": "CC-BY-3.0-AU", "title": "CC BY 3.0 AU", "url": "https://creativecommons.org/licenses/by/3.0/au/"}:
        raise RetentionInputError("batch response does not carry the admitted CC BY 3.0 AU record")
    publisher = publicdata.get("publisher")
    operator = publicdata.get("operator")
    if not isinstance(publisher, Mapping) or publisher.get("name") != "Australian Charities and Not-for-profits Commission":
        raise RetentionInputError("batch response ACNC attribution is missing")
    if not isinstance(operator, Mapping) or operator.get("name") != "National Digital":
        raise RetentionInputError("batch response National Digital attribution is missing")
    external_identifiers = subject.get("external_identifiers", ()) if isinstance(subject, Mapping) else ()
    identifier_values = {item.get("value") for item in external_identifiers if isinstance(item, Mapping) and item.get("scheme") == "ABN"}
    if subject.get("abn") != abn and abn not in identifier_values:
        raise RetentionInputError("durable subject does not carry the exact batch-entry ABN")
    representation = {
        "representation_kind": "third_party_api_register_row",
        "representation_origin": "publicdata.au independent republication; not ACNC publisher original bytes",
        "publisher": dict(publisher),
        "republisher": dict(operator),
        "dataset": publicdata.get("dataset"),
        "dataset_version": PUBLICDATA_REGISTER_VERSION,
        "api_locator": entry.get("api_url"),
        "api_response_sha256": expected_sha256,
        "response_fields": publicdata.get("fields"),
        "license": dict(licence),
        "row": dict(row),
        "upstream_original_csv_claim": {
            "sha256": PUBLICDATA_REGISTER_BATCH_UPSTREAM_SHA256,
            "verification_status": "mirror_claim_not_locally_verified",
        },
    }
    source_provenance = {
        "transport_schema": PUBLICDATA_REGISTER_BATCH_TRANSPORT_SCHEMA,
        "source_kind": PUBLICDATA_REGISTER_SOURCE_KIND,
        "transport_capture_method": transport.get("acquisition_channel"),
        "transport_captured_at": transport.get("acquisition_observed_at"),
        "observed_mirror_origin": "publicdata.au",
        "source_version": PUBLICDATA_REGISTER_VERSION,
        "response_fields": 69,
        "attribution": transport.get("rights_observed"),
        "rights": dict(licence),
        "publisher_original_bytes": False,
        "upstream_original_csv_sha256_claim": PUBLICDATA_REGISTER_BATCH_UPSTREAM_SHA256,
        "upstream_original_csv_verification": "mirror_claim_not_locally_verified",
        "currentness": {
            "source_version": PUBLICDATA_REGISTER_VERSION,
            "source_version_url": body.get("version_page"),
            "captured_at": transport.get("acquisition_observed_at"),
            "status": "versioned_source_currentness_observed",
        },
    }
    return retain_acnc_source_evidence(
        subject_id=subject_id,
        scope_id=scope_id,
        subject=subject,
        scope=scope,
        source_family="acnc_register",
        source_role="register_identity",
        source_url=entry.get("api_url"),
        raw_bytes=raw_bytes,
        representation=representation,
        acquired_at=transport.get("acquisition_observed_at"),
        source_definition_id=source_definition_id,
        source_record_id=source_record_id,
        rights_authority=rights_authority,
        source_provenance=source_provenance,
        acquisition_method="caller_supplied_publicdata_batch_transport",
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
    "PUBLICDATA_REGISTER_BODY_BYTES",
    "PUBLICDATA_REGISTER_BODY_SHA256",
    "PUBLICDATA_REGISTER_BATCH_EXPECTATIONS",
    "PUBLICDATA_REGISTER_BATCH_TRANSPORT_SCHEMA",
    "PUBLICDATA_REGISTER_BATCH_UPSTREAM_SHA256",
    "PUBLICDATA_REGISTER_SOURCE_KIND",
    "PUBLICDATA_REGISTER_URL",
    "PUBLICDATA_REGISTER_VERSION",
    "PUBLICDATA_TRANSPORT_SCHEMA",
    "RETENTION_SCHEMA",
    "REPRESENTATION_SCHEMA",
    "RetentionInputError",
    "bind_retained_acnc_source_evidence",
    "bind_t3_acnc_real_evidence",
    "retain_acnc_source_evidence",
    "retain_publicdata_acnc_register_transport",
    "retain_publicdata_acnc_register_batch_entry",
]
