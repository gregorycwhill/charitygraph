"""Clean Phase 5 preflight over authoritative governed-rights records.

This is a provider-free bridge.  Rights record bytes in the private
content-addressed store are authoritative; the v29 SQLite tables are only a
verified current-state lookup.  The bridge creates no catalogue rows and
delegates positive lowering to the existing governed-reference preflight.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable, Literal

from pydantic import Field, field_validator

from .contracts.canonical import canonical_json_bytes
from .contracts.common import Sha256, StrictModel, require_nonblank
from .phase5_factory import FactoryPlan
from .phase5_governed_factory_integration import (
    GovernedReference,
    PreflightDiagnostic,
    preflight_governed_references,
)
from .runtime.rights_governance_projection import (
    RightsGovernanceProjection,
    RightsProjectionError,
)
from .runtime.rights_governance_record import (
    INTERNAL_PRIVATE_USE_POLICY,
    INTERNAL_PRIVATE_USE_POLICY_ID,
    RightsGovernanceRecord,
    RightsGovernanceStore,
    RightsStorageError,
)


RightsPreflightState = Literal[
    "available", "missing", "blocked", "structurally_invalid", "unrecoverable",
    "mismatched", "not_applicable", "not_processed", "retrieval_failed",
]


class RightsPreflightReference(StrictModel):
    """Task metadata plus an exact authority record identity.

    Subject, scope, source record, representation and acquisition lineage are
    intentionally derived from the authority record rather than copied into
    this request model.
    """

    reference_id: str
    rights_record_id: Sha256
    source_family: str
    source_definition_id: str
    evidence_locator_ids: tuple[str, ...] = ()
    claim_family_id: str
    task_profile: str
    task_profile_version: str = "1"
    schema_version: str = "1"
    difficulty: Literal[
        "deterministic", "lower_cost_constrained_semantic",
        "stronger_semantic_judgement", "human_risk_review",
    ] = "deterministic"
    physical_bundle_opportunity: str | None = None

    @field_validator(
        "reference_id", "source_family", "source_definition_id", "claim_family_id",
        "task_profile", "task_profile_version", "schema_version",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("physical_bundle_opportunity")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids")
    @classmethod
    def _unique_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(not item.strip() for item in value):
            raise ValueError("evidence locator IDs must be nonblank and unique")
        return value


@dataclass(frozen=True)
class GovernedRightsFactoryPreflight:
    tasks: tuple[dict[str, Any], ...]
    diagnostics: tuple[PreflightDiagnostic, ...]

    @property
    def factory_plan(self) -> FactoryPlan:
        return FactoryPlan.from_manifest(list(self.tasks))

    @property
    def accepted_count(self) -> int:
        return len(self.tasks)


def _diagnostic(
    reference: RightsPreflightReference,
    state: RightsPreflightState,
    reason: str,
    *details: str,
    subject_id: str = "unresolved",
) -> PreflightDiagnostic:
    return PreflightDiagnostic(
        reference_id=reference.reference_id,
        subject_id=subject_id,
        state=state,
        reason=reason,
        details=tuple(details),
    )


def _lineage_hash(record: RightsGovernanceRecord) -> str:
    return hashlib.sha256(canonical_json_bytes(record.acquisition_lineage_ids)).hexdigest()


def _binding_hash(record: RightsGovernanceRecord) -> str:
    return hashlib.sha256(
        canonical_json_bytes({"binding": record.binding_key, "scope": record.scope})
    ).hexdigest()


def _projection_matches(record: RightsGovernanceRecord, row: dict[str, Any]) -> bool:
    expected = {
        "record_id": record.content_hash,
        "subject_id": record.subject_id,
        "scope": record.scope,
        "source_artifact_id": record.source_artifact_id,
        "source_record_id": record.source_record_id,
        "source_role": record.source_role,
        "representation_artifact_id": record.representation_artifact_id,
        "representation_sha256": str(record.representation_sha256),
        "acquisition_lineage_hash": _lineage_hash(record),
        "binding_hash": _binding_hash(record),
        "rights_policy_id": record.rights_policy_id,
        "rights_policy_version": record.rights_policy_version,
        "provider_processing_policy_id": record.provider_processing_policy_id,
        "provider_processing_policy_version": record.provider_processing_policy_version,
        "status": record.status,
        "review_status": record.review_status,
        "expires_on": record.expires_on.isoformat() if record.expires_on else None,
        "supersedes_record_id": record.supersedes_record_id,
        "revokes_record_id": record.revokes_record_id,
        "local_retention_status": record.local_retention.status,
        "provider_transmission_status": record.provider_transmission.status,
        "public_redistribution_status": record.public_redistribution.status,
        "actor_kind": record.actor_kind,
        "actor_id": record.actor_id,
        "recorded_at": record.recorded_at.isoformat(),
    }
    return all(row.get(key) == value for key, value in expected.items())


def _validate_authority(
    reference: RightsPreflightReference,
    *,
    store: RightsGovernanceStore,
    projection: RightsGovernanceProjection,
    catalog: Any,
    as_of: date,
    retained_bytes: Callable[[str], bytes] | None,
) -> tuple[PreflightDiagnostic | None, tuple[RightsGovernanceRecord, GovernedReference] | None]:
    try:
        record = store.load_record(reference.rights_record_id)
        if record.content_hash != reference.rights_record_id:
            return _diagnostic(reference, "mismatched", "rights record content address does not match request"), None
        current = projection.current_record(
            record_id=record.content_hash,
            subject_id=record.subject_id,
            scope=record.scope,
            as_of=as_of,
        )
    except (RightsStorageError, RightsProjectionError, ValueError) as exc:
        return _diagnostic(reference, "blocked", "authoritative rights material is unavailable or corrupt", str(exc)), None

    if current is None:
        return _diagnostic(
            reference, "blocked", "rights record is not the v29 current record",
            record.content_hash, subject_id=record.subject_id,
        ), None
    if not _projection_matches(record, current):
        return _diagnostic(
            reference, "mismatched", "v29 current row does not match authoritative rights record",
            record.content_hash, subject_id=record.subject_id,
        ), None
    if not record.can_promote(as_of=as_of):
        return _diagnostic(
            reference, "blocked", "rights record is expired, revoked, superseded, or not current",
            record.content_hash, subject_id=record.subject_id,
        ), None
    if record.rights_policy_id == INTERNAL_PRIVATE_USE_POLICY_ID:
        if reference.source_family not in INTERNAL_PRIVATE_USE_POLICY.source_families:
            return _diagnostic(
                reference,
                "mismatched",
                "internal-private-use policy does not cover the source family",
                reference.source_family,
                subject_id=record.subject_id,
            ), None
    if record.local_retention.status != "authorized" or record.local_retention.decision_id is None:
        return _diagnostic(
            reference, "blocked", "local retention authority is not authorized for the representation",
            record.content_hash, subject_id=record.subject_id,
        ), None
    if not reference.evidence_locator_ids:
        return _diagnostic(
            reference, "structurally_invalid", "governed rights preflight requires evidence locators",
            subject_id=record.subject_id,
        ), None
    if catalog.get_source_definition(reference.source_definition_id) is None:
        return _diagnostic(
            reference, "missing", "source definition reference is not durable",
            reference.source_definition_id, subject_id=record.subject_id,
        ), None
    scope = catalog.get_scope(record.scope)
    if scope is None:
        return _diagnostic(reference, "missing", "rights scope is not durable", record.scope, subject_id=record.subject_id), None
    if scope.get("subject_id") != record.subject_id:
        return _diagnostic(reference, "mismatched", "rights scope belongs to a different subject", record.scope, subject_id=record.subject_id), None

    source = catalog.get_source_record(record.source_record_id)
    if source is None:
        return _diagnostic(reference, "missing", "rights source record is not durable", record.source_record_id, subject_id=record.subject_id), None
    if (
        source.get("source_family") != reference.source_family
        or source.get("source_locator") != record.source_origin_url
        or source.get("source_role") != record.source_role
        or record.subject_id not in set((source.get("material") or {}).get("about_subject_ids") or ())
        or source.get("payload_ref") != record.source_artifact_id
    ):
        return _diagnostic(reference, "mismatched", "rights source identity, origin, role, or subject binding does not match", record.source_record_id, subject_id=record.subject_id), None

    source_artifact = catalog.get_artifact(record.source_artifact_id)
    if source_artifact is None or source_artifact.get("availability") != "available":
        return _diagnostic(reference, "missing", "rights source artifact is not durably available", record.source_artifact_id, subject_id=record.subject_id), None
    if source.get("payload_hash") != source_artifact.get("content_hash"):
        return _diagnostic(reference, "mismatched", "rights source artifact hash does not match source record", record.source_artifact_id, subject_id=record.subject_id), None

    for acquisition_id in record.acquisition_lineage_ids:
        receipt = catalog.get_acquisition_receipt(acquisition_id)
        if receipt is None:
            return _diagnostic(reference, "missing", "rights acquisition lineage is not durable", acquisition_id, subject_id=record.subject_id), None
        if (
            receipt.get("source_definition_id") != reference.source_definition_id
            or receipt.get("artifact_id") != record.source_artifact_id
            or receipt.get("content_hash") != source_artifact.get("content_hash")
            or receipt.get("outcome") not in {"available", "partial"}
        ):
            return _diagnostic(reference, "mismatched", "rights acquisition lineage is not exact", acquisition_id, subject_id=record.subject_id), None

    representation_id = record.representation_artifact_id
    if representation_id is None:
        return _diagnostic(reference, "structurally_invalid", "rights record has no exact representation artifact", subject_id=record.subject_id), None
    representation = catalog.get_artifact(representation_id)
    if representation is None or representation.get("availability") != "available":
        return _diagnostic(reference, "missing", "rights representation artifact is not durably available", representation_id, subject_id=record.subject_id), None
    if representation.get("content_hash") != str(record.representation_sha256):
        return _diagnostic(reference, "mismatched", "rights representation hash does not match durable artifact", representation_id, subject_id=record.subject_id), None
    if retained_bytes is not None:
        try:
            retained = retained_bytes(representation_id)
        except (FileNotFoundError, OSError, ValueError):
            return _diagnostic(reference, "unrecoverable", "rights representation bytes cannot be read", representation_id, subject_id=record.subject_id), None
        if hashlib.sha256(retained).hexdigest() != str(record.representation_sha256):
            return _diagnostic(reference, "mismatched", "rights representation bytes do not match authority", representation_id, subject_id=record.subject_id), None
    if not any(
        item.get("input_artifact_id") == record.source_artifact_id
        for item in catalog.get_artifact_lineage(representation_id)
    ):
        return _diagnostic(reference, "mismatched", "rights representation lineage does not point to source artifact", representation_id, subject_id=record.subject_id), None

    governed = GovernedReference(
        reference_id=reference.reference_id,
        subject_id=record.subject_id,
        scope_id=record.scope,
        source_family=reference.source_family,
        source_definition_id=reference.source_definition_id,
        acquisition_receipt_ids=record.acquisition_lineage_ids,
        source_record_ids=(record.source_record_id,),
        evidence_locator_ids=reference.evidence_locator_ids,
        representation_artifact_ids=(representation_id,),
        representation_hashes={representation_id: str(record.representation_sha256)},
        rights_policy_id=record.rights_policy_id,
        rights_role=record.source_role,
        claim_family_id=reference.claim_family_id,
        task_profile=reference.task_profile,
        task_profile_version=reference.task_profile_version,
        schema_version=reference.schema_version,
        difficulty=reference.difficulty,
        physical_bundle_opportunity=reference.physical_bundle_opportunity,
    )
    return None, (record, governed)


def preflight_governed_rights(
    references: Iterable[RightsPreflightReference | dict[str, Any]],
    *,
    store: RightsGovernanceStore,
    projection: RightsGovernanceProjection,
    catalog: Any,
    as_of: date,
    retained_bytes: Callable[[str], bytes] | None = None,
    build_id: str = "phase5-governed-rights-preflight-v1",
    route_policy_version: str = "phase5-governed-rights-route-v1",
) -> GovernedRightsFactoryPreflight:
    """Validate private rights authority, then invoke clean Factory preflight."""

    tasks: list[dict[str, Any]] = []
    diagnostics: list[PreflightDiagnostic] = []
    seen: set[str] = set()
    for raw in references:
        try:
            reference = raw if isinstance(raw, RightsPreflightReference) else RightsPreflightReference.model_validate(raw)
        except Exception as exc:
            raw_id = str(raw.get("reference_id", "unresolved")) if isinstance(raw, dict) else "unresolved"
            diagnostics.append(PreflightDiagnostic(
                reference_id=raw_id,
                subject_id="unresolved",
                state="structurally_invalid",
                reason="rights preflight request is structurally invalid",
                details=(str(exc),),
            ))
            continue
        if reference.reference_id in seen:
            diagnostics.append(_diagnostic(reference, "structurally_invalid", "reference identity is duplicated"))
            continue
        seen.add(reference.reference_id)
        diagnostic, material = _validate_authority(
            reference,
            store=store,
            projection=projection,
            catalog=catalog,
            as_of=as_of,
            retained_bytes=retained_bytes,
        )
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        assert material is not None
        _record, governed = material
        result = preflight_governed_references(
            (governed,),
            catalog=catalog,
            retained_bytes=retained_bytes,
            build_id=build_id,
            route_policy_version=route_policy_version,
        )
        tasks.extend(result.tasks)
        diagnostics.extend(result.diagnostics)
    return GovernedRightsFactoryPreflight(tasks=tuple(tasks), diagnostics=tuple(diagnostics))


__all__ = [
    "GovernedRightsFactoryPreflight", "RightsPreflightReference",
    "RightsPreflightState", "preflight_governed_rights",
]
