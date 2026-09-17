"""Deterministic retained-evidence reprojection for North Star v0.2 section 7.

This module does not extract, reinterpret or promote evidence. It validates that
already-typed Direct Service propositions can be assigned only to the active
section-7 meaning while preserving their type, scope, locator and coverage
state.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.direct_service import CoverageState, DirectServiceProposition
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput


_SECTION_7_TYPES = frozenset({
    "service_offer", "eligibility", "access_pathway",
    "current_availability", "capacity_measure",
})
_TIME_BOUND_TYPES = frozenset({"current_availability", "capacity_measure"})
_MISSINGNESS = {
    "not_found": ("NOT_FOUND", "unknown_history"),
    "source_silent": ("SOURCE_SILENT", "processed_source_silent"),
    "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"),
    "not_acquired": ("NOT_ACQUIRED", "not_acquired"),
    "not_processed": ("NOT_PROCESSED", "no_domain_result"),
    "not_reviewed": ("NOT_REVIEWED", "not_reviewed"),
    "not_applicable": ("NOT_APPLICABLE", "not_applicable"),
    "withheld": ("WITHHELD", "withheld"),
    "stale": ("STALE", "unknown_history"),
    "unknown": ("UNKNOWN", "unknown_history"),
}

# These predicates belong only to the active North Star v0.2 projection.  They
# deliberately do not extend the historical Direct Service V1.2 wire type.
Section7V02Predicate = Literal[
    "advertised_availability", "operating_hours", "throughput", "waitlist",
    "staffing_constraint", "resource_constraint", "delivery_evidence",
]
FreshnessState = Literal["unassessed", "fresh", "stale"]
_TIME_SENSITIVE_V02 = frozenset({
    "advertised_availability", "operating_hours", "throughput", "waitlist",
    "staffing_constraint", "resource_constraint", "delivery_evidence",
})


class Section7V02ProjectionInput(StrictModel):
    """One explicit v0.2-only §7 predicate, never a historical wire output.

    It is a compact predicate vocabulary rather than a service mega-record:
    ``predicate`` remains the semantic role, while shared provenance fields
    keep a future retained observation traceable.
    """

    predicate: Section7V02Predicate
    subject_id: str
    scope_id: str
    scope_kind: Literal["organisation", "program", "service", "project", "site", "reporting_group"]
    coverage_state: CoverageState = "unknown"
    source_role: Literal["supporting", "corroborating", "context"]
    evidence_locator_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    observation_time: ObservationTime | None = None
    freshness_state: FreshnessState = "unassessed"
    freshness_policy_id: str | None = None
    availability_status: Literal["available", "limited", "waitlisted", "unavailable"] | None = None
    value: CanonicalValue | None = None
    unit: str | None = None
    detail: str | None = None

    @field_validator("subject_id", "scope_id", "freshness_policy_id", "unit", "detail")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("projection identifiers must be nonblank and unique")
        return value

    @model_validator(mode="after")
    def _distinct_and_evidence_bound(self) -> "Section7V02ProjectionInput":
        if self.coverage_state == "supported":
            if not self.evidence_locator_ids or not self.source_record_ids or not self.lineage_ids:
                raise ValueError("supported v0.2 section-7 predicates require locator, source and lineage")
            if self.predicate in _TIME_SENSITIVE_V02 and self.observation_time is None:
                raise ValueError("supported time-sensitive v0.2 section-7 predicates require observation_time")
        if self.freshness_state == "fresh" and self.freshness_policy_id is None:
            raise ValueError("freshness_state=fresh requires an explicit freshness policy")
        if self.freshness_policy_id is not None and self.freshness_state == "unassessed":
            raise ValueError("a freshness policy requires an assessed freshness state")
        if self.predicate == "advertised_availability":
            if self.availability_status is None:
                raise ValueError("advertised availability requires availability_status")
        elif self.availability_status is not None:
            raise ValueError("availability_status is limited to advertised_availability")
        if self.predicate == "throughput":
            if self.value is None or self.unit is None:
                raise ValueError("throughput requires value and unit")
        elif self.value is not None or self.unit is not None:
            if self.predicate != "waitlist":
                raise ValueError("numeric value and unit are limited to throughput or waitlist")
            if (self.value is None) != (self.unit is None):
                raise ValueError("waitlist measure requires both value and unit")
        if self.predicate in {"operating_hours", "staffing_constraint", "resource_constraint", "delivery_evidence"} and self.detail is None:
            raise ValueError(f"{self.predicate} requires detail")
        return self


class Section7V02Reprojection:
    """A versioned assignment for a predicate absent from the V1.2 wire schema."""

    def __init__(self, projection: Section7V02ProjectionInput) -> None:
        self.projection = projection

    @property
    def projection_contract_id(self) -> Literal["north-star-v0.2"]:
        return "north-star-v0.2"

    @property
    def section_ids(self) -> tuple[Literal[7], ...]:
        return (7,)

    def observation(
        self,
        *,
        record_id: str,
        created_at: datetime,
        producer: ProducerRef | dict,
    ) -> Observation:
        """Create the append-only observation owned by this v0.2 predicate."""
        return project_section7_v02_observation(
            self.projection, record_id=record_id, created_at=created_at, producer=producer,
        )

    def card_evidence(self, observation: Observation) -> CardEvidence:
        """Bind section evidence only to this predicate's created observation."""
        _assert_v02_observation_matches(self.projection, observation)
        return CardEvidence(
            observation_id=observation.record_id,
            disposition="REUSABLE_EXPERIMENTAL_INPUT",
            section_ids=self.section_ids,
            projection_contract_id=self.projection_contract_id,
            note=f"v0.2-only section-7 {self.projection.predicate}; no automatic section-11 assignment",
        )


def reproject_section7_v02(projection: Section7V02ProjectionInput) -> Section7V02Reprojection:
    """Assign one new explicit v0.2 §7 predicate without rewriting V1.2."""
    return Section7V02Reprojection(projection)


def _v02_outcome_state(coverage_state: CoverageState) -> str:
    return {
        "supported": "supported", "asserted_none": "resolved", "observed_absent": "resolved",
        "processing_failed": "extraction_failure", "not_applicable": "not_applicable",
        "withheld": "withheld", "unknown": "unknown", "not_attempted": "not_attempted",
        "source_unavailable": "not_attempted", "not_acquired": "not_attempted",
        "not_processed": "not_attempted", "not_reviewed": "unknown", "not_found": "unknown",
        "source_silent": "unknown", "stale": "unknown",
    }[coverage_state]


def project_section7_v02_observation(
    projection: Section7V02ProjectionInput,
    *,
    record_id: str,
    created_at: datetime,
    producer: ProducerRef | dict,
) -> Observation:
    """Project one explicit v0.2 §7 predicate into the existing Observation.

    The semantic role stays in the predicate string and in the immutable value
    payload; lineage edges run from the created observation to each supplied
    lineage artifact. This is deterministic projection, never extraction.
    """
    if projection.observation_time is None:
        raise ValueError("section-7 reprojection requires explicit observation_time; created_at is record metadata")
    value = _v02_observation_value(projection)
    return Observation(
        record_id=record_id,
        created_at=created_at,
        producer=producer,
        about_subject_ids=(projection.subject_id,),
        lineage=tuple(
            LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=item)
            for item in projection.lineage_ids
        ),
        subject_id=projection.subject_id,
        scope_id=projection.scope_id,
        predicate=f"north_star_v02.section7.{projection.predicate}",
        value=value,
        outcome_state=_v02_outcome_state(projection.coverage_state),
        evidence_locator_ids=projection.evidence_locator_ids,
        source_record_ids=projection.source_record_ids,
        observation_time=projection.observation_time,
        method="north_star_v02_section7_reprojection",
    )


def _v02_observation_value(projection: Section7V02ProjectionInput) -> dict[str, CanonicalValue]:
    """The immutable payload used by both projection and binding verification."""
    value: dict[str, CanonicalValue] = {
        "north_star_projection_contract": "north-star-v0.2",
        "section_id": 7,
        "section7_predicate": projection.predicate,
        "coverage_state": projection.coverage_state,
        "source_role": projection.source_role,
        "freshness_state": projection.freshness_state,
    }
    for key in ("freshness_policy_id", "availability_status", "value", "unit", "detail"):
        item = getattr(projection, key)
        if item is not None:
            value[key] = item
    return value


def _assert_v02_observation_matches(projection: Section7V02ProjectionInput, observation: Observation) -> None:
    if (
        observation.subject_id != projection.subject_id
        or observation.scope_id != projection.scope_id
        or observation.about_subject_ids != (projection.subject_id,)
        or observation.predicate != f"north_star_v02.section7.{projection.predicate}"
        or observation.value != _v02_observation_value(projection)
        or observation.outcome_state != _v02_outcome_state(projection.coverage_state)
        or observation.evidence_locator_ids != projection.evidence_locator_ids
        or observation.source_record_ids != projection.source_record_ids
        or observation.observation_time != projection.observation_time
        or observation.method != "north_star_v02_section7_reprojection"
    ):
        raise ValueError("section-7 CardEvidence requires the matching projected observation")
    targets = tuple(edge.target_artifact_id for edge in observation.lineage if edge.edge_type == "projected_as")
    if targets != projection.lineage_ids:
        raise ValueError("section-7 CardEvidence requires matching observation lineage")


class Section7Reprojection:
    """A compact v0.2 assignment derived from one retained typed proposition."""

    def __init__(self, proposition: DirectServiceProposition) -> None:
        if proposition.proposition_type not in _SECTION_7_TYPES:
            raise ValueError("only direct-service proposition types may project to North Star v0.2 section 7")
        if proposition.coverage_state == "supported" and proposition.proposition_type in _TIME_BOUND_TYPES:
            if proposition.observation_time is None:
                raise ValueError(f"{proposition.proposition_type} requires explicit retained time for a positive section-7 projection")
        if proposition.proposition_type == "capacity_measure" and proposition.coverage_state == "supported":
            if proposition.value is None or proposition.unit is None:
                raise ValueError("positive capacity_measure requires value and unit")
        self.proposition = proposition

    @property
    def projection_contract_id(self) -> Literal["north-star-v0.2"]:
        return "north-star-v0.2"

    @property
    def section_ids(self) -> tuple[Literal[7], ...]:
        return (7,)

    @property
    def evidence_locator_ids(self) -> tuple[str, ...]:
        return tuple(item.locator for item in self.proposition.evidence)

    def card_evidence(self, observation_id: str) -> CardEvidence:
        """Assign a retained experimental observation to section 7 only."""
        return CardEvidence(
            observation_id=observation_id,
            disposition="REUSABLE_EXPERIMENTAL_INPUT",
            section_ids=self.section_ids,
            projection_contract_id=self.projection_contract_id,
            note=f"retained direct-service {self.proposition.proposition_type}; no automatic section-11 assignment",
        )


def reproject_section7(proposition: DirectServiceProposition) -> Section7Reprojection:
    """Validate and retain one active-v0.2 section-7 assignment."""
    return Section7Reprojection(proposition)


def section7_missingness(
    *,
    subject_id: str,
    coverage_state: CoverageState,
    note: str | None = None,
) -> CoverageInput:
    """Project one retained non-positive Direct Service coverage state to section 7."""
    try:
        state, basis = _MISSINGNESS[coverage_state]
    except KeyError as exc:
        raise ValueError("section-7 missingness requires a non-positive retained coverage state") from exc
    return CoverageInput(
        subject_id=subject_id,
        section_id=7,
        projection_contract_id="north-star-v0.2",
        state=state,
        basis=basis,
        note=note,
    )


__all__ = [
    "Section7Reprojection", "reproject_section7", "section7_missingness",
    "Section7V02ProjectionInput", "Section7V02Reprojection", "reproject_section7_v02",
    "project_section7_v02_observation",
]
