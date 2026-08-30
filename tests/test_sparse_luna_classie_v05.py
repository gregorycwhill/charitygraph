"""Non-provider tests for sparse experiment mechanics (no controlled taxonomy)."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sparse_runner", ROOT / "scripts" / "run_sparse_luna_classie_v05.py")
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_projected_cost_includes_retry_output_ceiling() -> None:
    projected = runner.projected_cost("x" * 4000, 8000)
    assert projected > 0
    assert projected == runner.projected_cost("x" * 4000, 8000)


def test_classie_schema_is_strict_and_requires_both_arrays() -> None:
    schema = runner.build_classie_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"target_assessments", "assignments"}


def test_taxonomy_blind_view_removes_classification_without_rewriting_observations() -> None:
    observation = {"section_id": 2, "proposition": "A bounded fact"}
    source = {"observations": [observation, {"section_id": 19, "proposition": "reported label"}], "assignments": [{"concept_id": "fake:1"}]}
    blind = runner.build_taxonomy_blind_view(source)
    assert blind["assignments"] == []
    assert blind["observations"] == [observation]
    assert blind["observation_refs"] == {"O001": observation}

