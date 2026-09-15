"""Deterministic, retained-evidence North Star v0.2 reprojection for §§3, 6 and 11.

This is deliberately an assignment adapter, never an extractor, promoter, or
capability assessment.  Each predicate has one owner section; callers cannot
obtain cross-section propagation by supplying a different numeric section.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.direct_service import CoverageState
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput


Section3611Predicate = Literal[
    "program_or_service_scope_reported", "coordination_source_reported", "operating_division_reported",
    "participation_opportunity_reported", "participation_role_reported", "participation_episode_reported",
    "aggregate_participation_measure_reported", "volunteer_contribution_hours_reported",
    "organisational_scale_measure_reported", "resource_or_infrastructure_fact_reported", "capability_source_reported",
]
ClaimBasis = Literal["source_fact", "source_interpretation"]
ScopeKind = Literal["organisation", "program", "service", "project", "site", "reporting_group", "other"]
_SECTION = {
    "program_or_service_scope_reported": 3, "coordination_source_reported": 3, "operating_division_reported": 3,
    "participation_opportunity_reported": 6, "participation_role_reported": 6,
    "participation_episode_reported": 6, "aggregate_participation_measure_reported": 6,
    "volunteer_contribution_hours_reported": 6,
    "organisational_scale_measure_reported": 11, "resource_or_infrastructure_fact_reported": 11,
    "capability_source_reported": 11,
}
_MISSINGNESS = {
    "not_found": ("NOT_FOUND", "unknown_history"), "source_silent": ("SOURCE_SILENT", "processed_source_silent"),
    "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"), "not_acquired": ("NOT_ACQUIRED", "not_acquired"),
    "not_processed": ("NOT_PROCESSED", "no_domain_result"), "not_reviewed": ("NOT_REVIEWED", "not_reviewed"),
    "not_applicable": ("NOT_APPLICABLE", "not_applicable"), "withheld": ("WITHHELD", "withheld"),
    "stale": ("STALE", "unknown_history"), "unknown": ("UNKNOWN", "unknown_history"),
}


class Section3611ProjectionInput(StrictModel):
    """One atomic §3, §6 or §11 source-bound proposition."""
    predicate: Section3611Predicate
    subject_id: str
    scope_id: str
    scope_kind: ScopeKind
    coverage_state: CoverageState = "unknown"
    claim_basis: ClaimBasis
    source_role: Literal["supporting", "corroborating", "context"]
    evidence_locator_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    observation_time: ObservationTime | None = None
    detail: str | None = None
    value: CanonicalValue | None = None
    unit: str | None = None
    participant_population: str | None = None
    scope_role: Literal["program_or_service", "coordination", "operating_division"] | None = None

    @field_validator("subject_id", "scope_id", "detail", "unit", "participant_population")
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
    def _bounded_semantics(self) -> "Section3611ProjectionInput":
        if self.coverage_state == "supported" and (not self.evidence_locator_ids or not self.source_record_ids or not self.lineage_ids or self.observation_time is None):
            raise ValueError("supported propositions require time, locator, source and lineage")
        if self.predicate == "program_or_service_scope_reported":
            if self.scope_kind not in {"program", "service", "project"} or self.scope_role != "program_or_service":
                raise ValueError("program/service scope requires a child scope and explicit scope role")
        elif self.predicate == "coordination_source_reported":
            if self.scope_role != "coordination":
                raise ValueError("coordination requires an explicit coordination scope role")
        elif self.predicate == "operating_division_reported":
            if self.scope_kind != "other" or self.scope_role != "operating_division":
                raise ValueError("operating division remains an other scope with explicit role")
        elif self.scope_role is not None:
            raise ValueError("scope_role is limited to section-3 scope predicates")
        if self.predicate in {"aggregate_participation_measure_reported", "participation_episode_reported", "volunteer_contribution_hours_reported"}:
            if self.value is None or self.unit is None or self.participant_population is None:
                raise ValueError("participation measures require value, unit and explicit population")
        elif self.participant_population is not None:
            raise ValueError("participant population is limited to participation measures or episodes")
        if self.predicate == "capability_source_reported" and (self.claim_basis != "source_interpretation" or self.detail is None):
            raise ValueError("qualitative capability is only a detailed source interpretation")
        if self.predicate != "capability_source_reported" and self.claim_basis != "source_fact":
            raise ValueError("only qualitative capability may use source_interpretation")
        return self


def _payload(item: Section3611ProjectionInput) -> dict[str, CanonicalValue]:
    payload: dict[str, CanonicalValue] = {
        "north_star_projection_contract": "north-star-v0.2", "section_id": _SECTION[item.predicate],
        "section3611_predicate": item.predicate, "claim_basis": item.claim_basis,
        "coverage_state": item.coverage_state, "source_role": item.source_role,
    }
    for key in ("detail", "value", "unit", "participant_population", "scope_role"):
        value = getattr(item, key)
        if value is not None:
            payload[key] = value
    return payload


def project_section3611_observation(item: Section3611ProjectionInput, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    """Project one bounded fact with an immutable v0.2 section owner."""
    outcome = "supported" if item.coverage_state == "supported" else "unknown"
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=(item.subject_id,),
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=x) for x in item.lineage_ids),
        subject_id=item.subject_id, scope_id=item.scope_id, predicate=f"north_star_v02.section{_SECTION[item.predicate]}.{item.predicate}",
        value=_payload(item), outcome_state=outcome, evidence_locator_ids=item.evidence_locator_ids,
        source_record_ids=item.source_record_ids, observation_time=item.observation_time or ObservationTime(observed_at=created_at),
        method="north_star_v02_section3611_reprojection")


def section3611_card_evidence(item: Section3611ProjectionInput, observation: Observation) -> CardEvidence:
    section = _SECTION[item.predicate]
    outcome = "supported" if item.coverage_state == "supported" else "unknown"
    if (observation.subject_id != item.subject_id or observation.about_subject_ids != (item.subject_id,) or observation.scope_id != item.scope_id
        or observation.predicate != f"north_star_v02.section{section}.{item.predicate}" or observation.value != _payload(item)
        or observation.outcome_state != outcome or observation.evidence_locator_ids != item.evidence_locator_ids
        or observation.source_record_ids != item.source_record_ids or observation.observation_time != item.observation_time
        or observation.method != "north_star_v02_section3611_reprojection"):
        raise ValueError("section-3/6/11 CardEvidence requires the matching projected observation")
    if tuple(edge.target_artifact_id for edge in observation.lineage if edge.edge_type == "projected_as") != item.lineage_ids:
        raise ValueError("section-3/6/11 CardEvidence requires matching observation lineage")
    return CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(section,),
        projection_contract_id="north-star-v0.2", note=f"v0.2-only section-{section} {item.predicate}; no automatic cross-section assignment")


def section3611_missingness(*, subject_id: str, section_id: Literal[3, 6, 11], coverage_state: CoverageState, note: str | None = None) -> CoverageInput:
    try:
        state, basis = _MISSINGNESS[coverage_state]
    except KeyError as exc:
        raise ValueError("section-3/6/11 missingness requires a non-positive coverage state") from exc
    return CoverageInput(subject_id=subject_id, section_id=section_id, projection_contract_id="north-star-v0.2", state=state, basis=basis, note=note)
