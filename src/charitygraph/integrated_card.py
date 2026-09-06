"""Reusable, provenance-preserving assembly for a private North-Star card.

This is a projection/assembly primitive, not a semantic extractor.  Callers
must provide already identified subjects, scopes, observations and section
assignments.  In particular, an empty section is represented as missingness,
never as a negative assertion.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts.knowledge import Observation, RelationshipStatement, ScopeRecord, SubjectRecord


SECTION_TITLES: dict[int, str] = {
    1: "Identity & regulatory status", 2: "Purpose, mandate & cause",
    3: "Programs, services, projects & campaigns", 4: "Populations & beneficiaries",
    5: "Geography", 6: "Participation", 7: "Fundraising & resource mobilisation",
    8: "Finance & resource flows", 9: "Governance", 10: "Workforce",
    11: "Capability, capacity, access & availability", 12: "Relationships & ecosystem",
    13: "Memberships, schemes, registrations & accreditations", 14: "Ethos & institutional identity",
    15: "Positions, commitments & implementation", 16: "Conduct, adverse matters & compliance",
    17: "Notable context & institutional history", 18: "Outcomes, impact & evaluation",
    19: "Classifications & semantic lenses", 20: "Evidence, coverage, freshness & corrections",
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
    assignment_contract: AssignmentContract = "CANONICAL_COMPATIBLE"
    note: str | None = None

    @model_validator(mode="after")
    def valid_sections(self) -> "CardEvidence":
        if any(section not in SECTION_TITLES for section in self.section_ids):
            raise ValueError("section_ids must be North-Star sections 1..20")
        if len(set(self.section_ids)) != len(self.section_ids):
            raise ValueError("section_ids must be unique")
        if self.assignment_contract == "UNRESOLVED" and self.section_ids:
            raise ValueError("unresolved historical assignments cannot be projected by numeric section ID")
        if self.assignment_contract == "LEGACY_COMPATIBLE_SUBSET" and any(section > 8 for section in self.section_ids):
            raise ValueError("legacy-compatible subset only permits unchanged sections 1..8")
        return self


class CoverageInput(_Strict):
    subject_id: str
    section_id: int = Field(ge=1, le=20)
    state: Missingness
    basis: CoverageBasis
    note: str | None = None

    @model_validator(mode="after")
    def state_has_basis(self) -> "CoverageInput":
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
    title: str
    observation_ids: tuple[str, ...] = ()
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
        if len({item.observation_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("each observation has one integration disposition")
        if any(item.source_subject_id not in subject_ids or item.target_subject_id not in subject_ids for item in self.relationships):
            raise ValueError("relationships must reference durable subjects")
        if any(item.subject_id not in subject_ids for item in self.coverage_inputs):
            raise ValueError("coverage inputs must reference durable subjects")
        return self


def compile_coverage(graph: IntegratedGraph, *, subject_id: str | None = None) -> tuple[SectionCoverage, ...]:
    """Compile a reproducible coverage matrix from explicit assignments."""
    if subject_id is None:
        subject_ids = {item.subject_id for item in graph.subjects}
        if len(subject_ids) != 1:
            raise ValueError("subject_id is required to compile multi-subject coverage")
        subject_id = next(iter(subject_ids))
    observation_ids = {item.record_id for item in graph.observations if item.subject_id == subject_id}
    evidence = [item for item in graph.evidence if item.observation_id in observation_ids]
    explicit = {item.section_id: item for item in graph.coverage_inputs if item.subject_id == subject_id}
    result: list[SectionCoverage] = []
    for section_id, title in SECTION_TITLES.items():
        assigned = [item for item in evidence if section_id in item.section_ids]
        ids = tuple(item.observation_id for item in assigned)
        counts: dict[str, int] = {}
        for item in assigned:
            counts[item.disposition] = counts.get(item.disposition, 0) + 1
        if ids:
            missingness: Missingness = "GOVERNED_PRESENT" if all(item.disposition == "REUSABLE_GOVERNED" for item in assigned) else "EXPERIMENTAL_REVIEW"
            basis = "observed_present"
        else:
            item = explicit.get(section_id)
            if item is None:
                missingness, basis = "UNKNOWN", "unknown_history"
            else:
                missingness, basis = item.state, item.basis
        result.append(SectionCoverage(section_id=section_id, title=title, observation_ids=ids, missingness=missingness, disposition_counts=counts, basis=basis))
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
        coverage_inputs=tuple(item for item in graph.coverage_inputs if item.subject_id == subject_id),
    ), subject_id=subject_id)
    return {
        "subject_id": subject_id,
        "observation_ids": tuple(item.record_id for item in graph.observations if item.subject_id == subject_id),
        "relationship_ids": tuple(item.record_id for item in graph.relationships if item.source_subject_id == subject_id or item.target_subject_id == subject_id),
        "sections": tuple(item.model_dump(mode="json") for item in coverage),
    }


def compile_matrix(graph: IntegratedGraph) -> tuple[dict[str, object], ...]:
    """Return canonical section rows with one explicit cell per subject."""
    rows: list[dict[str, object]] = []
    for section_id, title in SECTION_TITLES.items():
        cells = []
        for subject in graph.subjects:
            coverage = compile_coverage(graph, subject_id=subject.subject_id)[section_id - 1]
            cells.append({"subject_id": subject.subject_id, "subject_name": subject.display_name, "status": coverage.missingness, "observation_count": len(coverage.observation_ids), "basis": coverage.basis})
        rows.append({"section_id": section_id, "title": title, "cells": tuple(cells)})
    return tuple(rows)


__all__ = ["SECTION_TITLES", "CardEvidence", "CoverageInput", "IntegratedGraph", "SectionCoverage", "compile_coverage", "compile_matrix", "project_subject"]
