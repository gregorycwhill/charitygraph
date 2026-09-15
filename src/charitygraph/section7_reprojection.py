"""Deterministic retained-evidence reprojection for North Star v0.2 section 7.

This module does not extract, reinterpret or promote evidence. It validates that
already-typed Direct Service propositions can be assigned only to the active
section-7 meaning while preserving their type, scope, locator and coverage
state.
"""
from __future__ import annotations

from typing import Literal

from .contracts.direct_service import CoverageState, DirectServiceProposition
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


__all__ = ["Section7Reprojection", "reproject_section7", "section7_missingness"]
