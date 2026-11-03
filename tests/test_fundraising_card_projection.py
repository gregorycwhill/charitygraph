import json
from pathlib import Path

import pytest

from charitygraph.fundraising_money_linkage import FundraisingMoneyScopeLink
from charitygraph.models import CauseBaseCard
from charitygraph.north_star_projection import project_fundraising, render_fundraising_card


FIXTURE = Path(__file__).parent / "fixtures" / "fundraising_card_projection.json"


def load_fixture():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return (
        CauseBaseCard.model_validate(payload["card"]),
        tuple(FundraisingMoneyScopeLink.model_validate(item) for item in payload["money_links"]),
    )


def test_normal_card_projection_preserves_freshness_scope_provenance_and_unknowns():
    card, money_links = load_fixture()
    projection = project_fundraising(card, money_links)
    rendered = render_fundraising_card(projection)

    assert projection.model_dump(mode="json") == project_fundraising(card, money_links).model_dump(mode="json")
    assert projection.practices[0].lifecycle == "current"
    assert projection.campaigns[0].lifecycle == "historical"
    assert projection.money[0].linkage_status == "unknown"
    assert {item.evidence_id for item in projection.evidence} == {"ev_current", "ev_historical", "ev_money"}
    assert "organisation (not attributed)" in rendered
    assert "fundraising_provider_relationships`: `unknown`" in rendered
    assert "125000 AUD" in rendered


def test_projection_refuses_unbound_money_and_does_not_turn_source_silence_into_a_method():
    card, money_links = load_fixture()
    payload = money_links[0].model_dump(mode="json")
    payload["reporting_entity_causebase_id"] = "cb_other_subject"
    payload["linkage_status"] = "explicit"
    payload["attributed_scope_kind"] = "campaign"
    payload["attributed_scope_id"] = "fc_external_campaign"
    payload["linkage_evidence_ids"] = ["ev_money"]
    payload["linkage_source_wording"] = "External campaign disclosure"
    wrong_subject = FundraisingMoneyScopeLink.model_validate(payload)

    with pytest.raises(ValueError, match="does not match card subject"):
        project_fundraising(card, (wrong_subject,))

    projection = project_fundraising(card)
    assert projection.provider_relationships == ()
    assert any(item.status == "unknown" for item in projection.coverage)


def test_visible_output_makes_no_fundraising_performance_or_effectiveness_claim():
    card, money_links = load_fixture()
    rendered = render_fundraising_card(project_fundraising(card, money_links)).lower()
    forbidden = ("roi", "cost-to-raise", "donor acquisition cost", "lifetime value", "profitability", "causal uplift")
    assert not any(term in rendered for term in forbidden)
