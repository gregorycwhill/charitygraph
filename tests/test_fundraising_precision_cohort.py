import json
from pathlib import Path

from scripts.run_fundraising_precision_cohort import build_report


def test_precision_cohort_reports_denominators_refusals_and_adversarial_outcomes():
    fixture = Path("tests/fixtures/fundraising_precision_cohort_v1.json")
    report = build_report(json.loads(fixture.read_text(encoding="utf-8")))
    assert report["cohort"]["handles"] == {"count": 30, "denominator": 30, "rate": 1.0}
    assert report["review"]["outcomes"] == {"refused": 4, "true_negative": 3, "true_positive": 5}
    assert report["review"]["precision_oriented"]["supported_promotions"] == {"count": 5, "denominator": 5, "rate": 1.0}
    assert report["review"]["precision_oriented"]["explicit_refusals"] == {"count": 7, "denominator": 12, "rate": 0.5833}
    assert report["review"]["attribution_grain"]["none"] == 9
    assert "not_joinable" in report["cohort"]["identity_status"]
