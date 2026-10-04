from decimal import Decimal
import pytest

from charitygraph.fundraising_finance_extraction import (
    deterministic_statement_measure_kind,
    normalise_fundraising_finance_row,
)


def row(**changes):
    value = {"observation_id":"source:1", "measurement_id":"money:1", "raw_value":"(1,250)", "currency":"AUD", "unit_scale":"1000", "unit_label":"$'000", "measure_kind":"direct_fundraising_cost", "source_native_wording":"Direct fundraising costs", "evidence_ids":["ev:annual:12"], "period":{"period_start":"2024-07-01", "period_end":"2025-06-30", "period_length_days":365}, "reporting_scope":"subject", "reporting_subject_causebase_id":"cb:one", "recognition_basis":"accrual", "gross_net_basis":"not_applicable", "gst_treatment":"exclusive", "pass_through_treatment":"not_applicable", "cost_attribution":"direct", "allocation_method":"direct_source_reported", "amount_is_approximate":False, "source_role":"audited_financial_statement", "assurance":"audited", "aggregation_set_id":"note:7", "component_is_disjoint":True, "source_family":"annual_report_or_financial_statements", "source_id":"annual:2025", "source_locator":"page 12, note 7, row 3", "subject_binding_basis":"statement names Charity One ABN", "scope_kind":"organisation", "scope_id":"cb:one", "component_treatment":"direct"}
    value.update(changes); return value


def test_pdf_or_structured_row_is_parsed_with_scale_sign_and_complete_provenance():
    result = normalise_fundraising_finance_row(row())
    fact = result.observation
    assert result.outcome == "observed"
    assert fact.measurement.amount.normalised_amount == Decimal("-1250000")
    assert fact.source_locator == "page 12, note 7, row 3"
    assert fact.measurement.period.period_end.isoformat() == "2025-06-30"


def test_unknown_or_generic_labels_cannot_be_silently_promoted():
    with pytest.raises(Exception): normalise_fundraising_finance_row(row(source_native_wording="Marketing", measure_kind=None))
    with pytest.raises(Exception): normalise_fundraising_finance_row(row(source_native_wording="Marketing", measure_kind="direct_fundraising_cost", measurement_id=None))


@pytest.mark.parametrize(("heading", "expected"), [
    ("Fundraising costs", "total_fundraising_cost"),
    (" Direct   Fundraising Costs ", "direct_fundraising_cost"),
    ("Fundraising income", "recognised_revenue"),
    ("Gross fundraising proceeds", "gross_proceeds"),
])
def test_exact_financial_statement_headings_have_a_governed_source_native_mapping(heading, expected):
    source_row = row(source_native_wording=heading, measure_kind=None)
    assert deterministic_statement_measure_kind(source_row) == expected
    assert normalise_fundraising_finance_row(source_row).observation.measurement.measure_kind == expected


@pytest.mark.parametrize("heading", ["Donations", "Income", "Marketing", "Net fundraising income"])
def test_statement_mapping_refuses_generic_or_net_headings(heading):
    source_row = row(source_native_wording=heading, measure_kind=None)
    assert deterministic_statement_measure_kind(source_row) is None
    with pytest.raises(Exception):
        normalise_fundraising_finance_row(source_row)


def test_statement_mapping_cannot_be_reused_for_non_statement_sources():
    source_row = row(source_family="organisation_disclosure", source_native_wording="Fundraising costs", measure_kind=None)
    assert deterministic_statement_measure_kind(source_row) is None
    with pytest.raises(Exception):
        normalise_fundraising_finance_row(source_row)


@pytest.mark.parametrize("status", ["not_found_in_scoped_source", "not_processed", "unavailable"])
def test_scoped_non_results_remain_explicit_and_have_no_money_fact(status):
    result = normalise_fundraising_finance_row({"coverage_status":status, "source_id":"annual:2025", "source_locator":"note 7", "missingness_note":"table reviewed; no direct disclosure"})
    assert result.outcome == status and result.observation is None
