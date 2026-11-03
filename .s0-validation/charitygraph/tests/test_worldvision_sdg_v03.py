import json
import importlib.util
from pathlib import Path

_RUNNER_PATH = Path(__file__).parents[1] / "scripts" / "run_worldvision_luna_sdg_v03.py"
_SPEC = importlib.util.spec_from_file_location("worldvision_sdg_v03_runner", _RUNNER_PATH)
runner = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(runner)


def test_taxonomy_blind_view_excludes_section_19_and_assignments(tmp_path: Path, monkeypatch):
    source = {
        "observations": [
            {"section_id": 1, "scope": {"kind": "subject", "label": "World Vision Australia"}, "proposition": "p", "epistemic_status": "supported", "temporal_scope": {"kind": "current", "value": "now"}, "evidence": [], "qualifications": []},
            {"section_id": 19, "scope": {"kind": "named_program_or_service", "label": "Martu Leadership Program"}, "proposition": "old", "epistemic_status": "supported", "temporal_scope": {"kind": "historical", "value": "past"}, "evidence": [], "qualifications": []},
            {"section_id": 19, "scope": {"kind": "named_program_or_service", "label": "Martu Leadership Program"}, "proposition": "old 2", "epistemic_status": "supported", "temporal_scope": {"kind": "historical", "value": "past"}, "evidence": [], "qualifications": []},
            {"section_id": 3, "scope": {"kind": "named_program_or_service", "label": "Martu Leadership Program"}, "proposition": "old 3", "epistemic_status": "supported", "temporal_scope": {"kind": "historical", "value": "past"}, "evidence": [], "qualifications": []},
        ],
        "assignments": [{"scheme": "ACNC CLASSIE"}],
    }
    parsed = tmp_path / "parsed.json"
    parsed.write_text(json.dumps(source), encoding="utf-8")
    monkeypatch.setattr(runner, "KNOWLEDGE_RUN", tmp_path)
    (tmp_path / "packet.sha256").write_text(runner.EXPECTED_SOURCE_PACKET_SHA + "\n", encoding="ascii")
    view, refs = runner.build_knowledge_view(parsed)
    assert len(view["observations"]) == 1
    assert list(refs) == ["O001"]
    assert "assignments" not in view
    assert view["observations"][0]["proposition"] == "p"


def test_mapping_validation_requires_exact_scopes_goals_and_supporting_observation():
    taxonomy = {"concepts": [{"concept_id": "concept:goal"}]}
    refs = {"O001": {"evidence": [{"source": "S001", "locator": "L0001", "role": "supporting"}]}}
    value = {
        "target_assessments": [{"target_scope": {"kind": kind, "label": label}, "status": "no_supported_assignment", "note": "none"} for kind, label in runner.TARGETS],
        "assignments": [{"target_scope": {"kind": "subject", "label": "World Vision Australia"}, "scheme": "un-sdg", "scheme_version": "1", "goal_id": "concept:goal", "supporting_observations": [{"observation_ref": "O001", "role": "supporting"}], "rationale": "r", "alternatives": [], "qualifications": []}],
    }
    result = runner.validate_mapping(value, observation_refs=refs, taxonomy=taxonomy)
    assert result["failures"] == []
    assert result["distinct_goals_used"] == 1


def test_mapping_schema_is_strict_and_provider_is_not_called_by_validation():
    schema = json.loads(Path(runner.__file__).with_name("worldvision_sdg_v03_schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"target_assessments", "assignments"}
    assert schema["properties"]["assignments"]["items"]["additionalProperties"] is False
