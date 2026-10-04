from datetime import date
from decimal import Decimal
import json
from pathlib import Path

from charitygraph.fundraising_finance_extraction import normalise_fundraising_finance_row
from charitygraph.fundraising_finance_history import (
    FUNDRAISING_FINANCE_HISTORY_VERSION, HistoricalFundraisingMoneyObservation, build_fundraising_money_history,
)


def row(year, amount, **changes):
    value = {
        "observation_id": f"source:{year}", "measurement_id": f"money:{year}", "raw_value": str(amount),
        "currency": "AUD", "measure_kind": "direct_fundraising_cost", "source_native_wording": "Fundraising costs",
        "evidence_ids": [f"ev:{year}"], "period": {"period_start": f"{year}-07-01", "period_end": f"{year + 1}-06-30", "period_length_days": 365},
        "reporting_scope": "subject", "reporting_subject_causebase_id": "cb:one", "recognition_basis": "accrual",
        "gross_net_basis": "not_applicable", "gst_treatment": "exclusive", "pass_through_treatment": "not_applicable",
        "cost_attribution": "direct", "allocation_method": "direct_source_reported", "amount_is_approximate": False,
        "source_role": "audited_financial_statement", "assurance": "audited", "source_family": "annual_report_or_financial_statements",
        "source_id": f"annual:{year}", "source_locator": f"page 10 row {year}", "subject_binding_basis": "statement names Charity One ABN",
        "scope_kind": "organisation", "scope_id": "cb:one", "component_treatment": "direct",
    }
    value.update(changes)
    return value


def historic(year, amount, **changes):
    classification_id = changes.pop("classification_id", "statement:fundraising-costs")
    return HistoricalFundraisingMoneyObservation(
        source_fact=normalise_fundraising_finance_row(row(year, amount, **changes)).observation,
        classification_id=classification_id,
    )


def test_like_for_like_annual_history_exposes_nominal_change_without_annualisation():
    history = build_fundraising_money_history([historic(2023, 100), historic(2024, 125)])
    comparison = history.comparisons[0]
    assert comparison.status == "comparable"
    assert comparison.nominal_change == Decimal("25")
    assert comparison.nominal_change_fraction == Decimal("0.25")
    assert history.nominal_amounts is True


def test_restated_fact_is_preserved_and_creates_a_visible_discontinuity():
    original = historic(2023, 100)
    restated = historic(2024, 110, observation_id="source:2024-restated", measurement_id="money:2024-restated")
    restated.restates_observation_id = original.source_fact.observation_id
    history = build_fundraising_money_history([original, restated])
    assert [item.source_fact.observation_id for item in history.observations] == ["source:2023", "source:2024-restated"]
    assert "restatement_present" in history.comparisons[0].reasons
    assert history.comparisons[0].nominal_change is None


def test_classification_entity_and_short_period_never_become_a_trend():
    classification_shift = build_fundraising_money_history([
        historic(2023, 100), historic(2024, 130, classification_id="statement:fundraising-and-marketing"),
    ])
    assert "classification_changed" in classification_shift.comparisons[0].reasons
    entity_change = historic(2024, 120)
    entity_change.reporting_entity_changed = True
    assert "reporting_entity_changed" in build_fundraising_money_history([historic(2023, 100), entity_change]).comparisons[0].reasons
    short = historic(2024, 120, period={"period_start": "2024-07-01", "period_end": "2024-12-31", "period_length_days": 184})
    assert "nonstandard_or_inexact_reporting_period" in build_fundraising_money_history([historic(2023, 100), short]).comparisons[0].reasons


def test_versioned_history_fixture_records_the_non_promotional_discontinuities():
    fixture = json.loads(Path("tests/fixtures/fundraising_finance_history.json").read_text())
    assert fixture["contract_version"] == FUNDRAISING_FINANCE_HISTORY_VERSION
    assert fixture["nominal_amounts"] is True
    assert {case["expected_status"] for case in fixture["cases"]} == {"comparable", "discontinuity"}
    assert "No annualisation" in fixture["cases"][-1]["note"]
