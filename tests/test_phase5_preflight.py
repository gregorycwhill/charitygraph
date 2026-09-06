from __future__ import annotations

from charitygraph.phase5_preflight import (
    ClaimFamilyPolicy, PlanningUnit, SourceCoverageItem, build_planned_tasks,
    implemented_claim_families, preflight_interruption_safety, proposed_claim_families,
)


def test_claim_family_is_not_a_north_star_section() -> None:
    family = implemented_claim_families()[0]
    assert family.family_id != "section-1"
    assert family.north_star_sections == (1,)


def test_policy_versioning_and_proposed_boundaries_are_explicit() -> None:
    assert all(item.version for item in implemented_claim_families())
    assert all(item.maturity in {"proposed", "high_risk_depth_deferred"} for item in proposed_claim_families())


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
