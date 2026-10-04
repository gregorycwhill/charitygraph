"""Source-native envelope for governed fundraising finance observations.

This layer deliberately accepts already typed money measurements.  It never
reads a label to choose a financial meaning; it retains the source wording,
locator and binding that a governed extractor or reviewer supplied.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .finance_measurement import (
    CompatibilityDecision,
    FundraisingMoneyMeasurement,
    decide_addition_compatibility,
)


FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION = "1.1"
FinanceSourceFamily = Literal[
    "annual_report_or_financial_statements", "acnc_or_nscoa_return",
    "state_fundraising_disclosure", "campaign_report", "platform_report",
    "provider_record", "organisation_disclosure",
]
# The source can expressly name a scope below the reporting entity.  This is
# deliberately a scope declaration supplied by the extractor/reviewer, not a
# classification of nearby prose.
FinanceScopeKind = Literal[
    "organisation", "fundraising_portfolio", "practice", "campaign", "appeal",
    "provider_relationship",
]
ComponentTreatment = Literal["direct", "allocated", "possible", "excluded"]
EnvelopeKind = Literal["direct_disclosure", "deterministic_reconstruction", "bounds_or_share_candidate"]
AdditivityOutcome = Literal["confirmed_additive", "not_additive", "not_applicable", "not_processed"]
RightsDisposition = Literal[
    "rights_cleared_for_review_retention", "source_terms_recorded_research_only",
    "blocked_by_rights", "not_processed",
]
ProductionMethod = Literal["direct_source_claim", "deterministic_parsing", "governed_semantic_inference"]
ReviewStatus = Literal["reviewed", "automation_governed", "research_only"]
CoverageStatus = Literal["observed", "not_found_in_scoped_source", "not_processed", "unavailable"]


class FundraisingFinanceSourceObservation(BaseModel):
    """A reviewable source fact, intentionally distinct from a derived result."""

    observation_id: str = Field(min_length=1)
    measurement: FundraisingMoneyMeasurement
    source_family: FinanceSourceFamily
    source_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    source_native_wording: str = Field(min_length=1)
    subject_binding_basis: str = Field(min_length=1)
    scope_kind: FinanceScopeKind
    scope_id: str = Field(min_length=1)
    component_treatment: ComponentTreatment
    production_method: ProductionMethod
    review_status: ReviewStatus
    coverage_status: CoverageStatus
    observed_on: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    geography: str | None = None
    setting: str | None = None
    missingness_note: str | None = None

    @model_validator(mode="after")
    def retain_source_and_scope_semantics(self):
        if self.coverage_status == "observed" and self.missingness_note:
            raise ValueError("observed source fact cannot carry a missingness note")
        if self.coverage_status != "observed" and not self.missingness_note:
            raise ValueError("non-observed source state requires a missingness note")
        if self.component_treatment == "direct" and self.measurement.cost_attribution not in {"direct", "not_applicable"}:
            raise ValueError("direct component conflicts with allocated measurement")
        if self.component_treatment == "allocated" and self.measurement.cost_attribution != "allocated":
            raise ValueError("allocated component requires allocated measurement")
        if self.scope_kind == "organisation":
            expected = self.measurement.reporting_subject_causebase_id
            if self.measurement.reporting_scope != "subject" or not expected or self.scope_id != expected:
                raise ValueError("organisation scope must retain the subject reporting entity")
        if self.scope_kind in {"campaign", "appeal"} and not self.measurement.fundraising_activity_id:
            raise ValueError("campaign or appeal scope requires source-supported fundraising_activity_id")
        return self


class FinanceSourceCompatibilityDecision(BaseModel):
    contract_version: str = FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION
    status: Literal["compatible", "incompatible"]
    reasons: list[str] = Field(default_factory=list)
    measurement_decision: CompatibilityDecision

    @property
    def safe_to_add(self) -> bool:
        return self.status == "compatible"


class FundraisingFinanceEvidenceEnvelope(BaseModel):
    """Preflight packet for a finance fact before it reaches a money result.

    This is deliberately an evidence envelope, not a calculator.  In
    particular a complete bounds/share candidate is still returned as
    unavailable: CharityGraph has no authorised generic share, net-proceeds
    or effectiveness derivative.
    """

    contract_version: str = FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION
    envelope_id: str = Field(min_length=1)
    envelope_kind: EnvelopeKind
    reporting_entity_id: str = Field(min_length=1)
    period_start: date
    period_end: date
    recognition_basis: str = Field(min_length=1)
    metric_flow_meaning: str = Field(min_length=1)
    gross_net_treatment: str = Field(min_length=1)
    denominator_locator: str = Field(min_length=1)
    additivity_outcome: AdditivityOutcome
    rights_disposition: RightsDisposition
    definite_components: list[FundraisingFinanceSourceObservation] = Field(default_factory=list)
    possible_components: list[FundraisingFinanceSourceObservation] = Field(default_factory=list)
    excluded_components: list[FundraisingFinanceSourceObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_complete_and_truthful_components(self):
        components = self.definite_components + self.possible_components + self.excluded_components
        if not components:
            raise ValueError("finance evidence envelope requires source components")
        if self.period_end < self.period_start:
            raise ValueError("finance evidence envelope period is reversed")
        for component in self.definite_components:
            if component.component_treatment not in {"direct", "allocated"}:
                raise ValueError("definite components must be direct or allocated")
        for component in self.possible_components:
            if component.component_treatment != "possible":
                raise ValueError("possible components must be explicitly marked possible")
        for component in self.excluded_components:
            if component.component_treatment != "excluded":
                raise ValueError("excluded components must be explicitly marked excluded")
        for component in components:
            measurement = component.measurement
            if component.coverage_status != "observed":
                raise ValueError("finance evidence envelope components must be observed")
            if measurement.reporting_subject_causebase_id != self.reporting_entity_id:
                raise ValueError("component reporting entity differs from envelope")
            if measurement.period.period_start != self.period_start or measurement.period.period_end != self.period_end:
                raise ValueError("component period differs from envelope")
            if measurement.recognition_basis != self.recognition_basis:
                raise ValueError("component recognition basis differs from envelope")
            if measurement.gross_net_basis != self.gross_net_treatment:
                raise ValueError("component gross/net treatment differs from envelope")
        if self.envelope_kind in {"direct_disclosure", "deterministic_reconstruction"}:
            if not self.definite_components:
                raise ValueError("direct disclosure or reconstruction requires definite components")
            if self.additivity_outcome == "not_processed":
                raise ValueError("direct disclosure or reconstruction requires an additivity outcome")
        if self.envelope_kind == "deterministic_reconstruction" and self.additivity_outcome != "confirmed_additive":
            raise ValueError("deterministic reconstruction requires confirmed additivity")
        if self.envelope_kind == "bounds_or_share_candidate":
            if not (self.definite_components and self.possible_components and self.excluded_components):
                raise ValueError("bounds/share candidate requires definite, possible and excluded components")
            if self.rights_disposition in {"blocked_by_rights", "not_processed"}:
                raise ValueError("bounds/share candidate requires an explicit usable rights disposition")
        return self


class FinanceEvidenceEnvelopePreflight(BaseModel):
    """A non-deriving disposition for a validated evidence envelope."""

    envelope_id: str
    outcome: Literal["available_direct_disclosure", "available_reconstruction", "unavailable"]
    reason: str


def preflight_finance_evidence_envelope(
    envelope: FundraisingFinanceEvidenceEnvelope,
) -> FinanceEvidenceEnvelopePreflight:
    """Classify only direct/reconstruction readiness; never calculate a derivative."""

    if envelope.envelope_kind == "bounds_or_share_candidate":
        return FinanceEvidenceEnvelopePreflight(
            envelope_id=envelope.envelope_id, outcome="unavailable",
            reason="bounds_or_share_derivation_not_authorised",
        )
    if envelope.rights_disposition in {"blocked_by_rights", "not_processed"}:
        return FinanceEvidenceEnvelopePreflight(
            envelope_id=envelope.envelope_id, outcome="unavailable", reason=envelope.rights_disposition,
        )
    if envelope.envelope_kind == "direct_disclosure":
        return FinanceEvidenceEnvelopePreflight(
            envelope_id=envelope.envelope_id, outcome="available_direct_disclosure",
            reason="direct_source_components_retained",
        )
    return FinanceEvidenceEnvelopePreflight(
        envelope_id=envelope.envelope_id, outcome="available_reconstruction",
        reason="deterministic_components_confirmed_additive",
    )


def decide_finance_source_addition_compatibility(
    left: FundraisingFinanceSourceObservation, right: FundraisingFinanceSourceObservation
) -> FinanceSourceCompatibilityDecision:
    """Fail closed before adding source observations.

    Possible and excluded components belong in a separately governed bounds
    envelope, never in deterministic addition.  This rule prevents a source
    row being promoted into an asserted expense merely because it is nearby.
    """

    measurement_decision = decide_addition_compatibility(left.measurement, right.measurement)
    reasons = list(measurement_decision.reasons)
    if left.observation_id == right.observation_id:
        reasons.append("same_source_observation")
    if left.coverage_status != "observed" or right.coverage_status != "observed":
        reasons.append("source_fact_not_observed")
    if left.scope_kind != right.scope_kind:
        reasons.append("different_finance_scope_kind")
    if left.scope_id != right.scope_id:
        reasons.append("different_finance_scope")
    if left.component_treatment != right.component_treatment:
        reasons.append("different_component_treatment")
    if left.component_treatment in {"possible", "excluded"} or right.component_treatment in {"possible", "excluded"}:
        reasons.append("non_deterministic_component_treatment")
    return FinanceSourceCompatibilityDecision(
        status="compatible" if not reasons else "incompatible",
        reasons=list(dict.fromkeys(reasons)),
        measurement_decision=measurement_decision,
    )
