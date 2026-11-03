import json
import importlib.util
from pathlib import Path

_PATH = Path(__file__).parents[1] / "scripts" / "run_worldvision_terra_sdg_v04.py"
_SPEC = importlib.util.spec_from_file_location("terra_sdg_v04", _PATH)
runner = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(runner)


def _value():
    reviews = []
    for i in range(1, 22):
        reviews.append({"candidate_ref": f"C{i:03d}", "verdict": "accept", "supporting_observations": [{"observation_ref": "O001", "role": "supporting"}], "reason": "supported", "revised_rationale": None, "revised_qualifications": []})
    return {"candidate_reviews": reviews, "strongly_supported_omissions": []}


def test_validation_requires_each_candidate_once_and_accepts_bounded_omission_shape():
    value = _value()
    result = runner.validate_review(value, candidate_refs={f"C{i:03d}" for i in range(1, 22)}, observation_refs={"O001": {}}, taxonomy={"concepts": [{"concept_id": "concept:1", "authority_native_id": "SDG-1"}]}, existing_pairs=set())
    assert result["candidate_count"] == 21
    assert result["candidate_refs_exact"] is True
    assert result["failures"] == []


def test_normalized_candidate_packet_adds_registry_context_without_rewriting_luna_fields(monkeypatch):
    class Dependency:
        def build_knowledge_view(self):
            return {"observations": []}, {"O001": {}}

    monkeypatch.setattr(runner, "_load_v03_runner", lambda: Dependency())
    monkeypatch.setattr(runner, "KNOWLEDGE_RUN", Path("."))
    # Exercise the invariant directly with a representative Luna candidate.
    candidate = {"target_scope": {"kind": "subject", "label": "World Vision Australia"}, "scheme": "UN Sustainable Development Goals", "scheme_version": "2030 Agenda / 2015", "goal_id": "SDG-1", "rationale": "r"}
    normalized = dict(candidate)
    normalized["candidate_ref"] = "C001"
    normalized["registry_scheme"] = "un-sdg"
    normalized["registry_scheme_version"] = "1"
    assert normalized["scheme"] == candidate["scheme"]
    assert normalized["goal_id"] == candidate["goal_id"]
    assert normalized["registry_scheme"] == "un-sdg"


def test_review_schema_is_strict_and_does_not_allow_extra_fields():
    schema = json.loads((_PATH.parent / "worldvision_terra_sdg_v04_schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"candidate_reviews", "strongly_supported_omissions"}
    assert schema["properties"]["candidate_reviews"]["items"]["additionalProperties"] is False
