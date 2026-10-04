import json

import pytest

from charitygraph.fundraising_vocabulary import (
    CrosswalkEntry,
    FUNDRAISING_VOCABULARY_V1,
    machine_representation,
)


def test_candidate_is_faceted_and_covers_representative_practices():
    terms = {term.term_id: term for term in FUNDRAISING_VOCABULARY_V1.terms}
    for name in (
        "face_to_face", "telephone", "direct_mail", "digital", "bequests",
        "sms", "email", "website_donation", "social_media", "search", "paid_digital", "organic_digital",
        "major_gifts", "peer_to_peer", "community", "events",
        "corporate_partnerships", "workplace_giving", "grantseeking",
        "raffles_lotteries", "retail_goods_collections", "emergency_appeal",
    ):
        assert f"fundraising.{name}" in terms
    assert terms["fundraising.regular_giving"].facet == "strategy_program"
    assert terms["fundraising.face_to_face"].facet == "solicitation_mechanism"
    assert terms["fundraising.private_site"].facet == "setting_placement"
    assert terms["fundraising.direct_debit"].facet == "payment_transfer_instrument"
    assert terms["fundraising.paid_digital"].facet == "digital_distribution"
    assert "acquisition" in terms["fundraising.website_donation"].exclusions[0]


def test_regular_giving_f2f_example_is_composable_not_a_compound_term():
    terms = {term.term_id: term for term in FUNDRAISING_VOCABULARY_V1.terms}
    compatible = {
        "fundraising.regular_giving", "fundraising.face_to_face",
        "fundraising.private_site", "fundraising.recurring",
        "fundraising.direct_debit", "fundraising.acquisition",
        "fundraising.external_agency",
    }
    assert compatible <= set(terms)
    assert len({terms[item].facet for item in compatible}) == len(compatible)
    assert not any("regular_giving_face_to_face" in item.term_id for item in terms.values())


def test_external_schemes_are_governed_separately_and_non_equivalences_survive():
    artifact = machine_representation()
    assert json.loads(json.dumps(artifact))["status"] == "candidate"
    schemes = {item["scheme_id"]: item for item in artifact["source_schemes"]}
    assert schemes["pfra_f2f"]["disposition"] == "mapped"
    assert schemes["fia_awards"]["disposition"] == "reference_only"
    no_matches = [entry for entry in artifact["crosswalk"] if entry["predicate"] == "no_match"]
    assert {entry["scheme_id"] for entry in no_matches} >= {"acnc_ais", "nscoa", "fia_awards"}
    assert all(entry["unresolved_note"] for entry in no_matches)


def test_no_match_cannot_silently_target_a_native_term():
    with pytest.raises(ValueError, match="must not name"):
        CrosswalkEntry(
            scheme_id="example", source_term="example", native_term_id="fundraising.digital",
            predicate="no_match", rationale="test", unresolved_note="test",
        )
