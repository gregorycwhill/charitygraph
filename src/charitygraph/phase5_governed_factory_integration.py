"""Provider-free handoff from governed material references to the Phase 5 Factory.

This adapter consumes only already-persisted identifiers.  It validates exact
catalogue relationships and content hashes, creates no source material, and
does not interpret evidence.  Non-ready references produce diagnostics and are
never lowered into positive work.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Literal

from pydantic import Field, field_validator, model_validator

from .contracts import EvidenceInput, ModelTask, ProducerRef, SchemaRef, VersionedPolicy
from .contracts.canonical import canonical_sha256
from .contracts.ids import deterministic_id
from .contracts.common import require_nonblank
from .contracts.tasks import model_task_cache_key
from .phase5_factory import FactoryPlan
from .phase5_preflight import PlannedLogicalTask, StrictPlanModel


GovernedMaterialState = Literal[
    "available", "missing", "blocked", "structurally_invalid", "unrecoverable",
    "mismatched", "not_applicable", "not_processed", "retrieval_failed",
]

_NO_TASK_STATES = {
    "missing", "blocked", "structurally_invalid", "unrecoverable", "mismatched",
    "not_applicable", "not_processed", "retrieval_failed",
}
_AVAILABLE_OUTCOMES = {"available", "partial"}
_INPUT_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:phase5-governed-reference-input:1",
    schema_version="1",
)
_OUTPUT_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:phase5-governed-reference-output:1",
    schema_version="1",
)
_TASK_CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class GovernedReference(StrictPlanModel):
    """A reference to material that another governed path has already retained."""

    reference_id: str
    subject_id: str
    scope_id: str | None = None
    source_family: str
    source_definition_id: str
    acquisition_receipt_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    evidence_locator_ids: tuple[str, ...] = ()
    representation_artifact_ids: tuple[str, ...] = ()
    representation_hashes: dict[str, str] = Field(default_factory=dict)
    rights_policy_id: str | None = None
    rights_role: str
    declared_state: GovernedMaterialState = "available"
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
        "reference_id", "subject_id", "source_family", "source_definition_id",
        "rights_role", "claim_family_id", "task_profile", "task_profile_version",
        "schema_version",
    )
    @classmethod
    def _text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("scope_id", "rights_policy_id", "physical_bundle_opportunity")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator(
        "acquisition_receipt_ids", "source_record_ids", "evidence_locator_ids",
        "representation_artifact_ids",
    )
    @classmethod
    def _unique_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("reference IDs must be nonblank")
        if len(set(value)) != len(value):
            raise ValueError("reference IDs must be unique")
        return value

    @field_validator("representation_hashes")
    @classmethod
    def _hashes(cls, value: dict[str, str]) -> dict[str, str]:
        for artifact_id, content_hash in value.items():
            if not artifact_id.strip() or len(content_hash) != 64:
                raise ValueError("representation hashes must be keyed by nonblank IDs and contain SHA-256 values")
            int(content_hash, 16)
        return value

    @model_validator(mode="after")
    def _hash_keys_are_representations(self) -> "GovernedReference":
        if not set(self.representation_hashes).issubset(self.representation_artifact_ids):
            raise ValueError("representation hashes may only name representation artifacts")
        return self


class PreflightDiagnostic(StrictPlanModel):
    reference_id: str
    subject_id: str
    state: GovernedMaterialState
    reason: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class GovernedFactoryPreflight:
    tasks: tuple[dict[str, Any], ...]
    diagnostics: tuple[PreflightDiagnostic, ...]

    @property
    def factory_plan(self) -> FactoryPlan:
        return FactoryPlan.from_manifest(list(self.tasks))

    @property
    def accepted_count(self) -> int:
        return len(self.tasks)


def _diagnostic(reference: GovernedReference, state: GovernedMaterialState, reason: str, *details: str) -> PreflightDiagnostic:
    return PreflightDiagnostic(
        reference_id=reference.reference_id,
        subject_id=reference.subject_id,
        state=state,
        reason=reason,
        details=tuple(details),
    )


def _material_hash_for_locator(catalog: Any, locator: dict[str, Any]) -> str | None:
    if locator.get("artifact_id"):
        artifact = catalog.get_artifact(locator["artifact_id"])
        return None if artifact is None else artifact.get("content_hash")
    if locator.get("source_record_id"):
        source = catalog.get_source_record(locator["source_record_id"])
        return None if source is None else source.get("payload_hash")
    return None


def _build_typed_task(reference: GovernedReference, task: PlannedLogicalTask, catalog: Any, actual_hashes: dict[str, str]) -> ModelTask[Any]:
    evidence_inputs: list[EvidenceInput] = []
    for evidence_id in task.evidence_locator_ids:
        locator = catalog.get_evidence_locator(evidence_id)
        content_hash = _material_hash_for_locator(catalog, locator or {})
        if content_hash is None:
            raise ValueError(f"evidence locator {evidence_id} has no durable content hash")
        evidence_inputs.append(EvidenceInput(
            evidence_id=evidence_id,
            content_hash=content_hash,
            selection_hash=locator["material_hash"],
        ))
    parameters = {
        "logical_task_id": task.logical_task_id,
        "governed_reference_hash": task.governed_reference_hash,
        "source_family": reference.source_family,
        "source_definition_ids": list(task.source_definition_ids),
        "acquisition_receipt_ids": list(task.acquisition_receipt_ids),
        "source_record_ids": list(task.source_record_ids),
        "evidence_locator_ids": list(task.evidence_locator_ids),
        "representation_artifact_ids": list(task.representation_artifact_ids),
        "representation_hashes": actual_hashes,
        "rights_policy_ids": list(task.rights_policy_ids),
        "rights_roles": list(task.rights_roles),
    }
    policies = (VersionedPolicy(policy_id="phase5-governed-reference-preflight", version="1"),)
    cache_key = model_task_cache_key(
        task_type="structured_extraction",
        task_schema=_INPUT_SCHEMA,
        output_schema=_OUTPUT_SCHEMA,
        evidence_inputs=tuple(evidence_inputs),
        prompt_template_id="phase5-governed-reference-planning",
        prompt_template_version="1",
        policy_refs=policies,
        provider_id="fake",
        model_snapshot="phase5-governed-factory-v1",
        parameters=parameters,
        material_tool_versions=(),
    )
    record_id = deterministic_id(
        "modeltask:",
        {
            "subject_id": reference.subject_id,
            "scope_id": reference.scope_id,
            "task_type": "structured_extraction",
            "cache_key": cache_key,
            "output_schema": _OUTPUT_SCHEMA,
        },
    )
    return ModelTask(
        record_id=record_id,
        created_at=_TASK_CREATED_AT,
        producer=ProducerRef(kind="code", producer_id="phase5-governed-factory-integration", version="1"),
        subject_id=reference.subject_id,
        scope_id=reference.scope_id,
        cohort_id=None,
        task_type="structured_extraction",
        task_schema=_INPUT_SCHEMA,
        output_schema=_OUTPUT_SCHEMA,
        evidence_inputs=tuple(evidence_inputs),
        prompt_template_id="phase5-governed-reference-planning",
        prompt_template_version="1",
        policy_refs=policies,
        provider_id="fake",
        model_snapshot="phase5-governed-factory-v1",
        parameters=parameters,
        material_tool_versions=(),
        cache_key=cache_key,
        paid_output_categories=("extraction",),
    )


def _validate_available(
    reference: GovernedReference,
    catalog: Any,
    retained_bytes: Callable[[str], bytes] | None,
) -> tuple[PreflightDiagnostic | None, dict[str, str]]:
    subject = catalog.get_subject(reference.subject_id)
    if subject is None:
        return _diagnostic(reference, "missing", "subject reference is not durable"), {}
    if reference.scope_id is not None:
        scope = catalog.get_scope(reference.scope_id)
        if scope is None:
            return _diagnostic(reference, "missing", "scope reference is not durable"), {}
        if scope.get("subject_id") != reference.subject_id:
            return _diagnostic(reference, "mismatched", "scope is owned by a different subject", reference.scope_id), {}
    if not reference.source_record_ids or not reference.evidence_locator_ids or not reference.representation_artifact_ids:
        return _diagnostic(reference, "structurally_invalid", "available material requires source, evidence and representation references"), {}
    if not reference.acquisition_receipt_ids:
        return _diagnostic(reference, "unrecoverable", "available material has no acquisition receipt"), {}
    if catalog.get_source_definition(reference.source_definition_id) is None:
        return _diagnostic(reference, "missing", "source definition reference is not durable"), {}

    receipts = []
    for receipt_id in reference.acquisition_receipt_ids:
        receipt = catalog.get_acquisition_receipt(receipt_id)
        if receipt is None:
            return _diagnostic(reference, "missing", "acquisition receipt reference is not durable", receipt_id), {}
        if receipt.get("source_definition_id") != reference.source_definition_id:
            return _diagnostic(reference, "mismatched", "acquisition receipt is bound to a different source definition", receipt_id), {}
        outcome = receipt.get("outcome")
        if outcome == "blocked":
            return _diagnostic(reference, "blocked", "governed acquisition is blocked", receipt_id), {}
        if outcome in {"failed", "unavailable"}:
            return _diagnostic(reference, "retrieval_failed", "governed acquisition did not retrieve material", receipt_id), {}
        if outcome == "absent":
            return _diagnostic(reference, "missing", "governed acquisition recorded source absence", receipt_id), {}
        if outcome not in _AVAILABLE_OUTCOMES or not receipt.get("content_hash") or not receipt.get("artifact_id"):
            return _diagnostic(reference, "structurally_invalid", "acquisition receipt is not content-bearing", receipt_id), {}
        receipts.append(receipt)

    receipt_hashes = {str(item["content_hash"]) for item in receipts}
    for source_record_id in reference.source_record_ids:
        source = catalog.get_source_record(source_record_id)
        if source is None:
            return _diagnostic(reference, "missing", "source record reference is not durable", source_record_id), {}
        if source.get("source_family") != reference.source_family:
            return _diagnostic(reference, "mismatched", "source record family does not match governed reference", source_record_id), {}
        about_subjects = set((source.get("material") or {}).get("about_subject_ids") or ())
        if about_subjects and reference.subject_id not in about_subjects:
            return _diagnostic(reference, "mismatched", "source record is bound to a different subject", source_record_id), {}
        if source.get("payload_hash") not in receipt_hashes:
            return _diagnostic(reference, "mismatched", "source record payload hash does not match acquisition material", source_record_id), {}

    actual_hashes: dict[str, str] = {}
    acquisition_artifacts = {str(item["artifact_id"]) for item in receipts}
    for artifact_id in reference.representation_artifact_ids:
        artifact = catalog.get_artifact(artifact_id)
        if artifact is None:
            return _diagnostic(reference, "missing", "representation artifact reference is not durable", artifact_id), {}
        if artifact.get("availability") == "quarantined":
            return _diagnostic(reference, "blocked", "representation artifact is quarantined", artifact_id), {}
        if artifact.get("availability") != "available":
            return _diagnostic(reference, "unrecoverable", "representation artifact is not retained as available", artifact_id), {}
        actual_hash = str(artifact.get("content_hash"))
        expected_hash = reference.representation_hashes.get(artifact_id, actual_hash)
        if expected_hash != actual_hash:
            return _diagnostic(reference, "mismatched", "representation hash does not match durable artifact", artifact_id), {}
        if retained_bytes is not None:
            try:
                retained = retained_bytes(artifact_id)
            except (FileNotFoundError, OSError, ValueError):
                return _diagnostic(reference, "unrecoverable", "retained representation bytes cannot be read", artifact_id), {}
            if hashlib.sha256(retained).hexdigest() != actual_hash:
                return _diagnostic(reference, "mismatched", "retained representation bytes do not match durable artifact", artifact_id), {}
        lineage = catalog.get_artifact_lineage(artifact_id)
        if acquisition_artifacts and not any(item.get("input_artifact_id") in acquisition_artifacts for item in lineage):
            return _diagnostic(reference, "mismatched", "representation lineage does not point to acquired material", artifact_id), {}
        actual_hashes[artifact_id] = actual_hash

    accepted_evidence = set(reference.source_record_ids) | set(reference.representation_artifact_ids) | acquisition_artifacts
    for evidence_id in reference.evidence_locator_ids:
        locator = catalog.get_evidence_locator(evidence_id)
        if locator is None:
            return _diagnostic(reference, "missing", "evidence locator reference is not durable", evidence_id), {}
        if locator.get("source_record_id") not in accepted_evidence and locator.get("artifact_id") not in accepted_evidence:
            return _diagnostic(reference, "mismatched", "evidence locator is outside the governed material references", evidence_id), {}
    return None, actual_hashes


def preflight_governed_references(
    references: Iterable[GovernedReference | dict[str, Any]],
    *,
    catalog: Any,
    retained_bytes: Callable[[str], bytes] | None = None,
    build_id: str = "phase5-governed-factory-integration-v1",
    route_policy_version: str = "phase5-governed-reference-route-v1",
) -> GovernedFactoryPreflight:
    """Validate references and lower only ready material into Factory work."""
    tasks: list[dict[str, Any]] = []
    diagnostics: list[PreflightDiagnostic] = []
    seen_references: set[str] = set()
    for raw in references:
        reference = raw if isinstance(raw, GovernedReference) else GovernedReference.model_validate(raw)
        if reference.reference_id in seen_references:
            diagnostics.append(_diagnostic(reference, "structurally_invalid", "reference identity is duplicated"))
            continue
        seen_references.add(reference.reference_id)
        if reference.declared_state != "available":
            diagnostics.append(_diagnostic(reference, reference.declared_state, "governed input state is not eligible for Factory work"))
            continue
        diagnostic, actual_hashes = _validate_available(reference, catalog, retained_bytes)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
            continue
        material = {
            "reference_id": reference.reference_id,
            "subject_id": reference.subject_id,
            "scope_id": reference.scope_id,
            "source_family": reference.source_family,
            "source_definition_id": reference.source_definition_id,
            "acquisition_receipt_ids": reference.acquisition_receipt_ids,
            "source_record_ids": reference.source_record_ids,
            "evidence_locator_ids": reference.evidence_locator_ids,
            "representation_hashes": actual_hashes,
            "rights_policy_id": reference.rights_policy_id,
            "rights_role": reference.rights_role,
        }
        reference_hash = canonical_sha256(material)
        evidence_identity = canonical_sha256({"source_record_ids": reference.source_record_ids, "evidence_locator_ids": reference.evidence_locator_ids, "representation_hashes": actual_hashes})
        identity = {
            "build_id": build_id,
            "reference_hash": reference_hash,
            "subject_id": reference.subject_id,
            "scope_id": reference.scope_id,
            "claim_family_id": reference.claim_family_id,
            "task_profile": reference.task_profile,
            "task_profile_version": reference.task_profile_version,
            "schema_version": reference.schema_version,
            "evidence_corpus_hash": evidence_identity,
            "route_policy_version": route_policy_version,
        }
        logical_task_id = deterministic_id("semtask:", identity)
        planned = PlannedLogicalTask(
            logical_task_id=logical_task_id,
            build_id=build_id,
            subject_id=reference.subject_id,
            scope_id=reference.scope_id,
            claim_family_id=reference.claim_family_id,
            task_profile=reference.task_profile,
            task_profile_version=reference.task_profile_version,
            schema_version=reference.schema_version,
            evidence_corpus_hash=evidence_identity,
            prompt_policy_version="phase5-governed-reference-preflight:v1",
            route_policy_version=route_policy_version,
            difficulty=reference.difficulty,
            physical_bundle_opportunity=reference.physical_bundle_opportunity,
            source_definition_ids=(reference.source_definition_id,),
            acquisition_receipt_ids=reference.acquisition_receipt_ids,
            source_record_ids=reference.source_record_ids,
            evidence_locator_ids=reference.evidence_locator_ids,
            representation_artifact_ids=reference.representation_artifact_ids,
            representation_hashes=tuple(sorted(actual_hashes.items())),
            rights_policy_ids=() if reference.rights_policy_id is None else (reference.rights_policy_id,),
            rights_roles=(reference.rights_role,),
            governed_reference_hash=reference_hash,
        )
        typed_task = _build_typed_task(reference, planned, catalog, actual_hashes)
        task = planned.model_dump()
        task["_model_task"] = typed_task
        tasks.append(task)
    return GovernedFactoryPreflight(tasks=tuple(tasks), diagnostics=tuple(diagnostics))


__all__ = [
    "GovernedFactoryPreflight", "GovernedMaterialState", "GovernedReference",
    "PreflightDiagnostic", "preflight_governed_references",
]
