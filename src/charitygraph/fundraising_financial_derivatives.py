"""Fail-closed fundraising financial derivatives, never performance metrics.

The inputs are already source-preserved measurements.  This module only
performs arithmetic after exact entity, period and accounting-basis checks.
It deliberately has no ROI, cost-to-raise, donor-acquisition, LTV, channel
effectiveness, or causal-revenue output type.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

from .finance_measurement import FundraisingMoneyMeasurement
from .v05.models import Amount
from .v05.fundraising import AttributionComponent, FundraisingBounds, calculate_bounds


DERIVATIVE_CONTRACT_VERSION = "1.0"
ExpenseMethod = Literal["direct_disclosure", "functional_allocation_reconstruction", "defensible_bounds", "unavailable"]
_COST_KINDS = {"direct_fundraising_cost", "agency_fee", "commission", "media_spend", "staff_cost", "event_prize_cost", "administration_allocation", "total_fundraising_cost"}


class ProhibitedFundraisingCalculation(ValueError):
    """Raised when a request would manufacture a fundraising performance fact."""


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


class SourceReportedFundraisingDerivative(BaseModel):
    """A source-native value retained without CharityGraph recomputing it.

    The research gate permits an expressly reported share or proceeds value with
    its source basis.  It does not permit deriving one from an organisation's
    income and expense rows, even when those rows happen to have matching
    periods.  This model deliberately records the reported result rather than
    presenting arithmetic as an independently established performance fact.
    """
    contract_version: str = DERIVATIVE_CONTRACT_VERSION
    kind: Literal["fundraising_cost_share", "net_proceeds"]
    amount: Amount
    source_measurement_id: str
    evidence_ids: tuple[str, ...]
    source_wording: str
    reporting_scope: Literal["subject", "organisation_group", "consolidated_group"]
    period_start: str
    period_end: str
    accounting_basis: str
    approximate: bool = False

    @model_validator(mode="after")
    def require_source_native_basis(self):
        if not self.evidence_ids or not self.source_wording.strip():
            raise ValueError("source-reported derivative requires evidence and source wording")
        if not self.source_measurement_id or not self.period_start or not self.period_end:
            raise ValueError("source-reported derivative requires measurement and exact period")
        if not self.accounting_basis.strip() or self.accounting_basis == "unknown":
            raise ValueError("source-reported derivative requires an accounting basis")
        return self


def _amount(measurement: FundraisingMoneyMeasurement) -> Amount:
    return Amount(amount=str(measurement.amount.normalised_amount), currency=measurement.amount.normalised_currency)


def direct_expense(measurement: FundraisingMoneyMeasurement) -> FundraisingExpenseResult:
    if measurement.measure_kind not in {"direct_fundraising_cost", "total_fundraising_cost"}:
        raise ValueError("measurement is not a directly disclosed fundraising expense")
    if measurement.cost_attribution != "direct" or measurement.allocation_method != "direct_source_reported":
        raise ValueError("direct expense requires direct source-reported attribution")
    if measurement.amount_is_approximate is None:
        raise ValueError("direct expense requires approximation status")
    return FundraisingExpenseResult(method="direct_disclosure", source_measurement_ids=(measurement.observation_id,), evidence_ids=tuple(measurement.evidence_ids), amount=_amount(measurement), approximate=measurement.amount_is_approximate)


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


def fundraising_cost_share(cost: FundraisingMoneyMeasurement, total_expenses: FundraisingMoneyMeasurement) -> None:
    """Refuse a calculated cost share; retain only a source-reported value."""
    raise ProhibitedFundraisingCalculation(
        "calculated fundraising cost share is prohibited; retain an expressly source-reported share instead"
    )


def net_proceeds(gross_proceeds: FundraisingMoneyMeasurement, cost: FundraisingMoneyMeasurement, *, subtraction_permitted_by_source_contract: bool) -> None:
    """Refuse calculated net proceeds; matching rows do not prove attribution."""
    raise ProhibitedFundraisingCalculation(
        "calculated net proceeds is prohibited; retain an expressly source-reported proceeds amount instead"
    )
