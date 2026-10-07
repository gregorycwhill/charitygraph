"""Section 15/17 bounded domain contracts for the active North Star v0.3.

These contracts preserve what a source says and where it applies.  They are
adapters into the shared observation envelope, not a taxonomy, score, or a
mechanism for transferring propositions between related subjects.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import field_validator, model_validator

from .contracts.common import CanonicalValue, LineageEdge, ProducerRef, StrictModel, require_nonblank
from .contracts.ids import deterministic_id
from .contracts.knowledge import Observation, ObservationTime
from .integrated_card import CardEvidence, CoverageInput

ProjectionIdentity = Literal["north-star-v0.3"]
EthosRole = Literal["self_described", "formal_affiliation", "external_characterisation", "historical_orientation"]
HistoryFamily = Literal[
    "founding", "founder", "institutional_milestone", "merger", "split", "succession",
    "program_or_campaign", "public_inquiry_or_review", "recognition_or_award",
    "movement_or_network_context", "notable_person_relationship",
]
HistorySourceRole = Literal["discovery", "supporting", "corroborating"]
EventStatus = Literal["reported", "occurred", "announced", "completed", "ongoing", "uncertain"]


def _ids(value: tuple[str, ...], label: str) -> tuple[str, ...]:
    if not value or any(not item.strip() for item in value) or len(value) != len(set(value)):
        raise ValueError(f"{label} must be nonempty, nonblank and unique")
    return value


class EthosObservation(StrictModel):
    """One source-faithful ethos proposition at its lowest evidenced scope."""
    projection_contract_id: ProjectionIdentity = "north-star-v0.3"
    subject_id: str
    scope_id: str
    epistemic_role: EthosRole
    descriptor: str
    source_role: Literal["supporting", "corroborating", "context"]
    evidence_locator_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    lineage_ids: tuple[str, ...]
    observation_time: ObservationTime
    qualification: str | None = None
    material_disagreement: str | None = None

    @field_validator("subject_id", "scope_id", "descriptor", "qualification", "material_disagreement")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids")
    @classmethod
    def _identifiers(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        return _ids(value, info.field_name)


class NotableEvent(StrictModel):
    """A dated, bounded history event; not a quality or adverse-matter record."""
    projection_contract_id: ProjectionIdentity = "north-star-v0.3"
    candidate_id: str
    subject_id: str
    scope_id: str
    event_family: HistoryFamily
    statement: str
    event_date: date | datetime | None = None
    event_date_qualification: str | None = None
    source_retrieved_at: datetime | None = None
    source_roles: tuple[HistorySourceRole, ...]
    evidence_locator_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    lineage_ids: tuple[str, ...]
    related_subject_id: str | None = None
    relationship_kind: Literal["predecessor", "successor", "parent", "affiliate", "network", "person", "other"] | None = None
    procedural_status: EventStatus | None = None
    qualification: str | None = None
    uncertainty: str | None = None
    observation_time: ObservationTime

    @field_validator("candidate_id", "subject_id", "scope_id", "statement", "event_date_qualification", "related_subject_id", "relationship_kind", "procedural_status", "qualification", "uncertainty")
    @classmethod
    def _text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("source_roles")
    @classmethod
    def _roles(cls, value: tuple[HistorySourceRole, ...]) -> tuple[HistorySourceRole, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("source_roles must be nonempty and unique")
        return value

    @field_validator("evidence_locator_ids", "source_record_ids", "lineage_ids")
    @classmethod
    def _identifiers(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        return _ids(value, info.field_name)

    @model_validator(mode="after")
    def _bounded_event(self) -> "NotableEvent":
        expected = notable_event_candidate_id(
            subject_id=self.subject_id, scope_id=self.scope_id, event_family=self.event_family,
            event_date=self.event_date, statement=self.statement, related_subject_id=self.related_subject_id,
        )
        if self.candidate_id != expected:
            raise ValueError("candidate_id must match deterministic event identity")
        if self.relationship_kind is None and self.related_subject_id is not None:
            raise ValueError("related_subject_id requires relationship_kind")
        if self.relationship_kind is not None and self.related_subject_id is None:
            raise ValueError("relationship_kind requires related_subject_id")
        if self.event_family in {"merger", "split", "succession"} and self.related_subject_id is None:
            raise ValueError("lineage event requires an explicitly related subject")
        if self.event_family == "public_inquiry_or_review" and self.procedural_status is None:
            raise ValueError("inquiry/review occurrence requires procedural_status")
        return self


def notable_event_candidate_id(*, subject_id: str, scope_id: str, event_family: HistoryFamily, event_date: date | datetime | None, statement: str, related_subject_id: str | None) -> str:
    """Deterministic candidate identity collapses repeated descriptions of one event."""
    return deterministic_id("candidate:", {
        "contract": "notable-event-v1", "subject_id": subject_id, "scope_id": scope_id,
        "event_family": event_family, "event_date": event_date.isoformat() if event_date else None,
        "statement": statement, "related_subject_id": related_subject_id,
    })


def project_ethos_observation(item: EthosObservation, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=(item.subject_id,), subject_id=item.subject_id, scope_id=item.scope_id,
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=value) for value in item.lineage_ids),
        predicate=f"north_star_v03.section15.ethos.{item.epistemic_role}", value={"projection_contract_id": item.projection_contract_id, "descriptor": item.descriptor, "epistemic_role": item.epistemic_role, "source_role": item.source_role, "qualification": item.qualification, "material_disagreement": item.material_disagreement}, outcome_state="supported", evidence_locator_ids=item.evidence_locator_ids, source_record_ids=item.source_record_ids, observation_time=item.observation_time, qualifications=tuple(x for x in (item.qualification, item.material_disagreement) if x), method="ethos-v1-adapter")


def project_notable_event(item: NotableEvent, *, record_id: str, created_at: datetime, producer: ProducerRef | dict) -> Observation:
    value: dict[str, CanonicalValue] = {"projection_contract_id": item.projection_contract_id, "candidate_id": item.candidate_id, "event_family": item.event_family, "statement": item.statement, "source_roles": list(item.source_roles)}
    for key in ("event_date", "event_date_qualification", "source_retrieved_at", "related_subject_id", "relationship_kind", "procedural_status", "qualification", "uncertainty"):
        field = getattr(item, key)
        if field is not None: value[key] = field
    return Observation(record_id=record_id, created_at=created_at, producer=producer, about_subject_ids=tuple(x for x in (item.subject_id, item.related_subject_id) if x), subject_id=item.subject_id, scope_id=item.scope_id,
        lineage=tuple(LineageEdge(edge_type="projected_as", source_artifact_id=record_id, target_artifact_id=value) for value in item.lineage_ids), predicate=f"north_star_v03.section17.notable_event.{item.event_family}", value=value, outcome_state="supported", evidence_locator_ids=item.evidence_locator_ids, source_record_ids=item.source_record_ids, observation_time=item.observation_time, qualifications=tuple(x for x in (item.event_date_qualification, item.qualification, item.uncertainty) if x), method="notable-event-v1-adapter")


def v03_card_evidence(observation: Observation, *, section_id: Literal[15, 17]) -> CardEvidence:
    if not observation.predicate.startswith(f"north_star_v03.section{section_id}."):
        raise ValueError("section evidence must be projected by the matching v0.3 domain adapter")
    return CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(section_id,), projection_contract_id="north-star-v0.3", note="bounded v0.3 domain projection; no cross-section inference")


def v03_missingness(*, subject_id: str, section_id: Literal[15, 17], state: Literal["not_found", "source_silent", "source_unavailable", "not_acquired", "not_processed", "processing_failed", "not_reviewed", "not_attempted", "not_applicable", "withheld", "unknown", "stale"], note: str | None = None) -> CoverageInput:
    mapping = {"not_found": ("NOT_FOUND", "unknown_history"), "source_silent": ("SOURCE_SILENT", "processed_source_silent"), "source_unavailable": ("SOURCE_UNAVAILABLE", "source_unavailable"), "not_acquired": ("NOT_ACQUIRED", "not_acquired"), "not_processed": ("NOT_PROCESSED", "no_domain_result"), "processing_failed": ("PROCESSING_FAILED", "processing_failed"), "not_reviewed": ("NOT_REVIEWED", "not_reviewed"), "not_attempted": ("NOT_ATTEMPTED", "not_attempted"), "not_applicable": ("NOT_APPLICABLE", "not_applicable"), "withheld": ("WITHHELD", "withheld"), "unknown": ("UNKNOWN", "unknown_history"), "stale": ("STALE", "unknown_history")}
    mapped = mapping[state]
    return CoverageInput(subject_id=subject_id, section_id=section_id, projection_contract_id="north-star-v0.3", state=mapped[0], basis=mapped[1], note=note)
