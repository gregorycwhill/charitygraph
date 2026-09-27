from __future__ import annotations

import importlib.util
from pathlib import Path


def runner():
    path = Path(__file__).parents[1] / "scripts" / "run_sparse_whole_card_calibration_v01.py"
    spec = importlib.util.spec_from_file_location("sparse_calibration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sparse_experiment_cost_guard_uses_luna_and_terra_rates_separately():
    module = runner()
    projected = module.projected_exposure(b"x" * 1000, b"prompt")
    assert projected["gpt-5.6-terra"] > projected["gpt-5.6-luna"]
    assert sum(projected.values()) < module.SPEND_CAP_USD
