"""Fail-closed fundraising financial derivatives, never performance metrics.

The inputs are already source-preserved measurements.  This module only
performs arithmetic after exact entity, period and accounting-basis checks.
It deliberately has no ROI, cost-to-raise, donor-acquisition, LTV, channel
effectiveness, or causal-revenue output type.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, model_validator

from .finance_measurement import FundraisingMoneyMeasurement
from .v05.models import Amount
from .v05.fundraising import AttributionComponent, FundraisingBounds, calculate_bounds


DERIVATIVE_CONTRACT_VERSION = "1.0"
ExpenseMethod = Literal["direct_disclosure", "functional_allocation_reconstruction", "defensible_bounds", "unavailable"]
_COST_KINDS = {"direct_fundraising_cost", "agency_fee", "commission", "media_spend", "staff_cost", "event_prize_cost", "administration_allocation", "total_fundraising_cost"}


class FundraisingExpenseResult(BaseModel):
    contract_version: str = DERIVATIVE_CONTRACT_VERSION
    method: ExpenseMethod
    source_measurement_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    amount: Amount | None = None
    bounds: FundraisingBounds | None = None
    unavailable_reason: str | None = None
    approximate: bool = False

    @model_validator(mode="after")
    def one_safe_representation(self):
        if self.method == "defensible_bounds":
            if self.bounds is None or self.amount is not None or self.unavailable_reason:
                raise ValueError("bounds method requires bounds only")
        elif self.method == "unavailable":
            if self.amount is not None or self.bounds is not None or not self.unavailable_reason:
                raise ValueError("unavailable result requires an explicit reason and no value")
        elif self.amount is None or self.bounds is not None or self.unavailable_reason:
            raise ValueError("expense result requires one disclosed or reconstructed amount")
        if self.method != "unavailable" and (not self.source_measurement_ids or not self.evidence_ids):
            raise ValueError("available expense requires measurement and evidence provenance")
        return self


class DerivedMoneyResult(BaseModel):
    """A safely labelled amount, not an assessment of fundraising performance."""
    contract_version: str = DERIVATIVE_CONTRACT_VERSION
    kind: Literal["fundraising_cost_share", "net_proceeds"]
    amount: Amount
    numerator_measurement_id: str
    denominator_or_cost_measurement_id: str
    evidence_ids: tuple[str, ...]
    formula: Literal[
        "fundraising_cost / compatible_total_expenses",
        "compatible_gross_proceeds - compatible_fundraising_cost",
    ]
    approximate: bool = False


def _amount(measurement: FundraisingMoneyMeasurement) -> Amount:
    return Amount(amount=str(measurement.amount.normalised_amount), currency=measurement.amount.normalised_currency)


def direct_expense(measurement: FundraisingMoneyMeasurement) -> FundraisingExpenseResult:
    if measurement.measure_kind not in {"direct_fundraising_cost", "total_fundraising_cost"}:
        raise ValueError("measurement is not a directly disclosed fundraising expense")
    if measurement.cost_attribution != "direct" or measurement.allocation_method != "direct_source_reported":
        raise ValueError("direct expense requires direct source-reported attribution")
    if measurement.amount_is_approximate:
        raise ValueError("direct expense cannot be marked approximate")
    return FundraisingExpenseResult(method="direct_disclosure", source_measurement_ids=(measurement.observation_id,), evidence_ids=tuple(measurement.evidence_ids), amount=_amount(measurement))


def reconstructed_functional_expense(measurement: FundraisingMoneyMeasurement) -> FundraisingExpenseResult:
    if measurement.measure_kind not in _COST_KINDS or measurement.cost_attribution != "allocated":
        raise ValueError("functional reconstruction requires an allocated fundraising cost")
    if measurement.allocation_method not in {"source_reported_functional_allocation", "deterministic_reconstruction"}:
        raise ValueError("functional reconstruction requires a governed allocation method")
    if measurement.amount_is_approximate is None:
        raise ValueError("functional reconstruction requires approximation status")
    return FundraisingExpenseResult(method="functional_allocation_reconstruction", source_measurement_ids=(measurement.observation_id,), evidence_ids=tuple(measurement.evidence_ids), amount=_amount(measurement), approximate=measurement.amount_is_approximate)


def bounded_expense(components: list[AttributionComponent], *, evidence_ids: tuple[str, ...]) -> FundraisingExpenseResult:
    if not components or not evidence_ids:
        raise ValueError("bounds require components and evidence provenance")
    return FundraisingExpenseResult(method="defensible_bounds", source_measurement_ids=tuple(c.observation_id for c in components), evidence_ids=evidence_ids, bounds=calculate_bounds(components))


def unavailable_expense(reason: str) -> FundraisingExpenseResult:
    return FundraisingExpenseResult(method="unavailable", unavailable_reason=reason)


def _compatible(left: FundraisingMoneyMeasurement, right: FundraisingMoneyMeasurement) -> None:
    reasons: list[str] = []
    if left.amount.normalised_currency != right.amount.normalised_currency: reasons.append("different_currency")
    if (left.period.period_start, left.period.period_end, left.period.period_length_days) != (right.period.period_start, right.period.period_end, right.period.period_length_days) or not left.period.period_start or not right.period.period_start: reasons.append("different_or_unknown_period")
    if left.reporting_scope != right.reporting_scope or left.reporting_scope == "unknown": reasons.append("different_or_unknown_reporting_scope")
    if left.reporting_scope == "subject" and left.reporting_subject_causebase_id != right.reporting_subject_causebase_id: reasons.append("different_reporting_subject")
    if left.reporting_scope != "subject" and left.consolidation_scope_id != right.consolidation_scope_id: reasons.append("different_consolidation_scope")
    for field in ("recognition_basis", "gst_treatment", "pass_through_treatment"):
        a, b = getattr(left, field), getattr(right, field)
        if "unknown" in (a, b) or a != b: reasons.append(f"different_or_unknown_{field}")
    if reasons: raise ValueError("incompatible measurements: " + ", ".join(reasons))


def fundraising_cost_share(cost: FundraisingMoneyMeasurement, total_expenses: FundraisingMoneyMeasurement) -> DerivedMoneyResult:
    if cost.measure_kind not in _COST_KINDS or total_expenses.measure_kind != "total_expenses":
        raise ValueError("cost share requires a fundraising cost and explicitly typed total expense denominator")
    _compatible(cost, total_expenses)
    denominator = total_expenses.amount.normalised_amount
    if denominator == 0: raise ValueError("cost share denominator cannot be zero")
    return DerivedMoneyResult(kind="fundraising_cost_share", amount=Amount(amount=str(cost.amount.normalised_amount / denominator), currency="ratio"), numerator_measurement_id=cost.observation_id, denominator_or_cost_measurement_id=total_expenses.observation_id, evidence_ids=tuple(dict.fromkeys(cost.evidence_ids + total_expenses.evidence_ids)), formula="fundraising_cost / compatible_total_expenses", approximate=bool(cost.amount_is_approximate or total_expenses.amount_is_approximate))


def net_proceeds(gross_proceeds: FundraisingMoneyMeasurement, cost: FundraisingMoneyMeasurement, *, subtraction_permitted_by_source_contract: bool) -> DerivedMoneyResult:
    if gross_proceeds.measure_kind != "gross_proceeds" or gross_proceeds.gross_net_basis != "gross":
        raise ValueError("net proceeds requires explicitly gross proceeds")
    if cost.measure_kind not in _COST_KINDS:
        raise ValueError("net proceeds requires an explicitly typed fundraising cost")
    if not subtraction_permitted_by_source_contract or "unknown" in (gross_proceeds.source_role, cost.source_role):
        raise ValueError("net proceeds requires source/contract permission for subtraction")
    _compatible(gross_proceeds, cost)
    return DerivedMoneyResult(kind="net_proceeds", amount=Amount(amount=str(gross_proceeds.amount.normalised_amount - cost.amount.normalised_amount), currency=gross_proceeds.amount.normalised_currency), numerator_measurement_id=gross_proceeds.observation_id, denominator_or_cost_measurement_id=cost.observation_id, evidence_ids=tuple(dict.fromkeys(gross_proceeds.evidence_ids + cost.evidence_ids)), formula="compatible_gross_proceeds - compatible_fundraising_cost", approximate=bool(gross_proceeds.amount_is_approximate or cost.amount_is_approximate))
