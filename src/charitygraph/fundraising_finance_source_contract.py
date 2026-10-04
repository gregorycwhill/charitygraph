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


FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION = "1.0"
FinanceSourceFamily = Literal[
    "annual_report_or_financial_statements", "acnc_or_nscoa_return",
    "state_fundraising_disclosure", "campaign_report", "platform_report",
    "provider_record", "organisation_disclosure",
]
FinanceScopeKind = Literal["organisation", "campaign"]
ComponentTreatment = Literal["direct", "allocated", "possible", "excluded"]
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
        if self.scope_kind == "campaign" and not self.measurement.fundraising_activity_id:
            raise ValueError("campaign scope requires source-supported fundraising_activity_id")
        return self


class FinanceSourceCompatibilityDecision(BaseModel):
    contract_version: str = FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION
    status: Literal["compatible", "incompatible"]
    reasons: list[str] = Field(default_factory=list)
    measurement_decision: CompatibilityDecision

    @property
    def safe_to_add(self) -> bool:
        return self.status == "compatible"


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
