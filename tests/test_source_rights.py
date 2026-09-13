from datetime import date
import hashlib

import pytest

from charitygraph.source_rights import (
    ArtifactRightsDecision,
    FAIR_DEALING_POLICY_ID,
    OPENAI_PROVIDER_POLICY_ID,
    require_provider_rights,
)


ORIGIN = "https://example.test/public"
SOURCE = {
    "source_artifact_id": "srcblob:a", "source_record_id": "srcrec:a",
    "source_locator": ORIGIN, "source_role": "official_homepage",
    "exact_transmitted_representation": "bounded text",
}


def decision(**changes):
    value = dict(
        decision_id="rights:1", source_artifact_id="srcblob:a", source_record_id="srcrec:a",
        source_origin_url=ORIGIN, source_role="official_homepage", acquisition_lineage_ids=("acq:a",),
        transmitted_representation_sha256=hashlib.sha256(b"bounded text").hexdigest(),
        rights_policy_id=FAIR_DEALING_POLICY_ID, provider_processing_policy_id=OPENAI_PROVIDER_POLICY_ID,
        rights_basis="statutory_exception", evidence_locator="https://example.test/policy",
        evidence_sha256="b" * 64, assessed_on=date(2026, 9, 13), assessment_scope="private bounded analytical processing",
        local_retention_allowed=False, provider_transmission_allowed=True, public_redistribution_allowed=False,
        representation_class="bounded_excerpt", publicly_accessible_without_circumvention=True,
        access_controls_bypassed=False, lawfully_acquired=True, analytical_purpose="semantic_analysis",
        provider_no_training_default=True, provider_data_sharing_opt_in=False,
    )
    value.update(changes)
    return ArtifactRightsDecision.model_validate(value)


def test_bounded_public_web_excerpt_authorizes_private_analysis():
    assert decision().provider_transmission_allowed


def test_bounded_public_annual_report_excerpt_authorizes_private_analysis():
    assert decision(representation_class="bounded_excerpt", source_role="financial_report").provider_transmission_allowed


def test_structured_factual_representation_is_allowed_under_approved_policy():
    assert decision(representation_class="structured_factual", factual_representation_only=True).provider_transmission_allowed


def test_explicit_cc_licence_uses_stronger_basis_without_fair_dealing_predicates():
    value = decision(rights_basis="explicit_open_license", licence_identifier="CC BY 4.0",
        licence_or_terms_url="https://creativecommons.org/licenses/by/4.0/", rights_policy_id="CC_BY_4_0_V1")
    assert value.provider_transmission_allowed


def test_public_facts_only_requires_bound_fact_only_structured_representation():
    value = decision(rights_basis="public_facts_only", rights_policy_id="PUBLIC_FACTS_ONLY_V1", factual_representation_only=True,
        representation_class="structured_factual")
    assert value.provider_transmission_allowed
    with pytest.raises(ValueError, match="factual structured"):
        decision(rights_basis="public_facts_only", rights_policy_id="PUBLIC_FACTS_ONLY_V1", factual_representation_only=True,
            representation_class="bounded_excerpt")


@pytest.mark.parametrize("changes", [
    {"representation_class": "complete_or_near_complete_work"},
    {"representation_class": "unclear"},
    {"publicly_accessible_without_circumvention": False},
    {"publicly_accessible_without_circumvention": None},
    {"access_controls_bypassed": True},
    {"lawfully_acquired": False},
    {"explicit_prohibition_found": True},
    {"provider_processing_policy_id": ""},
    {"provider_processing_policy_id": "unapproved-provider-policy"},
    {"provider_no_training_default": False},
    {"provider_data_sharing_opt_in": True},
    {"acquisition_lineage_ids": ()},
])
def test_fair_dealing_fails_closed_on_missing_or_disqualifying_predicates(changes):
    with pytest.raises(ValueError):
        decision(**changes)


def test_generic_statutory_exception_cannot_authorize():
    with pytest.raises(ValueError, match="predicates"):
        decision(rights_policy_id="unapproved-statutory-policy")


def test_public_access_flag_alone_cannot_authorize():
    with pytest.raises(ValueError):
        decision(rights_policy_id="unapproved-statutory-policy", provider_transmission_allowed=True)


def test_fair_dealing_does_not_grant_public_redistribution():
    with pytest.raises(ValueError, match="V1 does not authorize redistribution"):
        decision(public_redistribution_allowed=True)


def test_fair_dealing_does_not_grant_local_retention():
    with pytest.raises(ValueError, match="does not authorize local retention"):
        decision(local_retention_allowed=True)


def test_fair_dealing_policy_never_authorizes_retention_even_when_provider_is_blocked():
    with pytest.raises(ValueError, match="does not authorize local retention"):
        decision(provider_transmission_allowed=False, local_retention_allowed=True)


def test_exact_hash_and_artifact_lineage_are_required():
    assert require_provider_rights([decision(transmitted_representation_sha256="c" * 64)], [SOURCE])
    assert require_provider_rights([decision()], [{**SOURCE, "source_record_id": "srcrec:other"}])
    assert require_provider_rights([decision()], [{**SOURCE, "source_locator": "https://other.test/"}])
    assert not require_provider_rights([decision()], [SOURCE])


def test_conflicting_duplicate_decisions_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        require_provider_rights([decision(), decision()], [SOURCE])
