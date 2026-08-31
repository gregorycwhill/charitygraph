"""Typed contracts for the bounded Phase 3 direct-service pressure case.

These are task/output contracts, not a new card or domain ontology.  They
make the distinctions exercised by the first case explicit while projecting
into the existing append-only Observation and RelationshipStatement
primitives.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import CanonicalValue, ProducerRef, SchemaRef, StrictModel, require_nonblank
from .knowledge import Observation, ObservationTime, RelationshipRole


def _schema(name: str) -> SchemaRef:
    return SchemaRef(schema_id=f"urn:charitygraph:builder:schema:{name}:1.0", schema_version="1.0")


CoverageState = Literal[
    "supported",
    "asserted_none",
    "observed_absent",
    "not_found",
    "source_silent",
    "source_unavailable",
    "not_acquired",
    "not_attempted",
    "not_processed",
    "processing_failed",
    "not_reviewed",
    "not_applicable",
    "withheld",
    "stale",
    "unknown",
]

DirectServiceSection = Literal[
    "participation",
    "capability_access_availability",
    "scheme_accreditation",
]

DirectServicePropositionType = Literal[
    "participation_opportunity",
    "participation_measure",
    "service_offer",
    "eligibility",
    "access_pathway",
    "current_availability",
    "capacity_measure",
    "scheme_membership",
    "accreditation",
]

ScopeKind = Literal["subject", "organisation", "program", "service", "project", "site", "reporting_group"]
RelationshipDirection = Literal["source_to_target", "target_to_source", "bidirectional", "uncertain"]


class DirectServiceEvidenceRef(StrictModel):
    """A compact, already-resolved locator supplied to a semantic task."""

    locator: str
    role: Literal["supporting", "corroborating", "context"]

    @field_validator("locator")
    @classmethod
    def _locator(cls, value: str) -> str:
        return require_nonblank(value, "locator")


class DirectServiceProposition(StrictModel):
    """One evidence-bound proposition at an explicit scope and grain."""

    proposition_type: DirectServicePropositionType
    scope_id: str
    scope_kind: ScopeKind
    scope_label: str | None = None
    coverage_state: CoverageState = "unknown"
    value: CanonicalValue | None = None
    unit: str | None = None
    scheme_id: str | None = None
    scheme_version: str | None = None
    scheme_status: str | None = None
    scheme_identifier: str | None = None
    observation_time: ObservationTime | None = None
    evidence: tuple[DirectServiceEvidenceRef, ...] = ()
    qualification: str | None = None

    @field_validator("scope_id", "scope_label", "unit", "scheme_id", "scheme_version", "scheme_status", "scheme_identifier", "qualification")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _invariants(self) -> "DirectServiceProposition":
        if len({item.locator for item in self.evidence}) != len(self.evidence):
            raise ValueError("direct-service evidence locators must be unique")
        if self.coverage_state in {"supported", "asserted_none", "observed_absent"} and not any(
            item.role == "supporting" for item in self.evidence
        ):
            raise ValueError("supported or observed absence propositions require supporting evidence")
        if self.proposition_type in {"scheme_membership", "accreditation"} and self.scheme_id is None:
            raise ValueError("scheme and accreditation propositions require scheme_id")
        if self.proposition_type not in {"scheme_membership", "accreditation"} and any(
            value is not None for value in (self.scheme_id, self.scheme_version, self.scheme_status, self.scheme_identifier)
        ):
            raise ValueError("scheme fields are limited to membership/accreditation propositions")
        if self.proposition_type in {"participation_measure", "capacity_measure"} and self.unit is None:
            raise ValueError("measure propositions require a unit")
        return self


class DirectServiceRelationship(StrictModel):
    """A role-bearing relationship output whose endpoints remain explicit."""

    source_scope_kind: ScopeKind
    source_scope_id: str
    source_label: str
    target_scope_kind: ScopeKind
    target_scope_id: str
    target_label: str
    role: RelationshipRole
    direction: RelationshipDirection
    evidence: tuple[DirectServiceEvidenceRef, ...] = ()
    observation_time: ObservationTime | None = None

    @field_validator("source_scope_id", "target_scope_id", "source_label", "target_label")
    @classmethod
    def _labels(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator("evidence")
    @classmethod
    def _evidence(cls, value: tuple[DirectServiceEvidenceRef, ...]) -> tuple[DirectServiceEvidenceRef, ...]:
        if not value:
            raise ValueError("direct-service relationships require evidence")
        return value


class DirectServiceSemanticOutput(StrictModel):
    """Validated logical output for the bounded direct-service task."""

    schema_ref: SchemaRef = Field(default_factory=lambda: _schema("direct-service-semantic-output"), validation_alias="schema", serialization_alias="schema")
    section: DirectServiceSection
    propositions: tuple[DirectServiceProposition, ...] = ()
    relationships: tuple[DirectServiceRelationship, ...] = ()

    @model_validator(mode="after")
    def _section_types(self) -> "DirectServiceSemanticOutput":
        allowed = {
            "participation": {"participation_opportunity", "participation_measure"},
            "capability_access_availability": {"service_offer", "eligibility", "access_pathway", "current_availability", "capacity_measure"},
            "scheme_accreditation": {"scheme_membership", "accreditation"},
        }
        if any(item.proposition_type not in allowed[self.section] for item in self.propositions):
            raise ValueError("proposition type does not belong to the declared direct-service section")
        return self


def project_observation(
    proposition: DirectServiceProposition,
    *,
    record_id: str,
    subject_id: str,
    scope_id: str | None,
    source_record_ids: tuple[str, ...],
    created_at: datetime,
    producer: ProducerRef | dict,
    method: str = "direct_service_semantic_task",
) -> Observation:
    """Project one typed proposition into the existing append-only observation.

    Coverage state is retained in the canonical value so states not present in
    the legacy outcome-state column (for example ``source_silent`` versus
    ``not_found``) are not collapsed.
    """

    if not source_record_ids:
        raise ValueError("direct-service observations require source record IDs")
    payload: dict[str, CanonicalValue] = {"coverage_state": proposition.coverage_state, "value": proposition.value}
    for key, value in (
        ("unit", proposition.unit),
        ("scheme_id", proposition.scheme_id),
        ("scheme_version", proposition.scheme_version),
        ("scheme_status", proposition.scheme_status),
        ("scheme_identifier", proposition.scheme_identifier),
        ("qualification", proposition.qualification),
    ):
        if value is not None:
            payload[key] = value
    outcome_state = {
        "processing_failed": "extraction_failure", "not_applicable": "not_applicable",
        "withheld": "withheld", "unknown": "unknown", "not_attempted": "not_attempted",
        "source_unavailable": "not_attempted", "not_acquired": "not_attempted",
        "not_processed": "not_attempted", "not_reviewed": "unknown", "not_found": "unknown",
        "source_silent": "unknown", "stale": "unknown", "asserted_none": "resolved",
        "observed_absent": "resolved", "supported": "supported",
    }[proposition.coverage_state]
    return Observation(
        record_id=record_id, created_at=created_at, producer=producer,
        subject_id=subject_id, scope_id=scope_id,
        predicate=f"direct_service.{proposition.proposition_type}", value=payload,
        outcome_state=outcome_state,
        evidence_locator_ids=tuple(item.locator for item in proposition.evidence),
        source_record_ids=source_record_ids,
        observation_time=proposition.observation_time or {"observed_at": created_at},
        method=method,
    )


def validate_scope_bindings(output: DirectServiceSemanticOutput, allowed_scope_ids: set[str]) -> None:
    """Reject model scope substitutions outside the task-visible allow-list."""

    if not allowed_scope_ids:
        raise ValueError("direct-service task must provide at least one visible scope")
    for proposition in output.propositions:
        if proposition.scope_id not in allowed_scope_ids:
            raise ValueError(f"unknown proposition scope_id: {proposition.scope_id}")
    for relationship in output.relationships:
        if relationship.source_scope_id not in allowed_scope_ids:
            raise ValueError(f"unknown relationship source_scope_id: {relationship.source_scope_id}")
        if relationship.target_scope_id not in allowed_scope_ids:
            raise ValueError(f"unknown relationship target_scope_id: {relationship.target_scope_id}")


DIRECT_SERVICE_OUTPUT_SCHEMA = _schema("direct-service-semantic-output")


__all__ = [
    "CoverageState", "DirectServiceSection", "DirectServicePropositionType", "ScopeKind",
    "RelationshipDirection", "DirectServiceEvidenceRef", "DirectServiceProposition",
    "DirectServiceRelationship", "DirectServiceSemanticOutput",
    "DIRECT_SERVICE_OUTPUT_SCHEMA", "project_observation", "validate_scope_bindings",
]
