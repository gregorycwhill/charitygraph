"""Non-provider invariants for the bounded v0.6 experiment runner."""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
_SPEC = importlib.util.spec_from_file_location("v06_runner", Path(__file__).parents[1] / "scripts" / "run_modest_website_luna_classie_v06.py")
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
CAP = _MODULE.CAP
build_taxonomy_blind_view = _MODULE.build_taxonomy_blind_view
projected = _MODULE.projected


def test_v06_projected_cost_uses_retry_exposure_and_cap_units() -> None:
    estimate = projected("x" * 4000, 8000)
    assert estimate > 0
    assert estimate < CAP


def test_v06_taxonomy_blind_view_removes_section_19_and_assignments() -> None:
    value = {
        "assignments": [{"concept_id": "private"}],
        "observations": [
            {"section_id": 1, "proposition": "retained"},
            {"section_id": 19, "proposition": "removed"},
        ],
    }
    result = build_taxonomy_blind_view(value)
    assert result["assignments"] == []
    assert [item["section_id"] for item in result["observations"]] == [1]
    assert set(result["observation_refs"]) == {"O001"}


def test_v06_retry_projection_is_conservative() -> None:
    short = projected("a", 8000)
    long = projected("a" * 40000, 8000)
    assert long > short
