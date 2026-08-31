"""Provider-facing DTOs for the bounded direct-service semantic task.

These transport models deliberately use a small JSON scalar algebra.  They are
not durable CharityGraph knowledge objects; :func:`wire_to_domain` converts a
validated response into the existing domain contract before persistence.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator

from .common import SchemaRef, StrictModel, require_nonblank
from .direct_service import (
    CoverageState,
    DirectServiceEvidenceRef,
    DirectServiceProposition,
    DirectServicePropositionType,
    DirectServiceRelationship,
    DirectServiceSection,
    DirectServiceSemanticOutput,
    RelationshipDirection,
    ScopeKind,
)
from .knowledge import RelationshipRole


WireScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None


class DirectServiceWireEvidenceRef(StrictModel):
    """Provider transport evidence reference; never persisted as a domain record."""

    locator: StrictStr
    role: Literal["supporting", "corroborating", "context"]

    @field_validator("locator")
    @classmethod
    def _locator(cls, value: str) -> str:
        return require_nonblank(value, "locator")


class DirectServiceWireObservationTime(StrictModel):
    effective_from: StrictStr | None = None
    effective_to: StrictStr | None = None
    reporting_period: StrictStr | None = None
    observed_at: StrictStr
    assessed_at: StrictStr | None = None


class DirectServiceWireProposition(StrictModel):
    """Bounded provider DTO for one typed proposition."""

    proposition_type: DirectServicePropositionType
    scope_id: StrictStr
    scope_kind: ScopeKind
    scope_label: StrictStr | None = None
    coverage_state: CoverageState = "unknown"
    value: WireScalar = None
    unit: StrictStr | None = None
    scheme_id: StrictStr | None = None
    scheme_version: StrictStr | None = None
    scheme_status: StrictStr | None = None
    scheme_identifier: StrictStr | None = None
    observation_time: DirectServiceWireObservationTime | None = None
    evidence: tuple[DirectServiceWireEvidenceRef, ...] = ()
    qualification: StrictStr | None = None


class DirectServiceWireRelationship(StrictModel):
    """Bounded provider DTO for one directed role relationship."""

    source_scope_kind: ScopeKind
    source_scope_id: StrictStr
    source_label: StrictStr
    target_scope_kind: ScopeKind
    target_scope_id: StrictStr
    target_label: StrictStr
    role: RelationshipRole
    direction: RelationshipDirection
    evidence: tuple[DirectServiceWireEvidenceRef, ...] = ()
    observation_time: DirectServiceWireObservationTime | None = None


class DirectServiceWireOutput(StrictModel):
    """Provider-only output; convert to ``DirectServiceSemanticOutput`` first."""

    schema_ref: SchemaRef = Field(
        default_factory=lambda: SchemaRef(
            schema_id="urn:charitygraph:builder:schema:direct-service-semantic-output:1.0",
            schema_version="1.0",
        ),
        validation_alias="schema",
        serialization_alias="schema",
    )
    section: DirectServiceSection
    propositions: tuple[DirectServiceWireProposition, ...] = ()
    relationships: tuple[DirectServiceWireRelationship, ...] = ()


def _temporal(value: DirectServiceWireObservationTime | None) -> dict | None:
    if value is None:
        return None

    def parse(raw: str | None, field: str):
        if raw is None:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")) if ("T" in raw or " " in raw) else date.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"invalid {field} temporal value") from exc

    return {
        "effective_from": parse(value.effective_from, "effective_from"),
        "effective_to": parse(value.effective_to, "effective_to"),
        "reporting_period": value.reporting_period,
        "observed_at": parse(value.observed_at, "observed_at"),
        "assessed_at": parse(value.assessed_at, "assessed_at"),
    }


def _canonical_scalar(value: WireScalar):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    raise ValueError("unsupported wire scalar")


def wire_to_domain(
    wire: DirectServiceWireOutput,
    *,
    allowed_scope_ids: set[str] | None = None,
    evidence_locators: set[str] | None = None,
) -> DirectServiceSemanticOutput:
    """Convert typed provider output without interpreting any prose."""
    def evidence(items):
        refs = tuple(DirectServiceEvidenceRef(locator=item.locator, role=item.role) for item in items)
        if evidence_locators is not None and any(item.locator not in evidence_locators for item in refs):
            raise ValueError("wire evidence locator is not present in the frozen packet")
        return refs

    propositions = tuple(
        DirectServiceProposition(
            proposition_type=item.proposition_type,
            scope_id=item.scope_id,
            scope_kind=item.scope_kind,
            scope_label=item.scope_label,
            coverage_state=item.coverage_state,
            value=_canonical_scalar(item.value),
            unit=item.unit,
            scheme_id=item.scheme_id,
            scheme_version=item.scheme_version,
            scheme_status=item.scheme_status,
            scheme_identifier=item.scheme_identifier,
            observation_time=_temporal(item.observation_time),
            evidence=evidence(item.evidence),
            qualification=item.qualification,
        )
        for item in wire.propositions
    )
    relationships = tuple(
        DirectServiceRelationship(
            source_scope_kind=item.source_scope_kind,
            source_scope_id=item.source_scope_id,
            source_label=item.source_label,
            target_scope_kind=item.target_scope_kind,
            target_scope_id=item.target_scope_id,
            target_label=item.target_label,
            role=item.role,
            direction=item.direction,
            evidence=evidence(item.evidence),
            observation_time=_temporal(item.observation_time),
        )
        for item in wire.relationships
    )
    domain = DirectServiceSemanticOutput(
        schema=wire.schema_ref,
        section=wire.section,
        propositions=propositions,
        relationships=relationships,
    )
    if allowed_scope_ids is not None:
        from .direct_service import validate_scope_bindings
        validate_scope_bindings(domain, allowed_scope_ids)
    return domain


__all__ = [
    "WireScalar", "DirectServiceWireEvidenceRef", "DirectServiceWireObservationTime",
    "DirectServiceWireProposition", "DirectServiceWireRelationship", "DirectServiceWireOutput",
    "wire_to_domain",
]
