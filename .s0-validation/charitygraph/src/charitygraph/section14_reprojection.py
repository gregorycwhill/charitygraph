"""Deterministic North Star v0.2 section-14 funding projections.

This is a projection vocabulary, not an extractor or a dependency assessment.
Every atomic observation is bound to one evidence-supported funding context.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.direct_service import CoverageState
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput


FundingPredicate = Literal[
    "instrument_observed", "stage_observed", "restriction_observed", "condition_observed",
    "amount_observed", "concentration_measure", "dependency_source_reported",
    "source_diversity_observed", "diversification_source_reported",
    "alternative_funding_source_reported", "unresolved_party_mention",
]
ClaimBasis = Literal["source_fact", "source_interpretation", "deterministic_calculation", "candidate", "governed_assessment", "unknown"]
FundingStage = Literal["award", "commitment", "payment", "receipt", "reporting_or_acquittal"]
_MISSINGNESS = {
    "not_found": ("NOT_FOUND", "unknown_history"), "source_silent": ("SOURCE_SILENT", "processed_source_silent"),
    "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"), "not_acquired": ("NOT_ACQUIRED", "not_acquired"),
    "not_processed": ("NOT_PROCESSED", "no_domain_result"), "not_reviewed": ("NOT_REVIEWED", "not_reviewed"),
    "not_applicable": ("NOT_APPLICABLE", "not_applicable"), "withheld": ("WITHHELD", "withheld"),
    "stale": ("STALE", "unknown_history"), "unknown": ("UNKNOWN", "unknown_history"),
}


class Section14FundingInput(StrictModel):
    """One atomic, evidence-bound §14 proposition; never a funding mega-record."""
    predicate: FundingPredicate
    funding_context_id: str
    subject_id: str
    scope_id: str
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
    numerator_observation_id: str | None = None
    denominator_observation_id: str | None = None
    calculation_method: str | None = None
    stage: FundingStage | None = None

    @field_validator("funding_context_id", "subject_id", "scope_id", "detail", "unit", "numerator_observation_id", "denominator_observation_id", "calculation_method")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("funding identifiers must be nonblank and unique")
        return value

    @model_validator(mode="after")
    def _evidence_and_semantics(self) -> "Section14FundingInput":
        if self.coverage_state == "supported":
            if not self.evidence_locator_ids or not self.source_record_ids or not self.lineage_ids or self.observation_time is None:
                raise ValueError("supported funding propositions require time, locator, source and lineage")
            if self.predicate not in {"concentration_measure", "amount_observed"} and self.detail is None:
                raise ValueError("supported funding propositions require substantive detail")
            if self.predicate == "amount_observed" and self.value is None:
                raise ValueError("supported funding amount requires a substantive value")
        if self.predicate == "stage_observed":
            if self.stage is None:
                raise ValueError("funding stage requires an explicit stage")
        elif self.stage is not None:
            raise ValueError("stage is limited to stage_observed")
        if self.predicate == "concentration_measure":
            if self.claim_basis != "deterministic_calculation" or not all((self.numerator_observation_id, self.denominator_observation_id, self.calculation_method, self.value)):
                raise ValueError("concentration measure requires deterministic numerator, denominator, method and result")
        elif any(item is not None for item in (self.numerator_observation_id, self.denominator_observation_id, self.calculation_method)):
            raise ValueError("calculation provenance is limited to concentration_measure")
        if self.predicate == "dependency_source_reported":
            if self.claim_basis != "source_interpretation" or self.detail is None:
                raise ValueError("dependency is only a source-reported interpretation with detail")
        if self.claim_basis == "governed_assessment":
            raise ValueError("C2 has no governed dependency assessment rule")
        return self


def _payload(item: Section14FundingInput) -> dict[str, CanonicalValue]:
    payload: dict[str, CanonicalValue] = {
        "north_star_projection_contract": "north-star-v0.2", "section_id": 14,
        "funding_context_id": item.funding_context_id, "section14_predicate": item.predicate,
        "claim_basis": item.claim_basis, "coverage_state": item.coverage_state, "source_role": item.source_role,
    }
    for key in ("detail", "value", "unit", "numerator_observation_id", "denominator_observation_id", "calculation_method", "stage"):
        value = getattr(item, key)
        if value is not None:
            payload[key] = value
    return payload


def project_section14_observation(item: Section14FundingInput, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    """Project one atomic §14 fact without inferring relation or dependency."""
    if item.observation_time is None:
        raise ValueError("section-14 reprojection requires explicit observation_time; created_at is record metadata")
    outcome = "supported" if item.coverage_state == "supported" else "unknown"
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=(item.subject_id,),
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=x) for x in item.lineage_ids),
        subject_id=item.subject_id, scope_id=item.scope_id, predicate=f"north_star_v02.section14.{item.predicate}",
        value=_payload(item), outcome_state=outcome, evidence_locator_ids=item.evidence_locator_ids,
        source_record_ids=item.source_record_ids, observation_time=item.observation_time,
        method="north_star_v02_section14_reprojection")


def section14_card_evidence(item: Section14FundingInput, observation: Observation) -> CardEvidence:
    expected_outcome = "supported" if item.coverage_state == "supported" else "unknown"
    if (observation.subject_id != item.subject_id or observation.about_subject_ids != (item.subject_id,)
        or observation.scope_id != item.scope_id or observation.outcome_state != expected_outcome
        or observation.predicate != f"north_star_v02.section14.{item.predicate}" or observation.value != _payload(item)
        or observation.evidence_locator_ids != item.evidence_locator_ids or observation.source_record_ids != item.source_record_ids
        or observation.observation_time != item.observation_time or observation.method != "north_star_v02_section14_reprojection"):
        raise ValueError("section-14 CardEvidence requires the matching projected observation")
    if tuple(edge.target_artifact_id for edge in observation.lineage if edge.edge_type == "projected_as") != item.lineage_ids:
        raise ValueError("section-14 CardEvidence requires matching observation lineage")
    return CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT",
        section_ids=(14,), projection_contract_id="north-star-v0.2", note=f"v0.2-only section-14 {item.predicate}; no automatic section-13 assignment")


def section14_missingness(*, subject_id: str, coverage_state: CoverageState, note: str | None = None) -> CoverageInput:
    try: state, basis = _MISSINGNESS[coverage_state]
    except KeyError as exc: raise ValueError("section-14 missingness requires a non-positive coverage state") from exc
    return CoverageInput(subject_id=subject_id, section_id=14, projection_contract_id="north-star-v0.2", state=state, basis=basis, note=note)
