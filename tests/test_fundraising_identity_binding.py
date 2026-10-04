from datetime import date

import pytest

from charitygraph.fundraising_identity_binding import (
    FundraisingBindingEvidence,
    FundraisingIdentityCandidate,
    binding_outcome_counts,
    resolve_fundraising_subject_binding,
)


def candidate(subject_id="subject:one", abn="12345678901", domain="one.example"):
    return FundraisingIdentityCandidate(subject_id=subject_id, abn=abn, canonical_domain=domain, names=("One Charity",))


def evidence(**changes):
    values = {"evidence_id": "e:1", "source_record_id": "src:1", "observed_at": date(2026, 10, 5)}
    values.update(changes)
    return FundraisingBindingEvidence(**values)


def test_exact_abn_resolves_unique_subject_and_retains_authority_basis():
    decision = resolve_fundraising_subject_binding(evidence(asserted_abn="12 345 678 901"), (candidate(),))
    assert decision.status == "confirmed"
    assert decision.subject_id == "subject:one"
    assert decision.basis == "exact_abn_with_identity_authority"


def test_explicit_relationship_and_verified_controlled_domain_are_separate_resolution_paths():
    relationship = resolve_fundraising_subject_binding(
        evidence(relationship_is_explicit=True, relationship_subject_id="subject:one"), (candidate(),)
    )
    domain = resolve_fundraising_subject_binding(
        evidence(asserted_domain="https://one.example/fundraise", domain_is_subject_controlled=True), (candidate(),)
    )
    assert relationship.basis == "explicit_subject_relationship"
    assert domain.basis == "verified_subject_controlled_domain"


def test_name_only_and_unverified_domain_remain_explicitly_unresolved():
    name_only = resolve_fundraising_subject_binding(evidence(source_native_name="One Charity"), (candidate(),))
    domain_only = resolve_fundraising_subject_binding(evidence(asserted_domain="one.example"), (candidate(),))
    assert name_only.status == domain_only.status == "unresolved"
    assert name_only.basis == domain_only.basis == "insufficient_identity_evidence"


def test_duplicate_exact_abn_and_shared_controlled_domain_remain_ambiguous():
    duplicate_abn = resolve_fundraising_subject_binding(
        evidence(asserted_abn="12345678901"), (candidate(), candidate("subject:two", "12345678901", "two.example"))
    )
    shared_domain = resolve_fundraising_subject_binding(
        evidence(asserted_domain="shared.example", domain_is_subject_controlled=True),
        (candidate("subject:one", "12345678901", "shared.example"), candidate("subject:two", "10987654321", "shared.example")),
    )
    assert duplicate_abn.status == shared_domain.status == "ambiguous"
    assert duplicate_abn.subject_id is None and shared_domain.subject_id is None


def test_invalid_partial_relationship_and_duplicate_candidate_ids_fail_fast():
    with pytest.raises(ValueError, match="explicit relationship"):
        evidence(relationship_subject_id="subject:one")
    with pytest.raises(ValueError, match="unique"):
        resolve_fundraising_subject_binding(evidence(asserted_abn="12345678901"), (candidate(), candidate()))


def test_outcome_counts_keep_resolved_ambiguous_and_unresolved_denominators_visible():
    decisions = (
        resolve_fundraising_subject_binding(evidence(asserted_abn="12345678901"), (candidate(),)),
        resolve_fundraising_subject_binding(evidence(source_native_name="One Charity"), (candidate(),)),
        resolve_fundraising_subject_binding(evidence(asserted_abn="12345678901"), (candidate(), candidate("subject:two", "12345678901"))),
    )
    assert binding_outcome_counts(decisions) == {"ambiguous": 1, "confirmed": 1, "unresolved": 1}
