"""Reusable, provenance-preserving assembly for a private North-Star card.

This is a projection/assembly primitive, not a semantic extractor.  Callers
must provide already identified subjects, scopes, observations and section
assignments.  In particular, an empty section is represented as missingness,
never as a negative assertion.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts.knowledge import Observation, RelationshipStatement, ScopeRecord, SubjectRecord


ProjectionContractId = Literal["north-star-v0.1", "north-star-v0.2"]


@dataclass(frozen=True)
class NorthStarProjectionContract:
    projection_contract_id: ProjectionContractId
    section_titles: Mapping[int, str]
    relationship_section_id: int

    def __post_init__(self) -> None:
        keys = tuple(self.section_titles)
        if keys != tuple(range(1, 21)):
            raise ValueError("North Star projection contracts must define sections 1 through 20 in order")
        if self.relationship_section_id not in self.section_titles:
            raise ValueError("relationship section must exist in the projection contract")


SECTION_TITLES_V0_1: Mapping[int, str] = MappingProxyType({
    1: "Identity & regulatory status", 2: "Purpose, mandate & cause",
    3: "Programs, services, projects & campaigns", 4: "Populations & beneficiaries",
    5: "Geography", 6: "Participation", 7: "Fundraising & resource mobilisation",
    8: "Finance & resource flows", 9: "Governance", 10: "Workforce",
    11: "Capability, capacity, access & availability", 12: "Relationships & ecosystem",
    13: "Memberships, schemes, registrations & accreditations", 14: "Ethos & institutional identity",
    15: "Positions, commitments & implementation", 16: "Conduct, adverse matters & compliance",
    17: "Notable context & institutional history", 18: "Outcomes, impact & evaluation",
    19: "Classifications & semantic lenses", 20: "Evidence, coverage, freshness & corrections",
})

SECTION_TITLES_VNEXT: Mapping[int, str] = MappingProxyType({
    1: "Identity / regulatory", 2: "Purpose / cause",
    3: "Programs / services", 4: "Activities / SDGs",
    5: "Geography / beneficiaries", 6: "Participation",
    7: "Direct service / capacity", 8: "Fundraising",
    9: "Governance / leadership", 10: "People / workforce",
    11: "Scale / capability", 12: "Relationships",
    13: "Finances", 14: "Funding / dependencies",
    15: "Ethos / values", 16: "Conduct / adverse",
    17: "Notable history", 18: "Evaluation / outcomes",
    19: "Classification / search / AI discovery",
    20: "Evidence / coverage / freshness / corrections",
})

NORTH_STAR_PROJECTION_V0_1 = NorthStarProjectionContract(
    projection_contract_id="north-star-v0.1",
    section_titles=SECTION_TITLES_V0_1,
    relationship_section_id=12,
)
NORTH_STAR_PROJECTION_VNEXT = NorthStarProjectionContract(
    projection_contract_id="north-star-v0.2",
    section_titles=SECTION_TITLES_VNEXT,
    relationship_section_id=12,
)
_PROJECTION_CONTRACTS = MappingProxyType({
    NORTH_STAR_PROJECTION_V0_1.projection_contract_id: NORTH_STAR_PROJECTION_V0_1,
    NORTH_STAR_PROJECTION_VNEXT.projection_contract_id: NORTH_STAR_PROJECTION_VNEXT,
})


def _contract_for_id(projection_contract_id: ProjectionContractId) -> NorthStarProjectionContract:
    return _PROJECTION_CONTRACTS[projection_contract_id]


def _registered_contract(contract: NorthStarProjectionContract) -> NorthStarProjectionContract:
    registered = _contract_for_id(contract.projection_contract_id)
    if contract != registered:
        raise ValueError("projection contract must exactly match a registered North Star version")
    return registered

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
CoverageBasis = Literal[
    "observed_present", "processed_source_silent", "no_domain_result",
    "unknown_history", "source_unavailable", "not_acquired", "not_reviewed",
    "not_applicable", "withheld",
]
AssignmentContract = Literal["CANONICAL_COMPATIBLE", "LEGACY_COMPATIBLE_SUBSET", "UNRESOLVED"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CardEvidence(_Strict):
    observation_id: str
    disposition: Disposition
    section_ids: tuple[int, ...] = ()
    # Unversioned historical records are bound to v0.1 by this compatibility
    # default. Active vNext assignments must opt into their version explicitly.
    projection_contract_id: ProjectionContractId = "north-star-v0.1"
    assignment_contract: AssignmentContract = "CANONICAL_COMPATIBLE"
    note: str | None = None

    @model_validator(mode="after")
    def valid_sections(self) -> "CardEvidence":
        contract = _contract_for_id(self.projection_contract_id)
        if any(section not in contract.section_titles for section in self.section_ids):
            raise ValueError(f"section_ids must exist in {self.projection_contract_id}")
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("section_ids must be unique")
        if self.assignment_contract == "UNRESOLVED" and self.section_ids:
            raise ValueError("unresolved historical assignments cannot be projected by numeric section ID")
        if self.projection_contract_id == "north-star-v0.1" and self.assignment_contract == "LEGACY_COMPATIBLE_SUBSET" and any(section > 8 for section in self.section_ids):
            raise ValueError("legacy-compatible subset only permits unchanged sections 1..8")
        return self


class CoverageInput(_Strict):
    subject_id: str
    section_id: int = Field(ge=1, le=20)
    projection_contract_id: ProjectionContractId = "north-star-v0.1"
    state: Missingness
    basis: CoverageBasis
    note: str | None = None

    @model_validator(mode="after")
    def state_has_basis(self) -> "CoverageInput":
        if self.section_id not in _contract_for_id(self.projection_contract_id).section_titles:
            raise ValueError(f"section_id must exist in {self.projection_contract_id}")
        required = {
            "SOURCE_SILENT": "processed_source_silent", "NOT_PROCESSED": "no_domain_result",
            "UNKNOWN": "unknown_history", "SOURCE_UNAVAILABLE": "source_unavailable",
            "NOT_ACQUIRED": "not_acquired", "NOT_REVIEWED": "not_reviewed",
            "NOT_APPLICABLE": "not_applicable", "WITHHELD": "withheld",
        }
        if self.state in required and self.basis != required[self.state]:
            raise ValueError(f"{self.state} requires basis {required[self.state]}")
        if self.state in {"GOVERNED_PRESENT", "EXPERIMENTAL_REVIEW"} and self.basis != "observed_present":
            raise ValueError(f"{self.state} requires basis observed_present")
        return self


class SectionCoverage(_Strict):
    section_id: int = Field(ge=1, le=20)
    projection_contract_id: ProjectionContractId
    title: str
    observation_ids: tuple[str, ...] = ()
    relationship_ids: tuple[str, ...] = ()
    missingness: Missingness
    disposition_counts: dict[str, int] = Field(default_factory=dict)
    basis: str | None = None


class IntegratedGraph(_Strict):
    subjects: tuple[SubjectRecord, ...]
    scopes: tuple[ScopeRecord, ...]
    observations: tuple[Observation, ...]
    relationships: tuple[RelationshipStatement, ...] = ()
    evidence: tuple[CardEvidence, ...]
    coverage_inputs: tuple[CoverageInput, ...] = ()

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
        assignment_keys = {(item.observation_id, item.projection_contract_id) for item in self.evidence}
        if len(assignment_keys) != len(self.evidence):
            raise ValueError("each observation may have one assignment per projection contract")
        if any(item.source_subject_id not in subject_ids or item.target_subject_id not in subject_ids for item in self.relationships):
            raise ValueError("relationships must reference durable subjects")
        if any(item.subject_id not in subject_ids for item in self.coverage_inputs):
            raise ValueError("coverage inputs must reference durable subjects")
        return self


def compile_coverage(
    graph: IntegratedGraph,
    *,
    projection_contract: NorthStarProjectionContract,
    subject_id: str | None = None,
) -> tuple[SectionCoverage, ...]:
    """Compile a reproducible coverage matrix from explicit assignments."""
    projection_contract = _registered_contract(projection_contract)
    if subject_id is None:
        subject_ids = {item.subject_id for item in graph.subjects}
        if len(subject_ids) != 1:
            raise ValueError("subject_id is required to compile multi-subject coverage")
        subject_id = next(iter(subject_ids))
    observation_ids = {item.record_id for item in graph.observations if item.subject_id == subject_id}
    evidence = [item for item in graph.evidence if item.observation_id in observation_ids and item.projection_contract_id == projection_contract.projection_contract_id]
    explicit = {
        item.section_id: item for item in graph.coverage_inputs
        if item.subject_id == subject_id and item.projection_contract_id == projection_contract.projection_contract_id
    }
    result: list[SectionCoverage] = []
    for section_id, title in projection_contract.section_titles.items():
        assigned = [item for item in evidence if section_id in item.section_ids]
        ids = tuple(item.observation_id for item in assigned)
        relationship_ids = tuple(item.record_id for item in graph.relationships if section_id == projection_contract.relationship_section_id and subject_id in {item.source_subject_id, item.target_subject_id})
        counts: dict[str, int] = {}
        for item in assigned:
            counts[item.disposition] = counts.get(item.disposition, 0) + 1
        if ids:
            missingness: Missingness = "GOVERNED_PRESENT" if all(item.disposition == "REUSABLE_GOVERNED" for item in assigned) else "EXPERIMENTAL_REVIEW"
            basis = "observed_present"
        elif relationship_ids:
            missingness = "EXPERIMENTAL_REVIEW" if any(item.status == "candidate" for item in graph.relationships if item.record_id in relationship_ids) else "GOVERNED_PRESENT"
            basis = "observed_present"
        else:
            item = explicit.get(section_id)
            if item is None:
                missingness, basis = "UNKNOWN", "unknown_history"
            else:
                missingness, basis = item.state, item.basis
        result.append(SectionCoverage(section_id=section_id, projection_contract_id=projection_contract.projection_contract_id, title=title, observation_ids=ids, relationship_ids=relationship_ids, missingness=missingness, disposition_counts=counts, basis=basis))
    return tuple(result)


def project_subject(
    graph: IntegratedGraph,
    subject_id: str,
    *,
    projection_contract: NorthStarProjectionContract,
) -> dict[str, object]:
    """Return one private card projection without copying observations."""
    projection_contract = _registered_contract(projection_contract)
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
        coverage_inputs=tuple(item for item in graph.coverage_inputs if item.subject_id == subject_id),
    ), subject_id=subject_id, projection_contract=projection_contract)
    return {
        "subject_id": subject_id,
        "projection_contract_id": projection_contract.projection_contract_id,
        "observation_ids": tuple(item.record_id for item in graph.observations if item.subject_id == subject_id),
        "relationship_ids": tuple(item.record_id for item in graph.relationships if item.source_subject_id == subject_id or item.target_subject_id == subject_id),
        "sections": tuple(item.model_dump(mode="json") for item in coverage),
    }


def compile_matrix(
    graph: IntegratedGraph,
    *,
    projection_contract: NorthStarProjectionContract,
) -> tuple[dict[str, object], ...]:
    """Return canonical section rows with one explicit cell per subject."""
    projection_contract = _registered_contract(projection_contract)
    rows: list[dict[str, object]] = []
    for section_id, title in projection_contract.section_titles.items():
        cells = []
        for subject in graph.subjects:
            coverage = compile_coverage(graph, subject_id=subject.subject_id, projection_contract=projection_contract)[section_id - 1]
            cells.append({"subject_id": subject.subject_id, "subject_name": subject.display_name, "status": coverage.missingness, "observation_count": len(coverage.observation_ids), "basis": coverage.basis})
        rows.append({"projection_contract_id": projection_contract.projection_contract_id, "section_id": section_id, "title": title, "cells": tuple(cells)})
    return tuple(rows)


__all__ = [
    "CardEvidence", "CoverageInput", "IntegratedGraph", "NORTH_STAR_PROJECTION_V0_1",
    "NORTH_STAR_PROJECTION_VNEXT", "NorthStarProjectionContract", "ProjectionContractId",
    "SECTION_TITLES_V0_1", "SECTION_TITLES_VNEXT", "SectionCoverage",
    "compile_coverage", "compile_matrix", "project_subject",
]
