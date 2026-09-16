"""Small active-v0.2 projections for the C6 and C7 specialist sections.

These inputs deliberately carry one semantic role at a time.  They are not a
taxonomy, fundraising, or ethos store and they never infer a claim from a
neighbouring North Star section.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.direct_service import CoverageState
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput

SpecialistPredicate = Literal[
    "activity_observed", "source_reported_classification_observed", "assessed_classification_observed",
    "discovery_signal_observed", "fundraising_practice_observed", "fundraising_campaign_observed",
    "ethos_self_description_observed", "ethos_affiliation_observed", "commitment_stated_observed",
    "claimed_implementation_observed", "observed_practice_observed", "verified_completion_observed",
]
EpistemicBasis = Literal["source_fact", "source_interpretation", "governed_event"]
AssignmentStatus = Literal["candidate", "accepted", "narrowed", "rejected", "abstained", "superseded"]

_SECTION = {
    "activity_observed": 4, "source_reported_classification_observed": 4,
    "assessed_classification_observed": 19, "discovery_signal_observed": 19,
    "fundraising_practice_observed": 8, "fundraising_campaign_observed": 8,
    "ethos_self_description_observed": 15, "ethos_affiliation_observed": 15,
    "commitment_stated_observed": 15, "claimed_implementation_observed": 15,
    "observed_practice_observed": 15, "verified_completion_observed": 15,
}
_MISSING = {
    "not_found": ("NOT_FOUND", "unknown_history"), "source_silent": ("SOURCE_SILENT", "processed_source_silent"),
    "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"), "not_acquired": ("NOT_ACQUIRED", "not_acquired"),
    "not_processed": ("NOT_PROCESSED", "no_domain_result"), "processing_failed": ("PROCESSING_FAILED", "processing_failed"),
    "not_reviewed": ("NOT_REVIEWED", "not_reviewed"), "not_attempted": ("NOT_ATTEMPTED", "not_attempted"),
    "unknown": ("UNKNOWN", "unknown_history"), "stale": ("STALE", "unknown_history"),
}

class SpecialistInput(StrictModel):
    predicate: SpecialistPredicate
    subject_id: str
    scope_id: str
    coverage_state: CoverageState = "unknown"
    source_role: Literal["supporting", "corroborating", "context"]
    epistemic_basis: EpistemicBasis
    evidence_locator_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    observation_time: ObservationTime | None = None
    detail: str | None = None
    taxonomy_id: str | None = None
    taxonomy_version: str | None = None
    concept_id: str | None = None
    assignment_status: AssignmentStatus | None = None
    method: str | None = None
    value: CanonicalValue | None = None

    @field_validator("subject_id", "scope_id", "detail", "taxonomy_id", "taxonomy_version", "concept_id", "method")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(value) != len(set(value)):
            raise ValueError("specialist identifiers must be nonblank and unique")
        return value

    @model_validator(mode="after")
    def _shape(self) -> "SpecialistInput":
        if self.coverage_state in {"asserted_none", "observed_absent"}:
            raise ValueError("substantive absence is not specialist missingness")
        if self.coverage_state == "supported" and (not self.evidence_locator_ids or not self.source_record_ids or not self.lineage_ids or self.observation_time is None):
            raise ValueError("supported specialist propositions require locator, source, lineage and time")
        classification = {"source_reported_classification_observed", "assessed_classification_observed"}
        if self.predicate in classification:
            if not all((self.taxonomy_id, self.taxonomy_version, self.concept_id, self.assignment_status, self.method)):
                raise ValueError("classification requires taxonomy identity, version, concept, status and method")
            expected = "source_fact" if self.predicate == "source_reported_classification_observed" else "governed_event"
            if self.epistemic_basis != expected:
                raise ValueError(f"{self.predicate} requires epistemic_basis {expected}")
        elif any(x is not None for x in (self.taxonomy_id, self.taxonomy_version, self.concept_id, self.assignment_status)):
            raise ValueError("taxonomy fields are limited to classification predicates")
        elif self.predicate == "discovery_signal_observed" and self.epistemic_basis != "source_fact":
            raise ValueError("discovery signals require source_fact basis")
        elif self.predicate in {"ethos_self_description_observed", "commitment_stated_observed", "claimed_implementation_observed"} and self.epistemic_basis != "source_interpretation":
            raise ValueError("self-described ethos and claims require source_interpretation")
        elif self.predicate in {"activity_observed", "fundraising_practice_observed", "fundraising_campaign_observed", "ethos_affiliation_observed", "observed_practice_observed", "verified_completion_observed"} and self.epistemic_basis != "source_fact":
            raise ValueError("observed facts require source_fact basis")
        if self.predicate != "discovery_signal_observed" and self.method is not None and self.predicate not in classification:
            raise ValueError("method is limited to classification and discovery predicates")
        return self

def _payload(item: SpecialistInput) -> dict[str, CanonicalValue]:
    result: dict[str, CanonicalValue] = {"north_star_projection_contract": "north-star-v0.2", "section_id": _SECTION[item.predicate], "specialist_predicate": item.predicate, "coverage_state": item.coverage_state, "source_role": item.source_role, "epistemic_basis": item.epistemic_basis}
    for key in ("detail", "taxonomy_id", "taxonomy_version", "concept_id", "assignment_status", "method", "value"):
        value = getattr(item, key)
        if value is not None: result[key] = value
    return result

def project_specialist_observation(item: SpecialistInput, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    section = _SECTION[item.predicate]
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=(item.subject_id,), subject_id=item.subject_id, scope_id=item.scope_id,
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=x) for x in item.lineage_ids),
        predicate=f"north_star_v02.section{section}.{item.predicate}", value=_payload(item), outcome_state="supported" if item.coverage_state == "supported" else "unknown",
        evidence_locator_ids=item.evidence_locator_ids, source_record_ids=item.source_record_ids, observation_time=item.observation_time or ObservationTime(observed_at=created_at), method="north_star_v02_specialist_reprojection")

def specialist_card_evidence(item: SpecialistInput, observation: Observation) -> CardEvidence:
    section = _SECTION[item.predicate]
    if (observation.subject_id != item.subject_id or observation.about_subject_ids != (item.subject_id,) or observation.scope_id != item.scope_id or observation.predicate != f"north_star_v02.section{section}.{item.predicate}" or observation.value != _payload(item) or observation.outcome_state != ("supported" if item.coverage_state == "supported" else "unknown") or observation.evidence_locator_ids != item.evidence_locator_ids or observation.source_record_ids != item.source_record_ids or observation.observation_time != item.observation_time or observation.method != "north_star_v02_specialist_reprojection"):
        raise ValueError("specialist CardEvidence requires matching projected observation")
    if tuple(x.target_artifact_id for x in observation.lineage if x.edge_type == "projected_as") != item.lineage_ids:
        raise ValueError("specialist CardEvidence requires matching lineage")
    return CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(section,), projection_contract_id="north-star-v0.2", note=f"v0.2-only {item.predicate}; no cross-section propagation")

def specialist_missingness(*, subject_id: str, section_id: Literal[4, 8, 15, 19], coverage_state: CoverageState, note: str | None = None) -> CoverageInput:
    try: state, basis = _MISSING[coverage_state]
    except KeyError as exc: raise ValueError("specialist missingness requires non-positive coverage state") from exc
    return CoverageInput(subject_id=subject_id, section_id=section_id, projection_contract_id="north-star-v0.2", state=state, basis=basis, note=note)
