import json
from datetime import date
from pathlib import Path

import pytest

from charitygraph.fundraising_money_linkage import FundraisingMoneyScopeLink
from charitygraph.fundraising_query import (
    FundraisingQueryInput,
    charities_with_campaign_level_proceeds,
    charities_with_current_practice,
    charities_with_current_practices,
    charities_with_disclosed_fundraising_expenditure,
    charities_with_method_known_finance_unattributed,
)
from charitygraph.models import CauseBaseCard


FIXTURE = Path(__file__).parent / "fixtures" / "fundraising_card_projection.json"


def input_fixture(*, regular_giving=False, card_id=None, money=None):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if card_id:
        payload["card"]["causebase_id"] = card_id
        for practice in payload["card"]["fundraising_practice_observed"]:
            practice["scope"]["scope_subject_causebase_id"] = card_id
        for link in payload["money_links"]:
            link["reporting_entity_causebase_id"] = card_id
            link["measurement"]["reporting_subject_causebase_id"] = card_id
    if regular_giving:
        payload["card"]["fundraising_practice_observed"].append({
            "observation_id": "fp_card_regular", "source_native_phrase": "regular giving program",
            "canonical_facets": ["fundraising.regular_giving"],
            "scope": {"scope_kind": "subject", "scope_subject_causebase_id": payload["card"]["causebase_id"], "observed_at": "2026-09-01"},
            "lifecycle": "current", "source_role": "direct_assertion", "evidence_ids": ["ev_current"],
        })
    if money is not None:
        payload["money_links"] = money
    return FundraisingQueryInput(card=CauseBaseCard.model_validate(payload["card"]), money_links=tuple(FundraisingMoneyScopeLink.model_validate(item) for item in payload["money_links"]))


def test_current_f2f_and_regular_giving_query_is_evidence_bounded_and_provider_free():
    both = input_fixture(regular_giving=True)
    f2f_only = input_fixture(card_id="cb_f2f_only")
    result = charities_with_current_practices((both, f2f_only), ("fundraising.face_to_face", "fundraising.regular_giving"))
    assert result.denominator == 2
    assert [match.causebase_id for match in result.matches] == ["cb_card_fundraising"]
    assert set(result.matches[0].practice_observation_ids) == {"fp_card_f2f", "fp_card_regular"}
    assert [evidence.evidence_id for evidence in result.matches[0].evidence] == ["ev_current"]
    assert result.matches[0].coverage[0].status == "observed"


def test_freshness_filter_excludes_old_evidence_without_calling_it_false():
    item = input_fixture()
    result = charities_with_current_practice((item,), "fundraising.face_to_face", evidence_observed_on_or_after=date(2026, 9, 2))
    assert result.denominator == 1
    assert result.matches == ()
    assert item.card.coverage[0].status == "observed"


def test_expenditure_and_unattributed_coexistence_retain_money_provenance_without_causality():
    item = input_fixture()
    expenditure = charities_with_disclosed_fundraising_expenditure((item,))
    coexistence = charities_with_method_known_finance_unattributed((item,))
    assert expenditure.matches[0].money_observation_ids == ("fm_card_total_cost",)
    assert [evidence.evidence_id for evidence in expenditure.matches[0].evidence] == ["ev_money"]
    assert coexistence.matches[0].joint_coverage.state == "method_known_finance_aggregate"
    assert "no method-level attribution" in coexistence.matches[0].note


def test_campaign_proceeds_requires_explicit_campaign_link_and_gross_proceeds_kind():
    item = input_fixture()
    payload = item.money_links[0].model_dump(mode="json")
    payload["measurement"]["measure_kind"] = "gross_proceeds"
    payload["measurement"]["source_wording"] = "Winter Appeal gross proceeds"
    payload["linkage_status"] = "explicit"
    payload["attributed_scope_kind"] = "campaign"
    payload["attributed_scope_id"] = "fc_card_appeal"
    payload["linkage_evidence_ids"] = ["ev_money"]
    payload["linkage_source_wording"] = "Winter Appeal gross proceeds"
    linked = FundraisingQueryInput(card=item.card, money_links=(FundraisingMoneyScopeLink.model_validate(payload),))
    assert charities_with_campaign_level_proceeds((item,)).matches == ()
    result = charities_with_campaign_level_proceeds((linked,))
    assert result.matches[0].money_observation_ids == ("fm_card_total_cost",)


def test_duplicate_subject_and_unbound_finance_are_refused():
    item = input_fixture()
    with pytest.raises(ValueError, match="duplicate"):
        charities_with_current_practice((item, item), "fundraising.face_to_face")
    payload = item.money_links[0].model_dump(mode="json")
    payload["reporting_entity_causebase_id"] = "cb_other"
    payload["measurement"]["reporting_subject_causebase_id"] = "cb_other"
    with pytest.raises(ValueError, match="does not match"):
        FundraisingQueryInput(card=item.card, money_links=(FundraisingMoneyScopeLink.model_validate(payload),))
