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
        locator=f"/evidence/{identifier}", source_wording="Source-native fundraising assertion.",
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
    rows = compile_fundraising_candidates((evidence("one"),), (
        claim("f2f", "one"), claim("telephone", "one", "fundraising.telephone"),
        claim("private", "one", "fundraising.private_site"),
        claim("recurring", "one", "fundraising.recurring"),
    )).candidates
    assert {row.canonical_term_id for row in rows} == {"fundraising.face_to_face", "fundraising.telephone", "fundraising.private_site", "fundraising.recurring"}
    assert {row.facet for row in rows} == {"solicitation_mechanism", "setting_placement", "commitment_pattern"}
    assert all(row.disposition == "candidate" for row in rows)


def test_campaign_candidate_retains_campaign_identity_alongside_the_method():
    campaign_evidence = evidence("appeal").model_copy(update={
        "source_role": "first_party_campaign_page", "asserted_facets": ("campaign",),
        "scope": EvidenceScope(kind="campaign", identifier="winter-appeal"),
    })
    output = compile_fundraising_candidates((campaign_evidence,), (
        claim("appeal", "appeal", "fundraising.digital", candidate_kind="campaign", campaign_name="Winter Appeal"),
    ))
    candidate = output.candidates[0]
    assert (candidate.candidate_kind, candidate.campaign_name, candidate.canonical_term_id) == ("campaign", "Winter Appeal", "fundraising.digital")


def test_unknown_term_is_preserved_unresolved_not_guessed():
    output = compile_fundraising_candidates((evidence("one"),), (claim("unknown", "one", term=None, mapping_predicate="no_match", source_phrase="mystery drive"),))
    assert output.candidates[0].disposition == "unresolved"
    assert output.candidates[0].canonical_term_id is None
    assert output.unprocessed_claim_ids == ("unknown",)


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
