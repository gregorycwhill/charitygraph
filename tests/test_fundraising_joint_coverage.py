import json
from pathlib import Path

import pytest

from charitygraph.fundraising_joint_coverage import (
    JOINT_COVERAGE_CONTRACT_VERSION,
    JointCoverageState,
    classify_fundraising_joint_coverage,
    summarise_fundraising_joint_coverage,
)
from charitygraph.fundraising_money_linkage import FundraisingMoneyScopeLink
from charitygraph.models import CauseBaseCard


FIXTURE = Path(__file__).parent / "fixtures" / "fundraising_card_projection.json"


def fixture():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return CauseBaseCard.model_validate(payload["card"]), tuple(
        FundraisingMoneyScopeLink.model_validate(item) for item in payload["money_links"]
    )


def test_coexisting_practice_and_aggregate_money_are_visible_but_not_attributed():
    card, money = fixture()
    result = classify_fundraising_joint_coverage(card, money)
    assert result.contract_version == JOINT_COVERAGE_CONTRACT_VERSION
    assert result.state is JointCoverageState.METHOD_KNOWN_FINANCE_AGGREGATE
    assert not result.coexistence_is_attribution
    assert result.attributed_finance_observation_ids == ()
    assert "not" in result.note.lower()


def test_explicit_lower_grain_link_is_separate_from_coexistence():
    card, money = fixture()
    linked = money[0].model_copy(update={
        "linkage_status": "explicit", "attributed_scope_kind": "campaign",
        "attributed_scope_id": "fc_card_appeal", "linkage_evidence_ids": ["ev_money"],
        "linkage_source_wording": "Winter Appeal fundraising expenses",
    })
    result = classify_fundraising_joint_coverage(card, (linked,))
    assert result.state is JointCoverageState.LOWER_GRAIN_ATTRIBUTED
    assert result.attributed_finance_observation_ids == ("fm_card_total_cost",)


def test_non_aggregate_organisation_fact_and_method_are_both_known_not_attributed():
    card, money = fixture()
    payload = money[0].model_dump(mode="json")
    payload["measurement"]["measure_kind"] = "direct_fundraising_cost"
    payload["measurement"]["source_wording"] = "Direct fundraising costs"
    payload["linkage_status"] = "explicit"
    payload["linkage_evidence_ids"] = ["ev_money"]
    payload["linkage_source_wording"] = "Organisation fundraising costs"
    result = classify_fundraising_joint_coverage(card, (FundraisingMoneyScopeLink.model_validate(payload),))
    assert result.state is JointCoverageState.BOTH_KNOWN
    assert result.attributed_finance_observation_ids == ()


def test_finance_without_method_is_unknown_not_an_absence_claim_and_summary_keeps_denominator():
    card, money = fixture()
    card = card.model_copy(update={"fundraising_practice_observed": []})
    finance_only = classify_fundraising_joint_coverage(card, money)
    neither = classify_fundraising_joint_coverage(card, ())
    assert finance_only.state is JointCoverageState.FINANCE_KNOWN_METHOD_UNKNOWN
    assert neither.state is JointCoverageState.NEITHER
    summary = summarise_fundraising_joint_coverage((finance_only, neither))
    assert summary.denominator == 2
    assert summary.counts[JointCoverageState.FINANCE_KNOWN_METHOD_UNKNOWN] == 1
    assert summary.counts[JointCoverageState.NEITHER] == 1


def test_mismatched_finance_subject_is_refused_before_it_can_affect_coverage():
    card, money = fixture()
    wrong = money[0].model_copy(update={"reporting_entity_causebase_id": "cb_other"})
    with pytest.raises(ValueError, match="does not match card subject"):
        classify_fundraising_joint_coverage(card, (wrong,))
