from dataclasses import replace
from pathlib import Path

import pytest

from charitygraph.phase1 import deterministic_subject_id
from charitygraph.scoped_benchmark_v2 import (
    ABNS,
    ACTIVITY_CONCEPT_IDS,
    ACTIVITY_VOCABULARY_VERSION,
    CLASSIE_RIGHTS_GATE,
    HOLDOUT_ABNS,
    SUBJECT_IDS,
    ScopedBenchmarkV2,
    assert_not_holdout,
    build_benchmark_cases,
    build_evidence_registry,
    build_scoped_benchmark_v2,
    write_private_review_packet,
)


def test_evidence_registry_is_independent_and_bindings_are_checked():
    registry = build_evidence_registry()
    benchmark = build_scoped_benchmark_v2(registry)
    benchmark.validate(registry)
    locator, record = next(iter(registry.items()))
    tampered = dict(registry)
    tampered[locator] = replace(record, source_record_id="srcrec:tampered")
    with pytest.raises(ValueError, match="binding mismatch"):
        benchmark.validate(tampered)


def test_swapping_unrelated_source_binding_breaks_validation():
    registry = build_evidence_registry()
    benchmark = build_scoped_benchmark_v2(registry)
    case = next(c for c in benchmark.cases if c.proposition_key == "smith_learning_for_life")
    unrelated = next(c for c in benchmark.cases if c.subject_name == "Australian Red Cross Society" and c.evidence_locator_ids)
    changed = replace(case, evidence_locator_ids=unrelated.evidence_locator_ids)
    changed_benchmark = ScopedBenchmarkV2(tuple(changed if c.case_id == case.case_id else c for c in benchmark.cases))
    with pytest.raises(ValueError, match="subject mismatch|does not support"):
        changed_benchmark.validate(registry)


def test_negative_cases_reuse_real_positive_evidence_and_rules():
    benchmark = build_scoped_benchmark_v2()
    for negative in (c for c in benchmark.cases if c.expected_disposition == "prohibited"):
        assert any(
            positive.expected_disposition != "prohibited"
            and positive.subject_id == negative.subject_id
            and set(negative.evidence_locator_ids) & set(positive.evidence_locator_ids)
            for positive in benchmark.cases
        )


def test_subject_ids_are_actual_deterministic_governed_ids():
    for key, abn in ABNS.items():
        assert SUBJECT_IDS[key] == deterministic_subject_id(identifier_scheme="abn", identifier_value=abn)
    assert all(case.subject_id in SUBJECT_IDS.values() for case in build_scoped_benchmark_v2().cases)


def test_candidate_refs_cannot_masquerade_as_persisted_scope_ids():
    for case in build_scoped_benchmark_v2().cases:
        if case.expected_subject_kind != "organisation":
            assert case.benchmark_scope_ref.startswith("benchmark_scope_ref:")
        assert not (case.benchmark_scope_ref or "").startswith("scope:")


def test_structural_relationships_and_durability_are_explicit():
    benchmark = build_scoped_benchmark_v2()
    assert any(c.relationship_type == "has_division" and c.target_ref for c in benchmark.cases)
    assert any(c.relationship_type == "has_engagement_mechanism" and c.target_ref for c in benchmark.cases)
    assert any(c.relationship_type == "has_operating_scope" and c.target_ref for c in benchmark.cases)
    assert all(c.durability_expectation != "durable_subject" for c in benchmark.cases if c.expected_subject_kind in {"service_domain", "activity", "candidate", "mechanism", "portfolio_scope"})


def test_activity_values_are_exact_v2_ids_and_required_cases_are_exercised():
    benchmark = build_scoped_benchmark_v2()
    values = {c.concept_or_relation for c in benchmark.cases if c.expected_subject_kind == "activity"}
    assert values <= set(ACTIVITY_CONCEPT_IDS)
    assert {"activity.grantmaking", "activity.advocacy", "activity.policy_change", "activity.education_support_delivery", "activity.community_development", "activity.health_clinical_service_delivery", "activity.workforce_training"} <= values
    assert ACTIVITY_VOCABULARY_VERSION.endswith("-v2")


def test_fred_health_and_research_only_negative_case():
    cases = [c for c in build_scoped_benchmark_v2().cases if c.subject_name == "The Fred Hollows Foundation"]
    assert any(c.expected_disposition == "required" and c.concept_or_relation == "activity.health_clinical_service_delivery" for c in cases)
    assert any(c.expected_disposition == "acceptable" and c.concept_or_relation == "activity.workforce_training" for c in cases)
    assert any(c.expected_disposition == "acceptable_secondary" and c.concept_or_relation == "activity.research_evaluation" for c in cases)
    assert any(c.expected_disposition == "prohibited" and c.concept_or_relation == "activity.research_evaluation" for c in cases)


def test_world_vision_mechanism_is_not_activity_and_campaign_is_named():
    cases = build_scoped_benchmark_v2().cases
    assert any(c.expected_subject_kind == "mechanism" and c.concept_or_relation == "child sponsorship" for c in cases)
    assert any(c.expected_disposition == "prohibited" and c.concept_or_relation == "activity.community_engagement" for c in cases)
    conservation = [c for c in cases if c.subject_name == "Australian Conservation Foundation Incorporated"]
    assert any(c.concept_or_relation == "Save our big backyard" and c.expected_subject_kind == "campaign" for c in conservation)


def test_real_evidence_backed_unresolved_cases_exist():
    benchmark = build_scoped_benchmark_v2()
    unresolved = [c for c in benchmark.cases if c.expected_disposition == "unresolved"]
    assert len(unresolved) >= 3
    assert all(c.evidence_locator_ids for c in unresolved)


def test_classie_rights_gate_and_holdout_firewall():
    assert CLASSIE_RIGHTS_GATE["material_discoverable"] is True
    assert CLASSIE_RIGHTS_GATE["native_subject_population_files_exist"] is True
    assert CLASSIE_RIGHTS_GATE["status"] == "blocked_pending_rights_review"
    assert CLASSIE_RIGHTS_GATE["native_material_committed"] is False
    assert not HOLDOUT_ABNS.intersection(ABNS.values())
    with pytest.raises(RuntimeError, match="holdout firewall"):
        assert_not_holdout(abn="67649417658")


def test_private_packet_has_real_urls_selectors_and_proposed_status(tmp_path: Path):
    packet = write_private_review_packet(tmp_path)
    text = packet.read_text(encoding="utf-8")
    assert "Status: proposed" in text
    assert "https://www.acf.org.au/our-work" in text
    assert "heading:Save our big backyard" in text
    assert "No paid calls" in text
