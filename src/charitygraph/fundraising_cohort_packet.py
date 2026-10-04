"""Fail-closed local validation for a future real-source fundraising cohort.

This module neither retrieves nor stores source material.  It validates a
manually retained review packet so that a future rights-cleared cohort can be
measured without treating fixture descriptions as evidence.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


COHORT_PACKET_VERSION = "1.0"
CoverageStatus = Literal["observed", "not_found_in_scoped_source", "not_processed", "unavailable"]
AssertionDisposition = Literal["retained", "edited", "rejected", "refused"]
AssertionKind = Literal["practice", "f2f_currentness", "campaign", "provider_relationship", "finance_compatibility", "money_linkage"]
RightsDisposition = Literal["rights_cleared_for_review_retention", "source_terms_recorded_research_only", "blocked_by_rights", "not_processed"]
ErrorClass = Literal["identity_binding", "f2f_status_time", "scope", "campaign_practice", "provider_direction_time", "finance_entity_period_basis", "exact_grain_linkage", "contradiction", "scoped_silence", "finance_only", "incompatible_finance"]


class RetainedSource(BaseModel):
    source_id: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    source_native_wording: str = Field(min_length=1)
    rights_disposition: RightsDisposition
    observed_on: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def require_usable_rights_for_retained_source(self):
        if self.rights_disposition != "rights_cleared_for_review_retention":
            raise ValueError("retained packet source requires rights cleared for review retention")
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("source valid time is reversed")
        return self


class FundraisingPacketAssertion(BaseModel):
    assertion_id: str = Field(min_length=1)
    kind: AssertionKind
    source_id: str = Field(min_length=1)
    subject_binding_basis: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    production_method: Literal["direct_source_claim", "deterministic_parsing", "governed_semantic_inference"]
    review_status: Literal["independently_adjudicated", "reviewed", "research_only"]
    coverage_status: CoverageStatus
    disposition: AssertionDisposition
    error_class: ErrorClass | None = None
    finance_entity_id: str | None = None
    finance_period_start: date | None = None
    finance_period_end: date | None = None
    finance_basis: str | None = None
    same_source_exact_grain: bool | None = None

    @model_validator(mode="after")
    def retain_refusals_and_gate_finance(self):
        if self.coverage_status == "observed" and self.disposition == "refused":
            raise ValueError("an observed assertion cannot be refused")
        if self.coverage_status != "observed" and self.disposition == "retained":
            raise ValueError("a non-observed assertion cannot be retained")
        if self.disposition in {"edited", "rejected", "refused"} and not self.error_class:
            raise ValueError("non-retained assertion requires an error class")
        if self.kind == "finance_compatibility":
            if not all((self.finance_entity_id, self.finance_period_start, self.finance_period_end, self.finance_basis)):
                raise ValueError("finance compatibility assertion requires entity, period and basis")
            if self.finance_period_end < self.finance_period_start:
                raise ValueError("finance assertion period is reversed")
        if self.kind == "money_linkage":
            if self.same_source_exact_grain is None:
                raise ValueError("money linkage assertion requires exact-grain result")
            if self.disposition == "retained" and not self.same_source_exact_grain:
                raise ValueError("retained money linkage requires same-source exact-grain evidence")
        return self


class FundraisingCohortCase(BaseModel):
    case_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    identity_adjudication: Literal["confirmed", "ambiguous", "rejected"]
    sources: list[RetainedSource] = Field(default_factory=list)
    assertions: list[FundraisingPacketAssertion] = Field(default_factory=list)

    @model_validator(mode="after")
    def bind_assertions_to_retained_sources(self):
        source_ids = {source.source_id for source in self.sources}
        if not self.sources:
            raise ValueError("source-backed cohort case requires retained source metadata")
        if not self.assertions:
            raise ValueError("source-backed cohort case requires assertions")
        if any(assertion.source_id not in source_ids for assertion in self.assertions):
            raise ValueError("assertion source_id must be present in the case sources")
        if self.identity_adjudication != "confirmed" and any(a.disposition == "retained" for a in self.assertions):
            raise ValueError("ambiguous or rejected identity cannot retain an assertion")
        return self


class FundraisingCohortPacket(BaseModel):
    contract_version: str = COHORT_PACKET_VERSION
    packet_id: str = Field(min_length=1)
    packet_status: Literal["not_processed", "ready_for_independent_review"]
    source_backed: bool
    fixture_only: bool
    cases: list[FundraisingCohortCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def distinguish_template_from_evidence(self):
        if self.packet_status == "not_processed":
            if self.cases or self.source_backed or self.fixture_only:
                raise ValueError("not_processed packet is an empty template, not evidence")
        else:
            if not self.source_backed or self.fixture_only:
                raise ValueError("review packet must be source-backed and cannot be fixture-only")
            if not self.cases:
                raise ValueError("review packet requires source-backed cases")
            if any(
                assertion.review_status != "independently_adjudicated"
                for case in self.cases for assertion in case.assertions
            ):
                raise ValueError("review packet requires independently adjudicated assertions")
        return self


class CohortPacketLedger(BaseModel):
    packet_id: str
    packet_status: str
    case_denominator: int
    assertion_denominators: dict[str, int]
    dispositions: dict[str, int]
    error_classes: dict[str, int]
    is_external_quality_measurement: bool


def build_cohort_packet_ledger(packet: FundraisingCohortPacket) -> CohortPacketLedger:
    """Report assertion denominators separately from cases; set no quality rate."""
    assertions = [assertion for case in packet.cases for assertion in case.assertions]
    return CohortPacketLedger(
        packet_id=packet.packet_id,
        packet_status=packet.packet_status,
        case_denominator=len(packet.cases),
        assertion_denominators=dict(Counter(assertion.kind for assertion in assertions)),
        dispositions=dict(Counter(assertion.disposition for assertion in assertions)),
        error_classes=dict(Counter(assertion.error_class for assertion in assertions if assertion.error_class)),
        is_external_quality_measurement=packet.packet_status == "ready_for_independent_review",
    )
