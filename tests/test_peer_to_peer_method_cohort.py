"""Bounded, local regression controls for the peer-to-peer method family.

The rows are deliberately source-free fixtures.  They quantify exercised
compiler outcomes, not external precision, recall, prevalence, or current use.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path

from charitygraph.fundraising_evidence_roles import EvidenceScope, FundraisingEvidence
from charitygraph.fundraising_inference import NativeFundraisingClaim, compile_fundraising_candidates


FIXTURE = Path(__file__).parent / "fixtures" / "peer_to_peer_method_cohort.json"


def _evidence(case_id: str, phrase: str, *, binding: str = "confirmed", facets: tuple[str, ...] = ("practice",)):
    return FundraisingEvidence(
        evidence_id=case_id, source_id=f"fixture:{case_id}", source_role="first_party_practice_page",
        locator=f"fixture://{case_id}", source_wording=phrase, subject_binding=binding,
        binding_basis="fixture binding control", observed_at=date(2026, 10, 5),
        scope=EvidenceScope(kind="organisation", identifier="fixture-org"),
        production_method="governed_semantic_inference", review_status="reviewed",
        coverage="observed", asserted_facets=facets,
    )


def _result(case: dict[str, str]):
    expected = case["expected"]
    if expected == "candidate":
        evidence = _evidence(case["case_id"], case["source_phrase"])
        claim = NativeFundraisingClaim(
            claim_id=case["case_id"], evidence_id=evidence.evidence_id, source_phrase=case["source_phrase"],
            inference_method="governed_semantic_mapping", canonical_term_id="fundraising.peer_to_peer",
            mapping_predicate="close_match",
        )
    elif expected == "blocked":
        evidence = _evidence(case["case_id"], case["source_phrase"], binding="ambiguous")
        claim = NativeFundraisingClaim(
            claim_id=case["case_id"], evidence_id=evidence.evidence_id, source_phrase=case["source_phrase"],
            inference_method="governed_semantic_mapping", canonical_term_id="fundraising.peer_to_peer",
            mapping_predicate="close_match",
        )
    else:
        # A generic donation page, event, or platform reference is retained as
        # native wording but deliberately receives no peer-to-peer mapping.
        evidence = _evidence(case["case_id"], case["source_phrase"], facets=("channel",))
        claim = NativeFundraisingClaim(
            claim_id=case["case_id"], evidence_id=evidence.evidence_id, source_phrase=case["source_phrase"],
            inference_method="governed_semantic_mapping", mapping_predicate="no_match",
        )
    return compile_fundraising_candidates((evidence,), (claim,))


def test_peer_to_peer_fixture_cohort_has_positive_and_refusal_controls_with_explicit_denominators():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["status"] == "local_review_only_fixture"
    outcomes = {case["case_id"]: _result(case) for case in fixture["cases"]}
    dispositions = Counter(result.candidates[0].disposition for result in outcomes.values())

    assert dispositions == {"candidate": 2, "unresolved": 3, "blocked": 1}
    assert sum(dispositions.values()) == 6
    assert all(
        outcomes[case["case_id"]].candidates[0].disposition == case["expected"]
        for case in fixture["cases"]
    )
    assert all(
        outcomes[case["case_id"]].unprocessed_claim_ids == (case["case_id"],)
        for case in fixture["cases"] if case["expected"] == "unresolved"
    )


def test_peer_to_peer_negative_controls_never_become_method_or_platform_inferences():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        if case["expected"] != "unresolved":
            continue
        candidate = _result(case).candidates[0]
        assert candidate.canonical_term_id is None
        assert candidate.facet is None
        assert candidate.disposition == "unresolved"
