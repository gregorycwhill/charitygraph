import json
from pathlib import Path

import pytest

from charitygraph.fundraising_vocabulary import (
    CrosswalkEntry,
    FUNDRAISING_VOCABULARY_V1,
    VocabularyTermReference,
    machine_representation,
    resolve_crosswalk,
)


def test_v1_is_faceted_and_covers_representative_practices():
    terms = {term.term_id: term for term in FUNDRAISING_VOCABULARY_V1.terms}
    for name in (
        "face_to_face", "telephone", "direct_mail", "digital", "bequests",
        "major_gifts", "peer_to_peer", "community", "events",
        "corporate_partnerships", "workplace_giving", "grantseeking",
        "raffles_lotteries", "retail_goods_collections", "emergency_appeal",
    ):
        assert f"fundraising.{name}" in terms
    assert terms["fundraising.regular_giving"].facet == "strategy_program"
    assert terms["fundraising.face_to_face"].facet == "solicitation_mechanism"
    assert terms["fundraising.private_site"].facet == "setting_placement"
    assert terms["fundraising.direct_debit"].facet == "payment_transfer_instrument"


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
    assert json.loads(json.dumps(artifact))["vocabulary_id"] == "charitygraph-fundraising-v1"
    assert artifact["version"] == "1.0.0"
    assert artifact["status"] == "governed_review_only"
    schemes = {item["scheme_id"]: item for item in artifact["source_schemes"]}
    assert schemes["pfra_f2f"]["disposition"] == "mapped"
    assert schemes["fia_awards"]["disposition"] == "reference_only"
    no_matches = [entry for entry in artifact["crosswalk"] if entry["predicate"] == "no_match"]
    assert {entry["scheme_id"] for entry in no_matches} >= {"acnc_ais", "nscoa", "fia_awards"}
    assert all(entry["unresolved_note"] for entry in no_matches)


def test_no_match_cannot_silently_target_a_native_term():
    with pytest.raises(ValueError, match="must not name"):
        CrosswalkEntry(
            scheme_id="example", source_term="example", native_term_ids=("fundraising.digital",),
            predicate="no_match", rationale="test", unresolved_note="test",
        )


def test_exact_crosswalk_lookup_preserves_mapped_and_unmapped_outcomes():
    mapped = resolve_crosswalk("pfra_f2f", "face-to-face fundraising")
    assert mapped.matched is True
    assert mapped.native_terms == (VocabularyTermReference(term_id="fundraising.face_to_face"),)

    no_match = resolve_crosswalk("acnc_ais", "donations and bequests")
    assert no_match.matched is False
    assert no_match.unmapped is not None
    assert no_match.unmapped.reason == "explicit_no_match"

    unknown = resolve_crosswalk("pfra_f2f", "unregistered term")
    assert unknown.matched is False
    assert unknown.unmapped is not None
    assert unknown.unmapped.reason == "not_in_crosswalk"


def test_version_pinned_term_reference_refuses_unknown_native_term():
    with pytest.raises(ValueError, match="unknown fundraising vocabulary v1 term"):
        VocabularyTermReference(term_id="fundraising.other")


def test_crosswalk_fixture_keeps_negative_and_source_silence_cases_explicit():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "fundraising_vocabulary_v1_crosswalk_cases.json").read_text()
    )
    for case in fixture:
        result = resolve_crosswalk(case["scheme_id"], case["source_term"])
        assert result.matched is case["matched"]
        if result.matched:
            assert [reference.term_id for reference in result.native_terms] == case["native_term_ids"]
            assert result.predicate == case["predicate"]
        else:
            assert result.unmapped is not None
            assert result.unmapped.reason == case["unmapped_reason"]
