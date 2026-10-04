import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.finance_measurement import FundraisingMoneyMeasurement
from charitygraph.fundraising_finance_source_contract import (
    FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION,
    FundraisingFinanceSourceObservation,
    decide_finance_source_addition_compatibility,
)


def measurement(identifier="one", **changes):
    values = {
        "observation_id": f"money:{identifier}",
        "amount": {"source_amount": "100", "source_unit_scale": 1, "normalised_amount": "100"},
        "measure_kind": "direct_fundraising_cost", "source_wording": "Appeal A direct costs",
        "evidence_ids": ["evidence:statement:18"],
        "period": {"period_start": date(2024, 7, 1), "period_end": date(2025, 6, 30), "period_length_days": 365},
        "reporting_scope": "subject", "reporting_subject_causebase_id": "charity:one",
        "recognition_basis": "accrual", "gross_net_basis": "not_applicable", "gst_treatment": "exclusive",
        "pass_through_treatment": "not_applicable", "cost_attribution": "direct",
        "allocation_method": "direct_source_reported", "amount_is_approximate": False,
        "source_role": "audited_financial_statement", "assurance": "audited",
        "fundraising_activity_id": "campaign:appeal-a", "aggregation_set_id": "statement:appeal-a",
        "component_is_disjoint": True,
    }
    values.update(changes)
    return FundraisingMoneyMeasurement(**values)


def source(identifier="one", **changes):
    values = {
        "observation_id": f"source:{identifier}", "measurement": measurement(identifier),
        "source_family": "annual_report_or_financial_statements", "source_id": "annual-report:2025",
        "source_locator": "page 18, note 7", "source_native_wording": "Appeal A direct costs",
        "subject_binding_basis": "audited statement identifies Charity One", "scope_kind": "campaign",
        "scope_id": "campaign:appeal-a", "component_treatment": "direct",
        "production_method": "direct_source_claim", "review_status": "reviewed", "coverage_status": "observed",
    }
    values.update(changes)
    return FundraisingFinanceSourceObservation(**values)


def test_identical_source_contract_dimensions_allow_disjoint_direct_campaign_components():
    left = source("left")
    right = source("right", measurement=measurement("right", amount={"source_amount": "200", "source_unit_scale": 1, "normalised_amount": "200"}))
    assert decide_finance_source_addition_compatibility(left, right).safe_to_add


@pytest.mark.parametrize(("changes", "reason"), [
    ({"scope_kind": "organisation", "scope_id": "charity:one"}, "different_finance_scope_kind"),
    ({"component_treatment": "possible"}, "non_deterministic_component_treatment"),
    ({"component_treatment": "excluded"}, "non_deterministic_component_treatment"),
    ({"component_treatment": "allocated", "measurement": measurement("allocated", measure_kind="administration_allocation", cost_attribution="allocated", allocation_basis="reported-function", allocation_method="source_reported_functional_allocation")}, "different_component_treatment"),
])
def test_scope_and_component_counterexamples_fail_closed(changes, reason):
    decision = decide_finance_source_addition_compatibility(source("left"), source("right", **changes))
    assert not decision.safe_to_add
    assert reason in decision.reasons


def test_organisation_scope_cannot_be_rebound_and_non_observation_requires_missingness():
    with pytest.raises(ValidationError, match="organisation scope must retain"):
        source("bad", scope_kind="organisation", scope_id="charity:other")
    with pytest.raises(ValidationError, match="missingness note"):
        source("missing", coverage_status="not_found_in_scoped_source")


def test_versioned_fixture_names_source_families_and_refusal_cases():
    fixture = json.loads(Path("tests/fixtures/fundraising_finance_source_contract.json").read_text())
    assert fixture["contract_version"] == FUNDRAISING_FINANCE_SOURCE_CONTRACT_VERSION
    assert "provider_record" in fixture["source_families"]
    assert {"incompatible_organisation_campaign", "incompatible_possible", "incompatible_excluded"} <= set(fixture["cases"])
