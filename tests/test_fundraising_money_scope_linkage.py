import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.finance_measurement import FundraisingMoneyMeasurement
from charitygraph.fundraising_money_linkage import (
    LINKAGE_CONTRACT_VERSION,
    FundraisingMoneyScopeLink,
    decide_linked_addition_compatibility,
)


def measurement(**changes):
    values = {
        "observation_id": "obs:left", "amount": {"source_amount": "100", "source_unit_scale": 1, "normalised_amount": "100"},
        "measure_kind": "direct_fundraising_cost", "source_wording": "Direct fundraising cost -- Appeal A",
        "evidence_ids": ["ev:statement"],
        "period": {"period_start": date(2024, 7, 1), "period_end": date(2025, 6, 30), "period_length_days": 365},
        "reporting_scope": "subject", "reporting_subject_causebase_id": "cb:charity",
        "recognition_basis": "accrual", "gross_net_basis": "not_applicable", "gst_treatment": "exclusive",
        "pass_through_treatment": "not_applicable", "cost_attribution": "direct", "allocation_method": "direct_source_reported", "amount_is_approximate": False,
        "source_role": "audited_financial_statement", "assurance": "audited",
        "fundraising_activity_id": "activity:appeal-a", "aggregation_set_id": "statement:note-7:appeal-a",
        "component_is_disjoint": True,
    }
    values.update(changes)
    return FundraisingMoneyMeasurement(**values)


def explicit(scope, scope_id, **changes):
    reporting_entity = changes.get("reporting_subject_causebase_id", "cb:charity")
    values = {
        "measurement": measurement(**changes), "linkage_status": "explicit",
        "attributed_scope_kind": scope, "attributed_scope_id": scope_id,
        "reporting_entity_causebase_id": reporting_entity, "linkage_evidence_ids": ["ev:note"],
        "linkage_source_wording": "Appeal A direct costs",
    }
    return FundraisingMoneyScopeLink(**values)


def test_explicit_campaign_and_practice_attribution_are_separate_evidenced_links():
    campaign = explicit("campaign", "campaign:appeal-a")
    practice = explicit("practice", "practice:f2f", fundraising_activity_id="activity:f2f", source_wording="Face-to-face recruitment cost")
    assert campaign.linkage_status == practice.linkage_status == "explicit"
    assert campaign.attributed_scope_kind == "campaign"
    assert practice.attributed_scope_kind == "practice"


def test_t05_organisation_and_portfolio_examples_cannot_be_promoted_by_proximity():
    organisation_total = FundraisingMoneyScopeLink(measurement=measurement(measure_kind="recognised_revenue", source_wording="Total income", fundraising_activity_id=None), linkage_status="unknown", note="t05 c12")
    portfolio_share = FundraisingMoneyScopeLink(measurement=measurement(source_wording="Fundraising share of total expenses", fundraising_activity_id=None, cost_attribution="allocated", allocation_basis="reported-total-expenses", allocation_method="deterministic_reconstruction", amount_is_approximate=True), linkage_status="unknown", note="t05 c15")
    assert organisation_total.attributed_scope_kind == portfolio_share.attributed_scope_kind == "organisation"
    with pytest.raises(ValidationError, match="unknown linkage must remain"):
        FundraisingMoneyScopeLink(measurement=portfolio_share.measurement, linkage_status="unknown", attributed_scope_kind="practice", attributed_scope_id="practice:f2f")
    with pytest.raises(ValidationError, match="explicit linkage requires"):
        FundraisingMoneyScopeLink(measurement=organisation_total.measurement, linkage_status="explicit", attributed_scope_kind="campaign", attributed_scope_id="campaign:appeal-a")


def test_aggregate_total_cannot_be_mechanically_distributed_across_observed_methods():
    aggregate = FundraisingMoneyScopeLink(measurement=measurement(source_wording="Fundraising share of total expenses", fundraising_activity_id=None, cost_attribution="allocated", allocation_basis="reported-total-expenses", allocation_method="deterministic_reconstruction", amount_is_approximate=True), linkage_status="unknown", note="t05 c15 aggregate portfolio amount")
    f2f = explicit("practice", "practice:f2f", observation_id="obs:f2f", fundraising_activity_id="activity:f2f")
    digital = explicit("practice", "practice:digital", observation_id="obs:digital", fundraising_activity_id="activity:digital")
    assert not decide_linked_addition_compatibility(aggregate, f2f).safe_to_add
    assert not decide_linked_addition_compatibility(f2f, digital).safe_to_add


@pytest.mark.parametrize(("change", "reason"), [
    ({"period": {"period_start": date(2025, 1, 1), "period_end": date(2025, 12, 31), "period_length_days": 365}}, "different_period"),
    ({"reporting_subject_causebase_id": "cb:other"}, "different_reporting_subject"),
    ({"recognition_basis": "cash"}, "different_recognition_basis"),
    ({"cost_attribution": "allocated", "allocation_basis": "staff-hours", "allocation_method": "source_reported_functional_allocation"}, "different_cost_attribution"),
])
def test_incompatible_measurements_remain_uncombinable_after_explicit_linking(change, reason):
    left = explicit("campaign", "campaign:appeal-a")
    right = explicit("campaign", "campaign:appeal-a", observation_id="obs:right", **change)
    result = decide_linked_addition_compatibility(left, right)
    assert not result.safe_to_add
    assert reason in result.reasons


def test_fixture_preserves_t05_positive_and_negative_cases_and_contract_version():
    fixture = json.loads(Path("tests/fixtures/fundraising_money_scope_linkage.json").read_text())
    assert fixture["contract_version"] == LINKAGE_CONTRACT_VERSION
    assert {"positive_organisation", "positive_portfolio", "negative_mixed_row", "negative_aggregate"} <= set(fixture["t05_study_cases"])
