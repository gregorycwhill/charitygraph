from datetime import date

import pytest

from charitygraph.fundraising_evidence_roles import EvidenceScope, FundraisingEvidence
from charitygraph.f2f_currentness import F2FSourceEvidence
from charitygraph.fundraising_inference import (
    NativeFundraisingClaim,
    compile_f2f_practice_observations,
    compile_fundraising_candidates,
)


def evidence(identifier: str, *, role="first_party_practice_page", binding="confirmed", coverage="observed", facets=("practice",)):
    return FundraisingEvidence(
        evidence_id=identifier, source_id=f"source-{identifier}", source_role=role,
        locator=f"/evidence/{identifier}", source_wording="Source-native fundraising assertion: face-to-face fundraising.",
        subject_binding=binding, binding_basis="linked organisation identifier", observed_at=date(2026, 10, 1),
        valid_from=date(2026, 9, 1), scope=EvidenceScope(kind="organisation", identifier="org-1"),
        production_method="governed_semantic_inference", review_status="reviewed", coverage=coverage,
        coverage_description="NSW client directory" if coverage != "observed" else None,
        asserted_facets=facets,
    )


def claim(identifier: str, evidence_id: str, term="fundraising.face_to_face", **updates):
    values = dict(claim_id=identifier, evidence_id=evidence_id, source_phrase="face-to-face fundraising",
                  inference_method="governed_semantic_mapping", canonical_term_id=term,
                  mapping_predicate="close_match")
    values.update(updates)
    return NativeFundraisingClaim(**values)


def test_orthogonal_facets_and_simultaneous_methods_coexist():
    rows = compile_fundraising_candidates((evidence("one", facets=("practice", "setting", "commitment_pattern")),), (
        claim("f2f", "one"), claim("telephone", "one", "fundraising.telephone"),
        claim("private", "one", "fundraising.private_site"),
        claim("recurring", "one", "fundraising.recurring"),
    )).candidates
    assert {row.canonical_term_id for row in rows} == {"fundraising.face_to_face", "fundraising.telephone", "fundraising.private_site", "fundraising.recurring"}
    assert {row.facet for row in rows} == {"solicitation_mechanism", "setting_placement", "commitment_pattern"}
    assert all(row.disposition == "candidate" for row in rows)


def test_campaign_candidate_retains_campaign_identity_alongside_the_method():
    campaign_evidence = evidence("appeal").model_copy(update={
        "source_role": "first_party_campaign_page", "asserted_facets": ("campaign", "channel"),
        "scope": EvidenceScope(kind="campaign", identifier="winter-appeal"),
        "source_wording": "Winter Appeal online fundraising campaign.",
    })
    output = compile_fundraising_candidates((campaign_evidence,), (
        claim("appeal", "appeal", "fundraising.digital", candidate_kind="campaign", campaign_name="Winter Appeal",
              source_phrase="Winter Appeal online fundraising campaign."),
    ))
    candidate = output.candidates[0]
    assert (candidate.candidate_kind, candidate.campaign_name, candidate.canonical_term_id) == ("campaign", "Winter Appeal", "fundraising.digital")


def test_unknown_term_is_preserved_unresolved_not_guessed():
    unknown_evidence = evidence("one").model_copy(update={"source_wording": "Mystery drive."})
    output = compile_fundraising_candidates((unknown_evidence,), (claim("unknown", "one", term=None, mapping_predicate="no_match", source_phrase="mystery drive"),))
    assert output.candidates[0].disposition == "unresolved"
    assert output.candidates[0].canonical_term_id is None
    assert output.unprocessed_claim_ids == ("unknown",)


def test_direct_contact_channels_are_specific_and_composable():
    direct = evidence("direct", facets=("practice", "channel", "digital_distribution")).model_copy(update={
        "source_wording": "Our callers make telephone appeals. Our direct-mail appeal was posted in June. "
        "Text GIVE to donate by SMS. Our email appeal asks supporters to donate. Donate through our website. "
        "Our social appeal asks supporters to donate. We ran paid social advertising for the appeal.",
    })
    output = compile_fundraising_candidates((direct,), (
        claim("telephone", "direct", "fundraising.telephone", source_phrase="Our callers make telephone appeals."),
        claim("mail", "direct", "fundraising.direct_mail", source_phrase="Our direct-mail appeal was posted in June."),
        claim("sms", "direct", "fundraising.sms", source_phrase="Text GIVE to donate by SMS."),
        claim("email", "direct", "fundraising.email", source_phrase="Our email appeal asks supporters to donate."),
        claim("web", "direct", "fundraising.website_donation", source_phrase="Donate through our website."),
        claim("social", "direct", "fundraising.social_media", source_phrase="Our social appeal asks supporters to donate."),
        claim("paid", "direct", "fundraising.paid_digital", source_phrase="We ran paid social advertising for the appeal."),
    ))
    assert {row.canonical_term_id for row in output.candidates} == {
        "fundraising.telephone", "fundraising.direct_mail", "fundraising.sms", "fundraising.email",
        "fundraising.website_donation", "fundraising.social_media", "fundraising.paid_digital",
    }
    assert all(row.disposition == "candidate" for row in output.candidates)


def test_source_phrase_must_bind_direct_mail_candidate_to_retained_wording():
    evidence_row = evidence("mail", facets=("channel",)).model_copy(update={
        "source_wording": "Email supporters about our winter appeal.",
    })
    with pytest.raises(ValueError, match="source phrase is not retained"):
        compile_fundraising_candidates((evidence_row,), (
            claim("mail", "mail", "fundraising.direct_mail", source_phrase="Our direct-mail appeal was posted."),
        ))


def test_direct_mail_can_use_a_source_native_postal_phrase_with_governed_mapping():
    evidence_row = evidence("mail", facets=("channel",)).model_copy(update={
        "source_wording": "We sent a postal appeal to supporters in June.",
    })
    candidate = compile_fundraising_candidates((evidence_row,), (
        claim("mail", "mail", "fundraising.direct_mail", source_phrase="sent a postal appeal to supporters"),
    )).candidates[0]
    assert candidate.canonical_term_id == "fundraising.direct_mail"
    assert candidate.source_phrases == ("sent a postal appeal to supporters",)


def test_supported_practice_families_are_independent_not_competing_categories():
    """One reviewed statement can support several independent practices."""
    families = evidence("families", facets=("practice", "commitment_pattern")).model_copy(update={
        "source_wording": "Join our regular giving program. Fundraise with your friends. Community groups fundraise for us. "
        "Hold a fundraising event. Leave a gift in your Will. Our major gifts program. Partner with us as a business. "
        "Give through your workplace. Enter our charity raffle. Donate goods to our op shop.",
    })
    output = compile_fundraising_candidates((families,), (
        claim("regular", "families", "fundraising.regular_giving", source_phrase="Join our regular giving program."),
        claim("p2p", "families", "fundraising.peer_to_peer", source_phrase="Fundraise with your friends."),
        claim("community", "families", "fundraising.community", source_phrase="Community groups fundraise for us."),
        claim("event", "families", "fundraising.events", source_phrase="Hold a fundraising event."),
        claim("bequest", "families", "fundraising.bequests", source_phrase="Leave a gift in your Will."),
        claim("major", "families", "fundraising.major_gifts", source_phrase="Our major gifts program."),
        claim("corporate", "families", "fundraising.corporate_partnerships", source_phrase="Partner with us as a business."),
        claim("workplace", "families", "fundraising.workplace_giving", source_phrase="Give through your workplace."),
        claim("raffle", "families", "fundraising.raffles_lotteries", source_phrase="Enter our charity raffle."),
        claim("retail", "families", "fundraising.retail_goods_collections", source_phrase="Donate goods to our op shop."),
    ))
    assert {row.canonical_term_id for row in output.candidates} == {
        "fundraising.regular_giving", "fundraising.peer_to_peer", "fundraising.community",
        "fundraising.events", "fundraising.bequests", "fundraising.major_gifts",
        "fundraising.corporate_partnerships", "fundraising.workplace_giving",
        "fundraising.raffles_lotteries", "fundraising.retail_goods_collections",
    }
    assert all(row.disposition == "candidate" for row in output.candidates)


@pytest.mark.parametrize(("term", "native_phrase"), [
    ("fundraising.bequests", "Donations and bequests: $100,000"),
    ("fundraising.grantseeking", "Foundation grant received: $100,000"),
    ("fundraising.corporate_partnerships", "Corporate sponsorship revenue: $100,000"),
])
def test_funding_source_income_cannot_be_promoted_as_a_fundraising_practice(term, native_phrase):
    """A reported receipt is retained as finance evidence, not a method claim."""
    finance = evidence("finance", role="annual_report_statement", facets=()).model_copy(update={
        "source_wording": native_phrase,
    })
    with pytest.raises(ValueError, match="required practice facet"):
        compile_fundraising_candidates((finance,), (
            claim("incorrect-category", "finance", term, source_phrase=native_phrase),
        ))


def test_payment_instrument_requires_its_own_evidence_facet():
    practice = evidence("program", facets=("practice",))
    with pytest.raises(ValueError, match="required payment_transfer_instrument facet"):
        compile_fundraising_candidates((practice,), (
            claim("debit", "program", "fundraising.direct_debit", source_phrase="Pay by direct debit."),
        ))


def test_generic_online_donation_does_not_overclaim_paid_acquisition_or_current_campaign():
    donation_page = evidence("donate-online", facets=("channel",)).model_copy(update={
        "source_wording": "Donate online through our secure website.",
    })
    output = compile_fundraising_candidates((donation_page,), (
        claim("web", "donate-online", "fundraising.website_donation", source_phrase=donation_page.source_wording),
    ))
    candidate = output.candidates[0]
    assert candidate.canonical_term_id == "fundraising.website_donation"
    assert candidate.lifecycle == "unknown"
    with pytest.raises(ValueError, match="required digital_distribution facet"):
        compile_fundraising_candidates((donation_page,), (
            claim("paid", "donate-online", "fundraising.paid_digital", source_phrase=donation_page.source_wording),
        ))
    with pytest.raises(ValueError, match="required donor_relationship_stage facet"):
        compile_fundraising_candidates((donation_page,), (
            claim("acquisition", "donate-online", "fundraising.acquisition", source_phrase=donation_page.source_wording),
        ))
    with pytest.raises(ValueError, match="requires evidence donate-online to assert campaign"):
        compile_fundraising_candidates((donation_page,), (
            claim("campaign", "donate-online", "fundraising.website_donation", candidate_kind="campaign",
                  campaign_name="Undated Donate Page", source_phrase=donation_page.source_wording),
        ))


def test_contradictions_are_linked_not_resolved():
    output = compile_fundraising_candidates((evidence("yes"), evidence("no")), (
        claim("yes", "yes"), claim("no", "no", assertion="explicitly_absent"),
    ))
    assert len(output.candidates) == 2
    assert all(len(row.contradiction_candidate_ids) == 1 for row in output.candidates)


def test_duplicate_evidence_coalesces_without_losing_lineage():
    output = compile_fundraising_candidates((evidence("one"), evidence("two")), (claim("one", "one"), claim("two", "two")))
    assert len(output.candidates) == 1
    assert output.candidates[0].evidence_ids == ("one", "two")
    assert output.candidates[0].claim_ids == ("one", "two")
    assert [item.source_id for item in output.candidates[0].evidence] == ["source-one", "source-two"]
    assert output.candidates[0].evidence[0].locator == "/evidence/one"


def test_any_duplicate_that_is_not_promotable_keeps_the_combined_candidate_review_only():
    pending = evidence("pending").model_copy(update={"review_status": "not_reviewed"})
    output = compile_fundraising_candidates((evidence("reviewed"), pending), (claim("reviewed", "reviewed"), claim("pending", "pending")))
    assert output.candidates[0].disposition == "review_only"


@pytest.mark.parametrize(("lifecycle", "expected"), [("historical", "historical"), ("discontinued", "discontinued")])
def test_historical_and_cessation_states_are_preserved(lifecycle, expected):
    output = compile_fundraising_candidates((evidence(lifecycle),), (claim(lifecycle, lifecycle, lifecycle=lifecycle),))
    assert output.candidates[0].lifecycle == expected


def test_binding_and_role_gate_block_promotion():
    blocked = compile_fundraising_candidates((evidence("ambiguous", binding="ambiguous"),), (claim("ambiguous", "ambiguous"),))
    assert blocked.candidates[0].disposition == "blocked"
    with pytest.raises(ValueError, match="cannot support facets"):
        evidence("pfra", role="pfra_membership")


def f2f_pair(identifier: str, *, lifecycle_role="first_party_f2f_page", common_role="first_party_practice_page",
             currentness="current", binding="confirmed", coverage="observed", facets=("practice", "currentness")):
    valid_to = date(2026, 9, 15) if currentness == "discontinued" else None
    common = evidence(identifier, role=common_role, binding=binding, coverage=coverage, facets=facets).model_copy(update={
        "source_wording": "Our fundraisers speak with supporters face-to-face.",
        "valid_from": date(2026, 9, 1), "valid_to": valid_to, "asserted_facets": facets,
    })
    lifecycle = F2FSourceEvidence(
        evidence_id=identifier, source_role=lifecycle_role, subject_binding=binding,
        source_wording=common.source_wording, observed_at=common.observed_at,
        valid_from=common.valid_from, valid_to=common.valid_to,
        scope=common.scope.model_dump(), source_currentness=currentness,
        source_coverage_description="2026 NSW public client directory" if currentness == "not_found_in_scoped_source" else None,
    )
    return common, lifecycle


def test_f2f_first_party_current_practice_compiles_with_common_provenance():
    common, lifecycle = f2f_pair("f2f-current")
    result = compile_f2f_practice_observations((common,), (lifecycle,))
    observation = result.observations[0]
    assert observation.lifecycle.currentness == "current"
    assert observation.candidate is not None
    assert observation.candidate.canonical_term_id == "fundraising.face_to_face"
    assert observation.candidate.disposition == "candidate"
    assert observation.candidate.evidence[0].locator == "/evidence/f2f-current"


@pytest.mark.parametrize(("role", "common_role", "currentness", "facets"), [
    ("annual_report_statement", "annual_report_statement", "historical", ("practice",)),
    ("explicit_cessation", "first_party_practice_page", "discontinued", ("practice", "currentness")),
])
def test_f2f_historical_and_cessation_remain_time_bounded(role, common_role, currentness, facets):
    common, lifecycle = f2f_pair(f"{role}-{currentness}", lifecycle_role=role, common_role=common_role,
                                  currentness=currentness, facets=facets)
    result = compile_f2f_practice_observations((common,), (lifecycle,))
    assert result.observations[0].candidate.lifecycle == currentness


def test_f2f_pfra_and_scoped_silence_do_not_create_practice_candidates():
    pfra_common, pfra_lifecycle = f2f_pair("pfra-only", lifecycle_role="pfra_membership", common_role="pfra_membership",
                                            facets=())
    silence_common, silence_lifecycle = f2f_pair(
        "scoped-silence", lifecycle_role="scoped_source_inventory", common_role="scoped_source_inventory",
        currentness="not_found_in_scoped_source", coverage="not_found_in_scoped_source", facets=(),
    )
    result = compile_f2f_practice_observations((pfra_common, silence_common), (pfra_lifecycle, silence_lifecycle))
    assert [row.candidate for row in result.observations] == [None, None]
    assert [row.lifecycle.currentness for row in result.observations] == ["unknown", "not_found_in_scoped_source"]


def test_f2f_ambiguous_binding_fails_closed_without_a_candidate():
    common, lifecycle = f2f_pair("ambiguous-f2f", binding="ambiguous")
    result = compile_f2f_practice_observations((common,), (lifecycle,))
    assert result.observations[0].lifecycle.currentness == "unknown"
    assert result.observations[0].candidate is None


def test_f2f_common_and_lifecycle_provenance_must_describe_the_same_assertion():
    common, lifecycle = f2f_pair("mismatch")
    with pytest.raises(ValueError, match="must agree"):
        compile_f2f_practice_observations((common,), (lifecycle.model_copy(update={"source_wording": "Different wording"}),))
