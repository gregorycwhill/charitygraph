from __future__ import annotations

from charitygraph.phase5_preflight import (
    ClaimFamilyPolicy, PlanningUnit, SourceCoverageItem, build_planned_tasks,
    build_planning_matrix, classify_reuse_status, implemented_claim_families,
    preflight_interruption_safety, proposed_claim_families,
)


def test_claim_family_is_not_a_north_star_section() -> None:
    family = implemented_claim_families()[0]
    assert family.family_id != "section-1"
    assert family.north_star_sections == (1,)


def test_policy_versioning_and_proposed_boundaries_are_explicit() -> None:
    assert all(item.version for item in implemented_claim_families())
    assert all(item.maturity in {"phase5_planning_accepted", "high_risk_depth_deferred"} for item in proposed_claim_families())
    assert any(item.family_id == "scheme-participation-v1" and item.north_star_sections == (13,) for item in proposed_claim_families())


def test_planned_logical_identity_is_independent_of_physical_bundle() -> None:
    family = implemented_claim_families()[2]
    unit = PlanningUnit(subject_id="subject:" + "a" * 32, abn="12345678901", rank=1, family_id=family.family_id, north_star_sections=family.north_star_sections, applicability="applicable", state="source_ready_constrained_required", method_class="constrained_semantic", source_families=family.expected_source_family_refs, evidence_identity="e" * 64, rationale="test")
    first = build_planned_tasks([unit])[0]
    second = first.model_copy(update={"physical_bundle_opportunity": "bundle:other"})
    assert first.logical_task_id == second.logical_task_id


def test_interruption_safety_blocks_only_ambiguous_collision() -> None:
    result = preflight_interruption_safety()
    assert result["provider_calls"] == 0
    assert result["source_acquisition"] == 0
    assert result["ambiguous_resend_default"] == "blocked"
    assert result["unrelated_claim_family_tasks"] == "not_globally_blocked"


def test_coverage_states_are_distinct_and_not_boolean_completeness() -> None:
    available = SourceCoverageItem(subject_id="subject:" + "a" * 32, abn="12345678901", source_family="official_website", state="acquired_available")
    missing = available.model_copy(update={"state": "not_attempted"})
    failed = available.model_copy(update={"state": "attempted_unavailable"})
    assert {available.state, missing.state, failed.state} == {"acquired_available", "not_attempted", "attempted_unavailable"}
    assert not hasattr(available, "complete")


def test_planning_contract_does_not_offer_fuzzy_semantic_reuse() -> None:
    source = open("src/charitygraph/phase5_preflight.py", encoding="utf-8").read()
    assert "fuzzy" not in source.casefold()
    assert "exact_reusable_validated_candidate" in source


def test_scheme_participation_is_distinct_from_identity_taxonomy_and_relationships() -> None:
    families = {item.family_id: item for item in (*implemented_claim_families(), *proposed_claim_families())}
    scheme = families["scheme-participation-v1"]
    assert scheme.north_star_sections == (13,)
    assert scheme.family_id not in {"identity-regulatory-status-v1", "taxonomy-assignment-v1", "typed-relationship-role-v1"}
    assert scheme.domain_profile == "scheme_participation"


def test_applicability_is_not_missingness() -> None:
    family = proposed_claim_families()[0]
    assert family.applicability_state == "eligible_for_attempt"
    item = SourceCoverageItem(subject_id="subject:" + "b" * 32, abn="12345678901", source_family="annual_report", state="not_attempted")
    assert item.state == "not_attempted"
    assert family.applicability_state != item.state


def test_private_review_state_and_phase6_families_schedule_no_tasks() -> None:
    families = {item.family_id: item for item in proposed_claim_families()}
    assert all(item.default_publication_state == "private_review_only" for item in families.values())
    assert all(families[item].maturity == "high_risk_depth_deferred" for item in (
        "ethos-institutional-identity-proposed-v1", "positions-commitments-implementation-proposed-v1",
        "conduct-compliance-proposed-v1", "outcomes-evaluation-proposed-v1"))


def test_source_ready_stronger_method_classes_route_to_stronger_judgement() -> None:
    families = {item.family_id: item for item in (*implemented_claim_families(), *proposed_claim_families())}
    selected = (families["typed-relationship-role-v1"], families["fundraising-practice-proposed-v1"])
    subject_ids = {"12345678901": "subject:" + "a" * 32}
    cohort = [{"abn": "12345678901", "donation_rank_2024_public": 1}]
    reuse = [type("Reuse", (), {"abn": "12345678901", "evidence_identity": "e" * 64, "exact_reuse_status": "no_prior_result"})()]
    coverage = [SourceCoverageItem(subject_id=subject_ids["12345678901"], abn="12345678901", source_family=source, state="acquired_available") for family in selected for source in family.expected_source_family_refs]
    matrix = build_planning_matrix(cohort, subject_ids, selected, reuse, coverage)
    assert {item.family_id: item.state for item in matrix} == {family.family_id: "stronger_semantic_required" for family in selected}


def test_reuse_requires_structural_validity_and_quote_grounding() -> None:
    assert classify_reuse_status("12345678901", {"structural_output_valid": True, "quote_grounding_valid": True, "action": "completed"}) == "exact_reusable_validated_candidate"
    assert classify_reuse_status("12345678901", {"structural_output_valid": True, "quote_grounding_valid": False, "action": "completed"}) == "structural_valid_grounding_failed"
    assert classify_reuse_status("12345678901", {"structural_output_valid": False, "quote_grounding_valid": False, "action": "completed"}) == "structurally_invalid"
    assert classify_reuse_status("12345678901", {"structural_output_valid": True, "quote_grounding_valid": False, "action": "reused_exact_terra_A"}) == "structural_valid_grounding_failed"


def test_non_grounded_historical_result_is_not_reusable_planning_coverage() -> None:
    family = implemented_claim_families()[2]
    subject_ids = {"12345678901": "subject:" + "b" * 32}
    cohort = [{"abn": "12345678901", "donation_rank_2024_public": 1}]
    reuse = [type("Reuse", (), {"abn": "12345678901", "evidence_identity": "e" * 64, "exact_reuse_status": "structural_valid_grounding_failed"})()]
    coverage = [SourceCoverageItem(subject_id=subject_ids["12345678901"], abn="12345678901", source_family=source, state="acquired_available") for source in family.expected_source_family_refs]
    matrix = build_planning_matrix(cohort, subject_ids, (family,), reuse, coverage)
    assert matrix[0].state == "processing_failure_known"
