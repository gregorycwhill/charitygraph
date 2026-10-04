import json
from pathlib import Path

import pytest

from charitygraph.fundraising import estimate_fundraising
from charitygraph.models import FundraisingEstimate
from charitygraph.pipeline import build_card


FIXTURE = Path("tests/fixtures/source/entities.json")


def entities():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["entities"]


def test_direct_fundraising_estimate():
    estimate = estimate_fundraising(entities()[0])
    assert estimate.normalised_amount == 12000
    assert estimate.method == "direct_extract"
    assert estimate.confidence == "high"


def test_component_labels_do_not_create_a_fundraising_estimate():
    estimate = estimate_fundraising(entities()[1])
    assert estimate is None


def test_generic_card_pipeline_quarantines_component_label_inference():
    card = build_card(entities()[1], dataset_version="test")
    assert card.fundraising_expenditure is None
    assert any(
        observation.capability == "fundraising_expenditure"
        and observation.status == "not_yet_processed"
        for observation in card.coverage
    )


def test_no_evidence_returns_unavailable_and_ignores_legacy_prior_input():
    estimate = estimate_fundraising(entities()[2])
    assert estimate is None


@pytest.mark.parametrize("method", ["peer_imputation", "fallback_prior"])
def test_obsolete_fundraising_methods_are_rejected(method):
    with pytest.raises(ValueError):
        FundraisingEstimate(
            normalised_amount=1,
            method=method,
            confidence="low",
        )
