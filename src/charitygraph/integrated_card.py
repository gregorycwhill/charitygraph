"""Reusable, provenance-preserving assembly for a private North-Star card.

This is a projection/assembly primitive, not a semantic extractor.  Callers
must provide already identified subjects, scopes, observations and section
assignments.  In particular, an empty section is represented as missingness,
never as a negative assertion.
"""
from __future__ import annotations

from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts.knowledge import Observation, RelationshipStatement, ScopeRecord, SubjectRecord


SECTION_TITLES: dict[int, str] = {
    1: "Identity & regulatory status", 2: "Purpose, mandate & cause",
    3: "Programs, services, projects & campaigns", 4: "Populations & beneficiaries",
    5: "Geography", 6: "Participation", 7: "Fundraising & resource mobilisation",
    8: "Finance & resource flows", 9: "People, workforce & volunteering",
    10: "Governance, accountability & conduct", 11: "Capability, infrastructure & access",
    12: "Networks, partners & ecosystem", 13: "Evidence, transparency & information quality",
    14: "Technology, data & digital access", 15: "Communications & public presence",
    16: "Advocacy, policy & systems change", 17: "Risk, safeguarding & complaints",
    18: "Outcomes, evaluation & learning", 19: "Commitments, plans & future direction",
    20: "Cross-domain synthesis & open questions",
}

Disposition = Literal[
    "REUSABLE_GOVERNED", "REUSABLE_EXPERIMENTAL_INPUT", "DIAGNOSTIC_ONLY",
    "IDENTITY_OR_LINEAGE_UNRESOLVED", "NOT_AVAILABLE",
]
Missingness = Literal[
    "GOVERNED_PRESENT", "EXPERIMENTAL_REVIEW", "ASSERTED_NONE", "OBSERVED_ABSENT",
    "NOT_FOUND", "SOURCE_SILENT", "SOURCE_UNAVAILABLE", "NOT_ACQUIRED",
    "NOT_PROCESSED", "PROCESSING_FAILED", "NOT_REVIEWED", "NOT_APPLICABLE",
    "WITHHELD", "STALE", "UNKNOWN",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CardEvidence(_Strict):
    observation_id: str
    disposition: Disposition
    section_ids: tuple[int, ...] = ()
    note: str | None = None

    @model_validator(mode="after")
    def valid_sections(self) -> "CardEvidence":
        if any(section not in SECTION_TITLES for section in self.section_ids):
            raise ValueError("section_ids must be North-Star sections 1..20")
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("section_ids must be unique")
        return self


class SectionCoverage(_Strict):
    section_id: int = Field(ge=1, le=20)
    title: str
    observation_ids: tuple[str, ...] = ()
    missingness: Missingness
    disposition_counts: dict[str, int] = Field(default_factory=dict)


class IntegratedGraph(_Strict):
    subjects: tuple[SubjectRecord, ...]
    scopes: tuple[ScopeRecord, ...]
    observations: tuple[Observation, ...]
    relationships: tuple[RelationshipStatement, ...] = ()
    evidence: tuple[CardEvidence, ...]

    @model_validator(mode="after")
    def coherent(self) -> "IntegratedGraph":
        subject_ids = {item.subject_id for item in self.subjects}
        observation_ids = {item.record_id for item in self.observations}
        scope_ids = {item.record_id for item in self.scopes}
        if len(subject_ids) != len(self.subjects):
            raise ValueError("subjects must have unique durable subject IDs")
        if any(item.subject_id not in subject_ids for item in self.scopes):
            raise ValueError("every scope must belong to a durable subject")
        if any(item.subject_id not in subject_ids or (item.scope_id and item.scope_id not in scope_ids) for item in self.observations):
            raise ValueError("observations must reference durable subjects and scopes")
        if any(item.observation_id not in observation_ids for item in self.evidence):
            raise ValueError("card evidence must reference a retained observation")
        if len({item.observation_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("each observation has one integration disposition")
        if any(item.source_subject_id not in subject_ids or item.target_subject_id not in subject_ids for item in self.relationships):
            raise ValueError("relationships must reference durable subjects")
        return self


def compile_coverage(graph: IntegratedGraph) -> tuple[SectionCoverage, ...]:
    """Compile a reproducible coverage matrix from explicit assignments."""
    by_observation = {item.observation_id: item for item in graph.evidence}
    result: list[SectionCoverage] = []
    for section_id, title in SECTION_TITLES.items():
        assigned = [item for item in graph.evidence if section_id in item.section_ids]
        ids = tuple(item.observation_id for item in assigned)
        counts: dict[str, int] = {}
        for item in assigned:
            counts[item.disposition] = counts.get(item.disposition, 0) + 1
        if ids:
            missingness: Missingness = "GOVERNED_PRESENT" if all(item.disposition == "REUSABLE_GOVERNED" for item in assigned) else "EXPERIMENTAL_REVIEW"
        else:
            missingness = "SOURCE_SILENT"
        result.append(SectionCoverage(section_id=section_id, title=title, observation_ids=ids, missingness=missingness, disposition_counts=counts))
    return tuple(result)


def project_subject(graph: IntegratedGraph, subject_id: str) -> dict[str, object]:
    """Return one private card projection without copying observations."""
    if subject_id not in {item.subject_id for item in graph.subjects}:
        raise ValueError(f"unknown subject: {subject_id}")
    selected = {item.record_id for item in graph.observations if item.subject_id == subject_id}
    evidence = [item for item in graph.evidence if item.observation_id in selected]
    coverage = compile_coverage(IntegratedGraph(
        subjects=graph.subjects,
        scopes=tuple(item for item in graph.scopes if item.subject_id == subject_id),
        observations=tuple(item for item in graph.observations if item.subject_id == subject_id),
        relationships=tuple(item for item in graph.relationships if item.source_subject_id == subject_id or item.target_subject_id == subject_id),
        evidence=tuple(evidence),
    ))
    return {
        "subject_id": subject_id,
        "observation_ids": tuple(item.record_id for item in graph.observations if item.subject_id == subject_id),
        "relationship_ids": tuple(item.record_id for item in graph.relationships if item.source_subject_id == subject_id or item.target_subject_id == subject_id),
        "sections": tuple(item.model_dump(mode="json") for item in coverage),
    }


__all__ = ["SECTION_TITLES", "CardEvidence", "IntegratedGraph", "SectionCoverage", "compile_coverage", "project_subject"]
