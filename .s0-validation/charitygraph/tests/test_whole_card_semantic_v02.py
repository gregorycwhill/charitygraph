import pytest

from charitygraph.whole_card_semantic_v02 import STRICT_SCHEMA, WholeCardExtractionOutputV02, validate_output


def assessments():
    return [{"section_id": i, "status": "insufficient_evidence", "note": None} for i in range(1, 21)]


def observation(evidence=None):
    return {"section_id": 1, "scope": {"kind": "subject", "label": None}, "proposition": "A bounded fact", "epistemic_status": "supported", "temporal_scope": {"kind": "current", "value": None}, "evidence": evidence or [{"source": "S001", "locator": "L0001", "role": "supporting"}], "qualifications": []}


def test_v02_requires_all_twenty_sections_and_supporting_evidence():
    payload = {"section_assessments": assessments(), "observations": [observation()]}
    assert WholeCardExtractionOutputV02.model_validate(payload).observations
    with pytest.raises(ValueError):
        WholeCardExtractionOutputV02.model_validate({"section_assessments": assessments()[:-1], "observations": []})
    with pytest.raises(ValueError):
        WholeCardExtractionOutputV02.model_validate({"section_assessments": assessments(), "observations": [observation([{"source": "S001", "locator": "L0001", "role": "context"}])]})


def test_v02_temporal_scope_includes_as_of():
    value = observation(); value["temporal_scope"] = {"kind": "as_of", "value": "2026-08-30"}
    assert WholeCardExtractionOutputV02.model_validate({"section_assessments": assessments(), "observations": [value]})


def test_v02_compact_citations_resolve_without_opaque_ids():
    packet = {"sources": [{"source_key": "S001", "locators": [{"locator": "S001:L0001", "text": "fact"}, {"locator": "S001:L0002", "text": "more"}]}]}
    value = {"section_assessments": assessments(), "observations": [observation([{"source": "S001", "locator": "L0001-L0002", "role": "supporting"}])], "assignments": [], "relationships": [], "cross_source_issues": []}
    assert validate_output(value, packet).observations
    bad = {**value, "observations": [observation([{"source": "S002", "locator": "L0001", "role": "supporting"}])]}
    with pytest.raises(ValueError):
        validate_output(bad, packet)


def test_v02_assignments_relationships_and_issues_require_supporting_evidence():
    base = {"section_assessments": assessments(), "observations": [], "assignments": [], "relationships": [], "cross_source_issues": []}
    assignment = {"target_scope": {"kind": "subject", "label": None}, "scheme": "UN SDG", "scheme_version": "2026", "concept_id": "SDG1", "concept_label_if_permitted": "No poverty", "evidence": [{"source": "S001", "locator": "L0001", "role": "supporting"}], "rationale": "bounded", "alternatives": [], "qualification": []}
    relationship = {"source_scope": {"kind": "subject", "label": None}, "target_source_native_name": "Partner", "relationship_type": "partnership", "direction": "source_to_target", "temporal_scope": {"kind": "current", "value": None}, "evidence": [{"source": "S001", "locator": "L0001", "role": "supporting"}], "qualification": []}
    issue = {"issue_type": "contradiction", "description": "bounded", "evidence": [{"source": "S001", "locator": "L0001", "role": "supporting"}], "qualification": []}
    value = {**base, "assignments": [assignment], "relationships": [relationship], "cross_source_issues": [issue]}
    packet = {"sources": [{"source_key": "S001", "locators": [{"locator": "S001:L0001", "text": "fact"}]}]}
    assert validate_output(value, packet).assignments


def test_structured_relationship_role_and_target_scope_are_preserved():
    relationship = {
        "source_scope": {"kind": "subject", "label": "Foundation A"},
        "target_source_native_name": "Program Alpha",
        "target_scope": {"kind": "named_program_or_service", "label": "Program Alpha"},
        "role": "funder",
        "relationship_type": "supports",
        "direction": "source_to_target",
        "temporal_scope": {"kind": "current", "value": None},
        "evidence": [{"source": "S001", "locator": "L0001", "role": "supporting"}],
        "qualification": [],
    }
    value = {"section_assessments": assessments(), "observations": [], "assignments": [], "relationships": [relationship], "cross_source_issues": []}
    packet = {"sources": [{"source_key": "S001", "locators": [{"locator": "S001:L0001", "text": "fact"}]}]}
    result = validate_output(value, packet)
    assert result.relationships[0].role == "funder"
    assert result.relationships[0].target_scope.kind == "named_program_or_service"
    relationship_schema = STRICT_SCHEMA["$defs"]["Relationship"]
    assert "role" in relationship_schema["properties"]
    assert "target_scope" in relationship_schema["properties"]
