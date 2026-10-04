"""Versioned, fail-closed compatibility checks for fundraising money facts.

This module deliberately does not map wording to a metric.  An extractor or
reviewer supplies the source-preserved wording and the selected measurement
kind; this gate only decides whether two already-typed observations may be
added for one deterministic calculation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import FinancialPeriod, MoneyObservation


FINANCE_MEASUREMENT_COMPATIBILITY_VERSION = "1.0"

FundraisingMeasureKind = Literal[
    "amount_raised", "gross_proceeds", "donations_received", "cash_received",
    "pledged", "ticket_sales", "merchandise_sales", "sponsorship_revenue",
    "platform_processed_amount", "recognised_revenue", "direct_fundraising_cost",
    "agency_fee", "commission", "media_spend", "staff_cost", "event_prize_cost",
    "administration_allocation", "total_fundraising_cost",
]
ReportingScope = Literal["subject", "organisation_group", "consolidated_group", "unknown"]
RecognitionBasis = Literal["cash", "accrual", "revenue_recognition", "unknown"]
GrossNetBasis = Literal["gross", "net", "not_applicable", "unknown"]
GstTreatment = Literal["inclusive", "exclusive", "not_applicable", "unknown"]
PassThroughTreatment = Literal["included", "excluded", "not_applicable", "unknown"]
CostAttribution = Literal["direct", "allocated", "not_applicable", "unknown"]
AllocationMethod = Literal[
    "direct_source_reported", "source_reported_functional_allocation",
    "deterministic_reconstruction", "not_applicable", "unknown",
]
SourceRole = Literal["audited_financial_statement", "regulator_return", "organisation_disclosure", "platform_report", "unknown"]
Assurance = Literal["audited", "reviewed", "unaudited", "unknown"]


class FundraisingMoneyMeasurement(BaseModel):
    """One source-native money fact prepared for compatibility assessment.

    ``source_wording`` is retained even where ``measure_kind`` is selected by
    a governed mapping.  Unknown semantic dimensions are valid observations,
    but are never compatible with another observation for addition.
    """

    observation_id: str = Field(min_length=1)
    amount: MoneyObservation
    measure_kind: FundraisingMeasureKind
    source_wording: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    period: FinancialPeriod
    reporting_scope: ReportingScope
    reporting_subject_causebase_id: str | None = None
    consolidation_scope_id: str | None = None
    recognition_basis: RecognitionBasis = "unknown"
    gross_net_basis: GrossNetBasis = "unknown"
    gst_treatment: GstTreatment = "unknown"
    pass_through_treatment: PassThroughTreatment = "unknown"
    cost_attribution: CostAttribution = "not_applicable"
    allocation_basis: str | None = None
    allocation_method: AllocationMethod = "unknown"
    amount_is_approximate: bool | None = None
    source_role: SourceRole = "unknown"
    assurance: Assurance = "unknown"
    fundraising_activity_id: str | None = None
    # A source-supported statement grouping. It is not inferred from labels.
    aggregation_set_id: str | None = None
    component_is_disjoint: bool = False

    @model_validator(mode="after")
    def require_scope_identity_and_allocation_basis(self):
        if self.reporting_scope == "subject" and not self.reporting_subject_causebase_id:
            raise ValueError("subject reporting scope requires reporting_subject_causebase_id")
        if self.reporting_scope in {"organisation_group", "consolidated_group"} and not self.consolidation_scope_id:
            raise ValueError("group reporting scope requires consolidation_scope_id")
        if self.cost_attribution == "allocated" and not self.allocation_basis:
            raise ValueError("allocated cost requires source allocation_basis")
        if self.cost_attribution != "allocated" and self.allocation_basis:
            raise ValueError("allocation_basis is only valid for allocated cost")
        if self.cost_attribution == "allocated" and self.allocation_method == "unknown":
            raise ValueError("allocated cost requires allocation_method")
        if self.allocation_method == "deterministic_reconstruction" and self.amount_is_approximate is None:
            raise ValueError("deterministic reconstruction requires approximation status")
        return self


CompatibilityStatus = Literal["compatible", "incompatible"]


class CompatibilityDecision(BaseModel):
    contract_version: str = FINANCE_MEASUREMENT_COMPATIBILITY_VERSION
    status: CompatibilityStatus
    reasons: list[str] = Field(default_factory=list)

    @property
    def safe_to_add(self) -> bool:
        return self.status == "compatible"


def _period_key(period: FinancialPeriod) -> tuple[object, object, object] | None:
    # Labels such as "FY25" are not sufficient evidence that reporting periods
    # align. Exact dates plus a stated length prevent accidental annualisation.
    if not period.period_start or not period.period_end or not period.period_length_days:
        return None
    return period.period_start, period.period_end, period.period_length_days


def decide_addition_compatibility(
    left: FundraisingMoneyMeasurement, right: FundraisingMoneyMeasurement
) -> CompatibilityDecision:
    """Return a deterministic, explainable decision; missing metadata fails closed."""

    reasons: list[str] = []
    if left.observation_id == right.observation_id:
        reasons.append("same_observation")
    if left.measure_kind != right.measure_kind:
        reasons.append("different_measure_kind")
    if left.amount.normalised_currency != right.amount.normalised_currency:
        reasons.append("different_currency")
    if _period_key(left.period) is None or _period_key(right.period) is None:
        reasons.append("period_not_exactly_identified")
    elif _period_key(left.period) != _period_key(right.period):
        reasons.append("different_period")
    for field in ("reporting_scope", "recognition_basis", "gross_net_basis", "gst_treatment", "pass_through_treatment", "cost_attribution", "allocation_method", "amount_is_approximate"):
        left_value, right_value = getattr(left, field), getattr(right, field)
        if "unknown" in (left_value, right_value):
            reasons.append(f"{field}_unknown")
        elif left_value != right_value:
            reasons.append(f"different_{field}")
    if left.reporting_scope == "subject":
        if left.reporting_subject_causebase_id != right.reporting_subject_causebase_id:
            reasons.append("different_reporting_subject")
    elif left.consolidation_scope_id != right.consolidation_scope_id:
        reasons.append("different_consolidation_scope")
    if left.cost_attribution == "allocated" and left.allocation_basis != right.allocation_basis:
        reasons.append("different_allocation_basis")
    if left.fundraising_activity_id != right.fundraising_activity_id:
        reasons.append("different_fundraising_activity")
    if not left.aggregation_set_id or left.aggregation_set_id != right.aggregation_set_id:
        reasons.append("no_shared_source_aggregation_set")
    if not left.component_is_disjoint or not right.component_is_disjoint:
        reasons.append("component_disjointness_not_evidenced")
    return CompatibilityDecision(status="compatible" if not reasons else "incompatible", reasons=reasons)
