from datetime import date
import pytest

from charitygraph.finance_measurement import FundraisingMoneyMeasurement
from charitygraph.fundraising_financial_derivatives import (
    ProhibitedFundraisingCalculation,
    SourceReportedFundraisingDerivative,
    bounded_expense,
    direct_expense,
    fundraising_cost_share,
    net_proceeds,
    reconstructed_functional_expense,
    unavailable_expense,
)
from charitygraph.v05.fundraising import AttributionComponent


def m(identifier="cost", **change):
    value = dict(observation_id=f"obs:{identifier}", amount={"source_amount":"100","source_unit_scale":1,"normalised_amount":"100"}, measure_kind="direct_fundraising_cost", source_wording="source-preserved", evidence_ids=["ev:1"], period={"period_start":date(2024,7,1),"period_end":date(2025,6,30),"period_length_days":365}, reporting_scope="subject", reporting_subject_causebase_id="cb:one", recognition_basis="accrual", gross_net_basis="not_applicable", gst_treatment="exclusive", pass_through_treatment="not_applicable", cost_attribution="direct", allocation_method="direct_source_reported", amount_is_approximate=False, source_role="audited_financial_statement", assurance="audited")
    value.update(change); return FundraisingMoneyMeasurement(**value)


def test_direct_disclosed_reconstructed_bounded_and_unavailable_expense_paths():
    assert direct_expense(m()).method == "direct_disclosure"
    allocated = m("allocated", measure_kind="administration_allocation", cost_attribution="allocated", allocation_basis="reported_function", allocation_method="deterministic_reconstruction", amount_is_approximate=True)
    assert reconstructed_functional_expense(allocated).approximate is True
    bounded = bounded_expense([AttributionComponent(observation_id="a", amount={"amount":"10","currency":"AUD"}, treatment="definite", additivity_basis="a"), AttributionComponent(observation_id="b", amount={"amount":"5","currency":"AUD"}, treatment="possible", additivity_basis="b")], evidence_ids=("ev:bounds",))
    assert (bounded.bounds.lower_bound.amount, bounded.bounds.upper_bound.amount, bounded.bounds.point_estimate) == ("10", "15", None)
    assert unavailable_expense("not available from source").amount is None


def test_direct_disclosure_preserves_source_approximation_status():
    assert direct_expense(m(amount_is_approximate=True)).approximate is True


def test_organisation_level_rows_cannot_be_calculated_into_cost_share_or_net_proceeds():
    denominator = m("total", measure_kind="total_expenses", amount={"source_amount":"1000","source_unit_scale":1,"normalised_amount":"1000"})
    gross = m("gross", measure_kind="gross_proceeds", gross_net_basis="gross")
    with pytest.raises(ProhibitedFundraisingCalculation, match="source-reported"):
        fundraising_cost_share(m(), denominator)
    with pytest.raises(ProhibitedFundraisingCalculation, match="source-reported"):
        net_proceeds(gross, m("cost"), subtraction_permitted_by_source_contract=True)


def test_only_evidence_bound_source_reported_share_or_proceeds_can_be_retained():
    reported = SourceReportedFundraisingDerivative(
        kind="fundraising_cost_share", amount={"amount":"0.1", "currency":"ratio"},
        source_measurement_id="obs:reported-share", evidence_ids=("ev:reported",),
        source_wording="Fundraising expenditure was 10% of total expenses.",
        reporting_scope="subject", period_start="2024-07-01", period_end="2025-06-30",
        accounting_basis="accrual",
    )
    assert reported.kind == "fundraising_cost_share"
    with pytest.raises(Exception, match="accounting basis"):
        SourceReportedFundraisingDerivative(kind="net_proceeds", amount={"amount":"1", "currency":"AUD"}, source_measurement_id="obs:1", evidence_ids=("ev:1",), source_wording="Net proceeds", reporting_scope="subject", period_start="2024-07-01", period_end="2025-06-30", accounting_basis="unknown")


def test_prohibited_performance_metric_names_cannot_be_emitted_as_financial_facts():
    for name in ("fundraising_roi", "cost_to_raise_a_dollar", "donor_acquisition_cost", "lifetime_value", "profitability", "channel_effectiveness", "causal_uplift", "method_generated_revenue"):
        with pytest.raises(Exception):
            SourceReportedFundraisingDerivative(kind=name, amount={"amount":"1","currency":"AUD"}, source_measurement_id="a", evidence_ids=("ev",), source_wording="unsupported", reporting_scope="subject", period_start="2024-07-01", period_end="2025-06-30", accounting_basis="accrual")
