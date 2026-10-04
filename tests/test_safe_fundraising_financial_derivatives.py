from datetime import date
import pytest

from charitygraph.finance_measurement import FundraisingMoneyMeasurement
from charitygraph.fundraising_financial_derivatives import bounded_expense, component_rollup, direct_expense, fundraising_cost_share, net_proceeds, reconcile_attribution_bounds, reconstructed_functional_expense, unavailable_expense
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


def test_compatible_cost_share_and_net_proceeds_are_labelled_non_performance_derivatives():
    denominator = m("total", measure_kind="total_expenses", amount={"source_amount":"1000","source_unit_scale":1,"normalised_amount":"1000"})
    assert fundraising_cost_share(m(), denominator).amount.amount == "0.1"
    gross = m("gross", measure_kind="gross_proceeds", gross_net_basis="gross")
    assert net_proceeds(gross, m("cost"), subtraction_permitted_by_source_contract=True).amount.amount == "0"


@pytest.mark.parametrize("change", [{"reporting_subject_causebase_id":"cb:two"}, {"period":{"period_start":date(2025,1,1),"period_end":date(2025,12,31),"period_length_days":365}}, {"recognition_basis":"cash"}])
def test_cost_share_rejects_mismatched_scope_period_or_basis(change):
    denominator = m("total", measure_kind="total_expenses", amount={"source_amount":"1000","source_unit_scale":1,"normalised_amount":"1000"}, **change)
    with pytest.raises(ValueError, match="incompatible measurements"):
        fundraising_cost_share(m(), denominator)


def test_net_proceeds_requires_explicit_contract_permission_and_gross_semantics():
    gross = m("gross", measure_kind="gross_proceeds", gross_net_basis="gross")
    with pytest.raises(ValueError, match="permission"): net_proceeds(gross, m(), subtraction_permitted_by_source_contract=False)
    with pytest.raises(ValueError, match="gross proceeds"): net_proceeds(m("income", measure_kind="recognised_revenue"), m(), subtraction_permitted_by_source_contract=True)


def test_forbidden_performance_metric_names_cannot_be_emitted_as_financial_facts():
    from charitygraph.fundraising_financial_derivatives import DerivedMoneyResult
    for name in ("fundraising_roi", "cost_to_raise_a_dollar", "donor_acquisition_cost", "lifetime_value", "channel_effectiveness", "method_generated_revenue"):
        with pytest.raises(Exception):
            DerivedMoneyResult(kind=name, amount={"amount":"1","currency":"AUD"}, numerator_measurement_id="a", denominator_or_cost_measurement_id="b", evidence_ids=("ev",), formula="unsupported")
    with pytest.raises(Exception):
        DerivedMoneyResult(kind="net_proceeds", amount={"amount":"1","currency":"AUD"}, numerator_measurement_id="a", denominator_or_cost_measurement_id="b", evidence_ids=("ev",), formula="method generated X revenue")


def test_component_rollup_requires_declared_disjoint_compatibility():
    first = m("one", aggregation_set_id="statement:costs", component_is_disjoint=True)
    second = m("two", aggregation_set_id="statement:costs", component_is_disjoint=True)
    assert component_rollup([first, second]).amount.amount == "200"
    with pytest.raises(ValueError, match="component_disjointness_not_evidenced"):
        component_rollup([first, m("not-disjoint", aggregation_set_id="statement:costs")])


def test_reconciliation_preserves_definite_possible_excluded_and_contradiction():
    components = [
        AttributionComponent(observation_id="definite", amount={"amount":"60", "currency":"AUD"}, treatment="definite", additivity_basis="a"),
        AttributionComponent(observation_id="possible", amount={"amount":"30", "currency":"AUD"}, treatment="possible", additivity_basis="b"),
        AttributionComponent(observation_id="excluded", amount={"amount":"99", "currency":"AUD"}, treatment="excluded", additivity_basis="c"),
    ]
    possible = reconcile_attribution_bounds(m("total", amount={"source_amount":"80", "source_unit_scale":1,"normalised_amount":"80"}), components, source_declares_same_aggregation=True, evidence_ids=("ev:components",))
    assert (possible.status, possible.excluded_component_ids, possible.review_required) == ("possible", ("excluded",), False)
    contradiction = reconcile_attribution_bounds(m("bad-total", amount={"source_amount":"100", "source_unit_scale":1,"normalised_amount":"100"}), components, source_declares_same_aggregation=True, evidence_ids=("ev:components",))
    assert (contradiction.status, contradiction.review_required) == ("contradiction", True)
    with pytest.raises(ValueError, match="source-declared"):
        reconcile_attribution_bounds(m("total"), components, source_declares_same_aggregation=False, evidence_ids=("ev:components",))
