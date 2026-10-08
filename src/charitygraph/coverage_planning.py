"""Central, provider-free coverage-gap planning for semantic consumers.

This contract records what central acquisition assessed.  It is not evidence,
does not assert a negative fact, and intentionally has no locator or fetch API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts.ids import deterministic_id

CoverageState = Literal[
    "not_found_in_assessed_captures",
    "source_family_not_captured",
    "retrieval_or_representation_failure",
    "not_yet_processed",
]


class CoverageAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_id: str = Field(min_length=1)
    section_id: Literal[15, 17]
    claim_family: str = Field(min_length=1)
    state: CoverageState
    reason: str = Field(min_length=1)
    assessed_source_scope: tuple[str, ...] = ()
    assessed_at: datetime | None = None
    provenance: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _scope_is_explicit(self) -> "CoverageAssessment":
        if any(not item.strip() for item in self.assessed_source_scope + self.provenance):
            raise ValueError("coverage assessment scope and provenance must be nonblank")
        return self


class SourceOpportunity(BaseModel):
    """A deduplicated request for central acquisition planning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str
    subject_id: str = Field(min_length=1)
    section_id: Literal[15, 17]
    desired_source_family: str = Field(min_length=1)
    desired_claim_family: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    current_assessed_source_scope: tuple[str, ...] = ()
    current_assessed_at: datetime | None = None
    provenance: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _identity(self) -> "SourceOpportunity":
        expected = deterministic_id("requestitem:", {
            "subject_id": self.subject_id,
            "section_id": self.section_id,
            "desired_source_family": self.desired_source_family,
            "desired_claim_family": self.desired_claim_family,
        })
        if self.opportunity_id != expected:
            raise ValueError("opportunity_id must be deterministic")
        return self


def route_coverage_gap(assessment: CoverageAssessment, *, desired_source_family: str) -> SourceOpportunity:
    """Turn an assessment into a central opportunity; never acquire or discover."""
    return SourceOpportunity(
        opportunity_id=deterministic_id("requestitem:", {
            "subject_id": assessment.subject_id,
            "section_id": assessment.section_id,
            "desired_source_family": desired_source_family,
            "desired_claim_family": assessment.claim_family,
        }),
        subject_id=assessment.subject_id,
        section_id=assessment.section_id,
        desired_source_family=desired_source_family,
        desired_claim_family=assessment.claim_family,
        reason=assessment.reason,
        current_assessed_source_scope=assessment.assessed_source_scope,
        current_assessed_at=assessment.assessed_at,
        provenance=assessment.provenance,
    )


__all__ = ["CoverageAssessment", "CoverageState", "SourceOpportunity", "route_coverage_gap"]
