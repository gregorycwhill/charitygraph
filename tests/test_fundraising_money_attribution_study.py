import json
from pathlib import Path

from scripts.render_fundraising_money_attribution_study import INPUT, OUTPUT, render, validate


def test_study_is_valid_and_render_is_reproducible():
    study = json.loads(INPUT.read_text(encoding="utf-8"))
    validate(study)
    assert render(study) == OUTPUT.read_text(encoding="utf-8")


def test_aggregate_negative_cases_are_explicit():
    study = json.loads(INPUT.read_text(encoding="utf-8"))
    by_id = {case["id"]: case for case in study["cases"]}
    assert by_id["c14"]["smallest_justified_scope"] == "organisation"
    assert "MUST NOT split" in by_id["c14"]["incompatibilities"]
    assert by_id["c15"]["smallest_justified_scope"] == "fundraising_portfolio"
    assert "MUST NOT allocate" in by_id["c15"]["incompatibilities"]
    assert all(Path(case["locator"]).suffix != ".pdf" or case["locator"].startswith("http") for case in study["cases"])
