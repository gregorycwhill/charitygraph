"""Versioned source-role contract for fundraising semantic observations.

This is deliberately a validator, not a prose classifier.  An upstream
governed extractor supplies source-native assertions and this module ensures a
source can promote only the facets its role is permitted to evidence.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EvidenceRole = Literal[
    "first_party_practice_page", "first_party_campaign_page",
    "annual_report_statement", "regulator_registration", "pfra_membership",
    "agency_provider_case_evidence", "agency_client_directory",
    "platform_campaign_page", "industry_record", "procurement_or_job_evidence",
    "scoped_source_inventory", "other",
]
Facet = Literal[
    "practice", "campaign", "setting", "channel", "provider",
    "commitment_pattern", "currentness",
]
Binding = Literal["confirmed", "ambiguous", "unresolved"]
ReviewStatus = Literal["not_reviewed", "reviewed", "rejected"]
Coverage = Literal[
    "observed", "not_found_in_scoped_source", "not_available_from_source",
    "not_processed",
]
Promotion = Literal["promotable", "review_only", "blocked", "coverage_only"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceScope(_Strict):
    kind: Literal["organisation", "organisation_group", "program", "campaign", "geography", "unknown"] = "unknown"
    identifier: str | None = None
    geography: str | None = None
    description: str | None = None


class FundraisingEvidence(_Strict):
    """Structured extractor output retaining the evidence needed for review."""

    contract_version: Literal["fundraising-evidence-roles-v1"] = "fundraising-evidence-roles-v1"
    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_role: EvidenceRole
    locator: str = Field(min_length=1)
    source_wording: str = Field(min_length=1)
    subject_binding: Binding
    binding_basis: str = Field(min_length=1)
    observed_at: date
    valid_from: date | None = None
    valid_to: date | None = None
    scope: EvidenceScope = Field(default_factory=EvidenceScope)
    production_method: Literal["direct_extract", "deterministic_parse", "governed_semantic_inference"]
    review_status: ReviewStatus = "not_reviewed"
    coverage: Coverage = "observed"
    coverage_description: str | None = None
    asserted_facets: tuple[Facet, ...] = ()

    @model_validator(mode="after")
    def complete_and_ordered(self):
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from cannot follow valid_to")
        if self.coverage == "not_found_in_scoped_source":
            if self.asserted_facets:
                raise ValueError("scoped source silence cannot assert fundraising facets")
            if not self.coverage_description:
                raise ValueError("scoped source silence requires a coverage description")
        if self.coverage != "observed" and self.asserted_facets:
            raise ValueError("unobserved coverage cannot assert fundraising facets")
        if "currentness" in self.asserted_facets and not (self.valid_from or self.valid_to):
            raise ValueError("currentness requires source-supplied valid time")
        unsupported = set(self.asserted_facets) - _ROLE_FACETS[self.source_role]
        if unsupported:
            raise ValueError(f"{self.source_role} cannot support facets: {sorted(unsupported)}")
        return self


# This is a claim-family permission matrix, never a scalar trust score.  Roles
# with an empty set can still be retained as membership, registration, search or
# research evidence, but cannot produce a fundraising-practice observation.
_ROLE_FACETS: dict[EvidenceRole, frozenset[Facet]] = {
    "first_party_practice_page": frozenset({"practice", "setting", "channel", "commitment_pattern", "currentness"}),
    "first_party_campaign_page": frozenset({"campaign", "setting", "channel", "commitment_pattern", "currentness"}),
    "annual_report_statement": frozenset({"practice", "campaign", "setting", "channel", "commitment_pattern"}),
    "regulator_registration": frozenset(),
    "pfra_membership": frozenset(),
    "agency_provider_case_evidence": frozenset({"provider", "practice", "setting", "channel", "commitment_pattern", "currentness"}),
    "agency_client_directory": frozenset({"provider"}),
    "platform_campaign_page": frozenset({"campaign", "channel", "commitment_pattern", "currentness"}),
    "industry_record": frozenset(),
    "procurement_or_job_evidence": frozenset(),
    "scoped_source_inventory": frozenset(),
    "other": frozenset(),
}


class EvidenceRoleDecision(_Strict):
    evidence_id: str
    promotion: Promotion
    supported_facets: tuple[Facet, ...] = ()
    reason: str


def assess_fundraising_evidence(evidence: FundraisingEvidence) -> EvidenceRoleDecision:
    """Apply mechanical non-inference gates to one already-extracted record."""
    if evidence.coverage == "not_found_in_scoped_source":
        return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="coverage_only",
            reason="scoped source silence records search coverage, not practice absence")
    if evidence.subject_binding != "confirmed":
        return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="blocked",
            reason="subject binding is not confirmed; no fundraising facet is promoted")
    if evidence.source_role == "pfra_membership":
        return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="blocked",
            reason="PFRA membership supports membership only, never F2F practice or currentness")
    if evidence.source_role == "regulator_registration":
        return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="blocked",
            reason="regulator registration or permitted-method information does not evidence a fundraising practice")
    if not evidence.asserted_facets:
        return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="review_only",
            reason="source retained but contains no promotable fundraising facet")
    if evidence.review_status != "reviewed":
        return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="review_only",
            supported_facets=evidence.asserted_facets,
            reason="role permits these facets, but review is required before promotion")
    return EvidenceRoleDecision(evidence_id=evidence.evidence_id, promotion="promotable",
        supported_facets=evidence.asserted_facets,
        reason="confirmed binding, role-permitted facets, complete provenance and reviewed extraction")
