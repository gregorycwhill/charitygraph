"""Bounded v0.2 reprojection for C5 cross-cutting scope, time and epistemics."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.direct_service import CoverageState
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput

SectionC5Predicate = Literal[
    "identity_role_observed", "population_role_observed", "geography_role_observed",
    "governance_role_observed", "workforce_measure_observed", "historical_event_observed",
    "historical_interpretation_observed", "provenance_event_observed",
]
EpistemicBasis = Literal["source_fact", "source_interpretation", "governed_event"]
IdentityRole = Literal["legal_entity", "operating_organisation", "operating_unit", "branch", "brand", "former_name", "predecessor", "successor"]
PopulationRole = Literal["intended", "eligible", "reached", "served", "represented", "participating", "consulted", "mentioned", "affected"]
GeographyRole = Literal["registered", "administrative", "operating", "delivery", "catchment", "advertised", "funded", "program", "observed_reach"]
GovernanceRole = Literal["governing_body", "board_member", "responsible_person", "committee_member", "executive", "operational_governance", "service_governance"]
WorkforceRole = Literal["employee", "contractor", "labour_hire", "volunteer", "member", "placement", "partner_personnel", "mixed"]
WorkforceMeasure = Literal["headcount", "fte", "jobs", "hours"]
HistoricalEvent = Literal["founding", "rename", "merger", "split", "succession", "program", "campaign", "crisis", "inquiry", "milestone"]
ProvenanceEvent = Literal["source_correction", "source_supersession", "charitygraph_correction", "source_disagreement", "real_world_change"]

_SECTION = {"identity_role_observed": 1, "population_role_observed": 5, "geography_role_observed": 5,
            "governance_role_observed": 9, "workforce_measure_observed": 10, "historical_event_observed": 17,
            "historical_interpretation_observed": 17, "provenance_event_observed": 20}
_MISSINGNESS = {"not_found": ("NOT_FOUND", "unknown_history"), "source_silent": ("SOURCE_SILENT", "processed_source_silent"),
 "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"), "not_acquired": ("NOT_ACQUIRED", "not_acquired"),
 "not_processed": ("NOT_PROCESSED", "no_domain_result"), "not_reviewed": ("NOT_REVIEWED", "not_reviewed"),
 "processing_failed": ("PROCESSING_FAILED", "processing_failed"), "not_attempted": ("NOT_ATTEMPTED", "not_attempted"),
 "not_applicable": ("NOT_APPLICABLE", "not_applicable"), "withheld": ("WITHHELD", "withheld"), "stale": ("STALE", "unknown_history"), "unknown": ("UNKNOWN", "unknown_history")}

class SectionC5Input(StrictModel):
    predicate: SectionC5Predicate
    subject_id: str
    scope_id: str
    coverage_state: CoverageState = "unknown"
    source_role: Literal["supporting", "corroborating", "context"]
    epistemic_basis: EpistemicBasis
    evidence_locator_ids: tuple[str, ...] = ()
    source_record_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    observation_time: ObservationTime | None = None
    identity_role: IdentityRole | None = None
    population_role: PopulationRole | None = None
    geography_role: GeographyRole | None = None
    governance_role: GovernanceRole | None = None
    workforce_role: WorkforceRole | None = None
    workforce_measure: WorkforceMeasure | None = None
    event_type: HistoricalEvent | None = None
    provenance_event: ProvenanceEvent | None = None
    detail: str | None = None
    value: CanonicalValue | None = None

    @field_validator("subject_id", "scope_id", "detail")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids")
    @classmethod
    def _ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value) or len(set(value)) != len(value):
            raise ValueError("C5 identifiers must be nonblank and unique")
        return value

    @model_validator(mode="after")
    def _shape(self) -> "SectionC5Input":
        if self.coverage_state in {"asserted_none", "observed_absent"}:
            raise ValueError("substantive absence is not generic C5 missingness")
        if self.coverage_state == "supported" and (not self.evidence_locator_ids or not self.source_record_ids or not self.lineage_ids or self.observation_time is None):
            raise ValueError("supported C5 propositions require locator, source, lineage and time")
        if self.coverage_state == "supported" and self.predicate in {"identity_role_observed", "population_role_observed", "geography_role_observed", "governance_role_observed"} and self.detail is None and self.value is None:
            raise ValueError("supported C5 role propositions require substantive detail or value")
        needed = {"identity_role_observed": ("identity_role",), "population_role_observed": ("population_role",),
                  "geography_role_observed": ("geography_role",), "governance_role_observed": ("governance_role",),
                  "workforce_measure_observed": ("workforce_role", "workforce_measure", "value"),
                  "historical_event_observed": ("event_type", "detail"),
                  "historical_interpretation_observed": ("event_type", "detail"),
                  "provenance_event_observed": ("provenance_event", "detail")}[self.predicate]
        if any(getattr(self, name) is None for name in needed):
            raise ValueError(f"{self.predicate} requires {', '.join(needed)}")
        role_fields = {"identity_role", "population_role", "geography_role", "governance_role", "workforce_role", "workforce_measure", "event_type", "provenance_event"}
        permitted = set(needed)
        if self.predicate in {"population_role_observed", "geography_role_observed"}: permitted |= {"value", "detail"}
        if self.predicate == "workforce_measure_observed": permitted |= {"detail"}
        if self.predicate in {"historical_event_observed", "historical_interpretation_observed", "provenance_event_observed"}: permitted |= {"value"}
        if any(getattr(self, name) is not None for name in role_fields - permitted):
            raise ValueError("C5 semantic roles are limited to their own predicate")
        expected_basis = {
            "identity_role_observed": "source_fact", "population_role_observed": "source_fact",
            "geography_role_observed": "source_fact", "governance_role_observed": "source_fact",
            "workforce_measure_observed": "source_fact", "historical_event_observed": "source_fact",
            "historical_interpretation_observed": "source_interpretation",
        }.get(self.predicate)
        if expected_basis is not None and self.epistemic_basis != expected_basis:
            raise ValueError(f"{self.predicate} requires epistemic_basis {expected_basis}")
        if self.predicate == "provenance_event_observed":
            expected_basis = "governed_event" if self.provenance_event == "charitygraph_correction" else "source_fact"
            if self.epistemic_basis != expected_basis:
                raise ValueError(f"{self.provenance_event} requires epistemic_basis {expected_basis}")
        return self

def _payload(item: SectionC5Input) -> dict[str, CanonicalValue]:
    result: dict[str, CanonicalValue] = {"north_star_projection_contract": "north-star-v0.2", "section_id": _SECTION[item.predicate], "section_c5_predicate": item.predicate, "coverage_state": item.coverage_state, "source_role": item.source_role, "epistemic_basis": item.epistemic_basis}
    for key in ("identity_role", "population_role", "geography_role", "governance_role", "workforce_role", "workforce_measure", "event_type", "provenance_event", "detail", "value"):
        value = getattr(item, key)
        if value is not None: result[key] = value
    return result

def project_section_c5_observation(item: SectionC5Input, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    if item.observation_time is None:
        raise ValueError("C5 reprojection requires explicit observation_time; created_at is record metadata")
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=(item.subject_id,),
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=x) for x in item.lineage_ids),
        subject_id=item.subject_id, scope_id=item.scope_id, predicate=f"north_star_v02.section{_SECTION[item.predicate]}.{item.predicate}", value=_payload(item),
        outcome_state="supported" if item.coverage_state == "supported" else "unknown", evidence_locator_ids=item.evidence_locator_ids,
        source_record_ids=item.source_record_ids, observation_time=item.observation_time, method="north_star_v02_c5_reprojection")

def section_c5_card_evidence(item: SectionC5Input, observation: Observation) -> CardEvidence:
    expected_outcome = "supported" if item.coverage_state == "supported" else "unknown"
    section = _SECTION[item.predicate]
    if (observation.subject_id != item.subject_id or observation.about_subject_ids != (item.subject_id,)
        or observation.scope_id != item.scope_id or observation.predicate != f"north_star_v02.section{section}.{item.predicate}"
        or observation.outcome_state != expected_outcome or observation.value != _payload(item)
        or observation.evidence_locator_ids != item.evidence_locator_ids or observation.source_record_ids != item.source_record_ids
        or observation.observation_time != item.observation_time or observation.method != "north_star_v02_c5_reprojection"):
        raise ValueError("C5 CardEvidence requires matching projected observation")
    if tuple(edge.target_artifact_id for edge in observation.lineage if edge.edge_type == "projected_as") != item.lineage_ids:
        raise ValueError("C5 CardEvidence requires matching observation lineage")
    return CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(section,), projection_contract_id="north-star-v0.2", note=f"v0.2-only C5 {item.predicate}; no cross-section propagation")

def section_c5_missingness(*, subject_id: str, section_id: Literal[1, 5, 9, 10, 16, 17, 20], coverage_state: CoverageState, note: str | None = None) -> CoverageInput:
    try: state, basis = _MISSINGNESS[coverage_state]
    except KeyError as exc: raise ValueError("C5 missingness requires non-positive coverage state") from exc
    return CoverageInput(subject_id=subject_id, section_id=section_id, projection_contract_id="north-star-v0.2", state=state, basis=basis, note=note)

__all__ = ["SectionC5Input", "project_section_c5_observation", "section_c5_card_evidence", "section_c5_missingness"]
