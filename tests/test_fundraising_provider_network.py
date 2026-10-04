import json
from datetime import date
from pathlib import Path

import pytest

from charitygraph.fundraising_evidence_roles import EvidenceScope, FundraisingEvidence
from charitygraph.fundraising_relationship_network import (
    FundraisingProviderNetworkInput, ProviderIdentity, compile_provider_network,
)


CASES = json.loads(Path("tests/fixtures/fundraising_provider_network_cases.json").read_text())


def record(case):
    evidence = FundraisingEvidence(
        evidence_id=f"ev_{case['name']}", source_id="src_provider_case",
        source_role="platform_campaign_page" if case["provider_kind"] == "platform" else "agency_provider_case_evidence",
        locator="https://example.test/evidence", source_wording="Named provider relationship for a bounded campaign.",
        subject_binding="confirmed", binding_basis="charity registry identifier on source", observed_at=date(2026, 9, 1),
        scope=EvidenceScope(kind="campaign", identifier="campaign:spring"), production_method="direct_extract",
        review_status=case["review_status"], asserted_facets=("provider",),
    )
    return FundraisingProviderNetworkInput(
        relationship_id=f"frn_{case['name']}", charity_subject_id="charity:one",
        provider=ProviderIdentity(identity_state=case["provider_state"], subject_id=case["provider_subject_id"], binding_basis="explicit identifier"),
        provider_kind=case["provider_kind"], evidence=evidence, lifecycle=case["lifecycle"],
        relationship_scope="campaign", relationship_scope_id="campaign:spring",
        ended_on=date(2026, 6, 30) if case["lifecycle"] == "ended" else None,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_network_fixture_preserves_discovery_boundary(case):
    compiled = compile_provider_network((record(case),))[0]
    assert compiled.discovery_disposition == case["expected"]
    assert compiled.practice_observed is None
    assert compiled.source_wording
    assert compiled.provider_identity_state == case["provider_state"]


def test_ambiguous_identity_and_former_provider_are_never_promoted_to_current_practice():
    ambiguous, former = compile_provider_network((record(CASES[2]), record(CASES[3])))
    assert ambiguous.to_provider_subject_id is None
    assert ambiguous.discovery_disposition == "do_not_seed"
    assert former.ended_on == date(2026, 6, 30)
    assert former.discovery_disposition == "review_only"
    assert all(item.practice_observed is None for item in (ambiguous, former))


def test_relationship_requires_explicit_provider_facet_and_explicit_end_date():
    item = record(CASES[0])
    with pytest.raises(ValueError, match="provider facet"):
        FundraisingProviderNetworkInput.model_validate({**item.model_dump(), "evidence": item.evidence.model_copy(update={"asserted_facets": ()}).model_dump()})
    with pytest.raises(ValueError, match="ended_on"):
        FundraisingProviderNetworkInput.model_validate({**record(CASES[3]).model_dump(), "ended_on": None})
