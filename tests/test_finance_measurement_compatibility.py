import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.finance_measurement import (
    FINANCE_MEASUREMENT_COMPATIBILITY_VERSION,
    FundraisingMoneyMeasurement,
    decide_addition_compatibility,
)


def measurement(**changes):
    values = {
        "observation_id": "obs:left", "amount": {"source_amount": "100", "source_unit_scale": 1, "normalised_amount": "100"},
        "measure_kind": "direct_fundraising_cost", "source_wording": "Direct fundraising costs — appeal A",
        "evidence_ids": ["ev:1"], "period": {"period_start": date(2024, 7, 1), "period_end": date(2025, 6, 30), "period_length_days": 365},
        "reporting_scope": "subject", "reporting_subject_causebase_id": "cb:1", "recognition_basis": "accrual",
        "gross_net_basis": "not_applicable", "gst_treatment": "exclusive", "pass_through_treatment": "not_applicable",
        "cost_attribution": "direct", "allocation_method": "direct_source_reported", "amount_is_approximate": False, "source_role": "audited_financial_statement", "assurance": "audited",
        "fundraising_activity_id": "campaign:appeal-a", "aggregation_set_id": "statement:note-7:appeal-a", "component_is_disjoint": True,
    }
    values.update(changes)
    return FundraisingMoneyMeasurement(**values)


def test_exactly_aligned_disjoint_source_components_are_safe_to_add():
    left = measurement()
    right = measurement(observation_id="obs:right", amount={"source_amount": "200", "source_unit_scale": 1, "normalised_amount": "200"})
    decision = decide_addition_compatibility(left, right)
    assert decision.contract_version == FINANCE_MEASUREMENT_COMPATIBILITY_VERSION
    assert decision.safe_to_add


@pytest.mark.parametrize(("change", "reason"), [
    ({"measure_kind": "pledged", "recognition_basis": "accrual"}, "different_measure_kind"),
    ({"gross_net_basis": "gross"}, "different_gross_net_basis"),
    ({"period": {"period_start": date(2025, 1, 1), "period_end": date(2025, 12, 31), "period_length_days": 365}}, "different_period"),
    ({"reporting_scope": "consolidated_group", "reporting_subject_causebase_id": None, "consolidation_scope_id": "group:1"}, "different_reporting_scope"),
    ({"measure_kind": "donations_received", "recognition_basis": "cash", "cost_attribution": "not_applicable"}, "different_measure_kind"),
    ({"cost_attribution": "allocated", "allocation_basis": "staff-hours", "allocation_method": "source_reported_functional_allocation"}, "different_cost_attribution"),
])
def test_material_counterexamples_remain_separate(change, reason):
    decision = decide_addition_compatibility(measurement(), measurement(observation_id="obs:right", **change))
    assert not decision.safe_to_add
    assert reason in decision.reasons


def test_unknown_period_and_missing_disjointness_fail_closed():
    decision = decide_addition_compatibility(
        measurement(), measurement(observation_id="obs:right", period={"label": "FY25"}, component_is_disjoint=False)
    )
    assert not decision.safe_to_add
    assert {"period_not_exactly_identified", "component_disjointness_not_evidenced"} <= set(decision.reasons)


def test_source_native_fixture_is_versioned_and_non_promotional():
    fixture = json.loads(Path("tests/fixtures/finance_measurement_compatibility.json").read_text())
    assert fixture["contract_version"] == FINANCE_MEASUREMENT_COMPATIBILITY_VERSION
    assert "not fundraising-generated revenue" in fixture["source_examples"][1]["note"]


def test_scope_and_allocated_cost_require_their_identity_fields():
    with pytest.raises(ValidationError):
        measurement(reporting_subject_causebase_id=None)
    with pytest.raises(ValidationError):
        measurement(cost_attribution="allocated", allocation_method="source_reported_functional_allocation")
