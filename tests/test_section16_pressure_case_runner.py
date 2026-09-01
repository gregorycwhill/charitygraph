"""Mechanical guardrails for the bounded Section 16 execution runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from charitygraph.contracts.ids import validate_typed_id


def _runner_module():
    path = Path(__file__).parents[1] / "scripts" / "run_section16_pressure_case_v2.py"
    spec = importlib.util.spec_from_file_location("section16_pressure_case_runner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_uses_a_valid_cohort_id_and_only_substantive_bundles():
    runner = _runner_module()

    assert validate_typed_id(runner.COHORT_ID, "cohort:") == runner.COHORT_ID
    assert runner.ALLOWED_BUNDLES == {
        "2020_compliance_action",
        "2023_enforceable_undertaking",
        "2025_compliance_action",
    }
