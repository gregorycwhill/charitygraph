from pathlib import Path

import pytest

from charitygraph.scoped_benchmark_v2 import (
    ACTIVITY_VOCABULARY_VERSION,
    CHARITYGRAPH_ACTIVITY_VOCABULARY,
    CLASSIE_RIGHTS_GATE,
    NON_ACTIVITY_FACETS,
    build_scoped_benchmark_v2,
    assert_not_holdout,
    write_private_review_packet,
)


def test_v2_has_multiple_scopes_and_structural_distinctions():
    benchmark = build_scoped_benchmark_v2()
    benchmark.validate()
    smith = [c for c in benchmark.cases if c.subject_name == "The Smith Family"]
    assert {c.concept_or_relation for c in smith if c.scope_kind in {"program", "service"}} >= {"Learning for Life", "student2student"}
    red_cross = [c for c in benchmark.cases if c.subject_name == "Australian Red Cross Society"]
    assert any(c.scope_kind == "division" and c.concept_or_relation == "Lifeblood" for c in red_cross)
    assert any(c.expected_disposition == "prohibited" and c.concept_or_relation == "Lifeblood" for c in red_cross)


def test_mechanism_campaign_portfolio_and_program_are_not_collapsed():
    benchmark = build_scoped_benchmark_v2()
    assert any(c.scope_kind == "mechanism" and c.concept_or_relation == "child sponsorship" for c in benchmark.cases)
    assert any(c.expected_disposition == "prohibited" and "sponsorship as operational" in c.concept_or_relation for c in benchmark.cases)
    assert any(c.scope_kind == "campaign" for c in benchmark.cases)
    assert any(c.expected_disposition == "prohibited" and c.scope_id.endswith("portfolio-as-program") for c in benchmark.cases)


def test_dispositions_and_real_unresolved_case_are_supported():
    benchmark = build_scoped_benchmark_v2()
    dispositions = {case.expected_disposition for case in benchmark.cases}
    assert {"required", "acceptable_secondary", "prohibited", "unresolved"} <= dispositions
    assert any(case.expected_disposition == "unresolved" and not case.evidence_locator_ids for case in benchmark.cases)


def test_proposition_specific_evidence_rejects_unrelated_locator():
    benchmark = build_scoped_benchmark_v2()
    evidence_index = {evidence_id: case.concept_or_relation for case in benchmark.cases for evidence_id in case.evidence_locator_ids}
    benchmark.validate(evidence_index)
    case = next(case for case in benchmark.cases if case.evidence_locator_ids)
    evidence_index[case.evidence_locator_ids[0]] = "unrelated proposition"
    with pytest.raises(ValueError, match="does not support proposition"):
        benchmark.validate(evidence_index)


def test_activity_vocabulary_v2_is_explicit_and_excludes_non_activity_facets():
    assert ACTIVITY_VOCABULARY_VERSION.endswith("-v2")
    assert {"housing_provision", "health_clinical_service_delivery", "workforce_training", "community_development"} <= set(CHARITYGRAPH_ACTIVITY_VOCABULARY)
    assert not (set(CHARITYGRAPH_ACTIVITY_VOCABULARY) & NON_ACTIVITY_FACETS)
    assert "campaign" not in CHARITYGRAPH_ACTIVITY_VOCABULARY


def test_classie_is_blocked_and_native_material_is_not_committed():
    assert CLASSIE_RIGHTS_GATE["status"] == "blocked_pending_rights_review"
    assert CLASSIE_RIGHTS_GATE["native_material_committed"] is False
    assert CLASSIE_RIGHTS_GATE["synthetic_ids_created"] is False


def test_holdout_firewall_is_absolute():
    with pytest.raises(RuntimeError, match="holdout firewall"):
        assert_not_holdout(abn="67649417658")
    with pytest.raises(RuntimeError, match="holdout firewall"):
        assert_not_holdout(subject_name="Life Without Barriers")


def test_private_packet_is_review_only(tmp_path: Path):
    packet = write_private_review_packet(tmp_path)
    text = packet.read_text(encoding="utf-8")
    assert "Status: proposed" in text
    assert "No paid calls" in text
    assert "Lifeblood" in text and "child sponsorship" in text

