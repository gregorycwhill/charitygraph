"""Fail-closed, nominal historical comparisons for fundraising money facts.

This module deliberately keeps a historical series distinct from addition:
facts from different reporting periods must never be supplied to the
same-period aggregation gate.  It preserves every reported/restated fact and
only exposes a change where the two source facts describe a stable,
like-for-like annual measurement.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .fundraising_finance_source_contract import FundraisingFinanceSourceObservation


FUNDRAISING_FINANCE_HISTORY_VERSION = "1.0"
HistoryComparability = Literal["comparable", "discontinuity", "not_comparable"]


class HistoricalFundraisingMoneyObservation(BaseModel):
    """A source fact plus source/reviewer-supplied change metadata.

    ``classification_id`` must identify the source-supported line definition,
    not a keyword-derived category.  A restatement is retained as a separate
    fact; it is never silently substituted for the originally reported value.
    """

    source_fact: FundraisingFinanceSourceObservation
    classification_id: str | None = None
    restates_observation_id: str | None = None
    reporting_entity_changed: bool = False
    accounting_policy_changed: bool = False
    comparison_note: str | None = None

    @model_validator(mode="after")
    def require_observed_fact_and_restatement_target(self):
        if self.source_fact.coverage_status != "observed":
            raise ValueError("history contains observed source facts only; retain scoped non-results separately")
        if self.restates_observation_id == self.source_fact.observation_id:
            raise ValueError("a restatement cannot target itself")
        return self


class FundraisingHistoryComparison(BaseModel):
    """An adjacent-period comparison, with an explicit discontinuity reason."""

    left_observation_id: str
    right_observation_id: str
    status: HistoryComparability
    reasons: list[str] = Field(default_factory=list)
    nominal_change: Decimal | None = None
    nominal_change_fraction: Decimal | None = None


class FundraisingMoneyHistory(BaseModel):
    contract_version: str = FUNDRAISING_FINANCE_HISTORY_VERSION
    observations: list[HistoricalFundraisingMoneyObservation]
    comparisons: list[FundraisingHistoryComparison]
    nominal_amounts: bool = True


def _annual_period_key(entry: HistoricalFundraisingMoneyObservation) -> tuple[int, int] | None:
    period = entry.source_fact.measurement.period
    if not period.period_start or not period.period_end or not period.period_length_days:
        return None
    if period.is_transitional_or_nonstandard:
        return None
    # A normal annual report may contain a leap day.  Other durations require
    # an explicit non-comparable treatment rather than annualisation.
    if period.period_length_days not in {365, 366}:
        return None
    return period.period_start.month, period.period_start.day


def compare_historical_observations(
    left: HistoricalFundraisingMoneyObservation,
    right: HistoricalFundraisingMoneyObservation,
) -> FundraisingHistoryComparison:
    """Compare two different annual periods only when all material semantics align."""

    left_m, right_m = left.source_fact.measurement, right.source_fact.measurement
    reasons: list[str] = []
    if left_m.observation_id == right_m.observation_id:
        reasons.append("same_measurement")
    if left_m.measure_kind != right_m.measure_kind:
        reasons.append("different_measure_kind")
    if left_m.amount.normalised_currency != right_m.amount.normalised_currency:
        reasons.append("different_currency")
    if _annual_period_key(left) is None or _annual_period_key(right) is None:
        reasons.append("nonstandard_or_inexact_reporting_period")
    else:
        if _annual_period_key(left) != _annual_period_key(right):
            reasons.append("different_reporting_year_anchor")
        if left_m.period.period_start >= right_m.period.period_start:
            reasons.append("periods_not_chronological")
    for field in (
        "reporting_scope", "recognition_basis", "gross_net_basis", "gst_treatment",
        "pass_through_treatment", "cost_attribution", "allocation_method", "amount_is_approximate",
    ):
        left_value, right_value = getattr(left_m, field), getattr(right_m, field)
        if "unknown" in (left_value, right_value):
            reasons.append(f"{field}_unknown")
        elif left_value != right_value:
            reasons.append(f"different_{field}")
    if left_m.reporting_scope == "subject":
        if left_m.reporting_subject_causebase_id != right_m.reporting_subject_causebase_id:
            reasons.append("different_reporting_subject")
    elif left_m.consolidation_scope_id != right_m.consolidation_scope_id:
        reasons.append("different_consolidation_scope")
    if left.source_fact.scope_kind != right.source_fact.scope_kind or left.source_fact.scope_id != right.source_fact.scope_id:
        reasons.append("different_finance_scope")
    if left.classification_id is None or right.classification_id is None:
        reasons.append("classification_not_identified")
    elif left.classification_id != right.classification_id:
        reasons.append("classification_changed")
    if left.reporting_entity_changed or right.reporting_entity_changed:
        reasons.append("reporting_entity_changed")
    if left.accounting_policy_changed or right.accounting_policy_changed:
        reasons.append("accounting_policy_changed")
    if left.restates_observation_id or right.restates_observation_id:
        reasons.append("restatement_present")
    status: HistoryComparability = "comparable" if not reasons else "discontinuity"
    if status == "comparable":
        change = right_m.amount.normalised_amount - left_m.amount.normalised_amount
        fraction = None if left_m.amount.normalised_amount == 0 else change / left_m.amount.normalised_amount
        return FundraisingHistoryComparison(
            left_observation_id=left.source_fact.observation_id, right_observation_id=right.source_fact.observation_id,
            status=status, nominal_change=change, nominal_change_fraction=fraction,
        )
    return FundraisingHistoryComparison(
        left_observation_id=left.source_fact.observation_id, right_observation_id=right.source_fact.observation_id,
        status=status, reasons=list(dict.fromkeys(reasons)),
    )


def build_fundraising_money_history(
    observations: list[HistoricalFundraisingMoneyObservation],
) -> FundraisingMoneyHistory:
    """Return a source-preserving chronology and comparisons between neighbours.

    The supplied facts are not deduplicated: a restatement, classification
    shift or entity change is material evidence and remains visible.
    """
    ordered = sorted(
        observations,
        key=lambda item: (
            item.source_fact.measurement.period.period_start is None,
            item.source_fact.measurement.period.period_start,
            item.source_fact.observation_id,
        ),
    )
    return FundraisingMoneyHistory(
        observations=ordered,
        comparisons=[compare_historical_observations(a, b) for a, b in zip(ordered, ordered[1:])],
    )
