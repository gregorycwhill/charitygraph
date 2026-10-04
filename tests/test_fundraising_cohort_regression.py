import json
from pathlib import Path

from scripts.run_fundraising_cohort_regression import build_report


def test_regression_cohort_reports_conservative_denominators_and_negative_controls():
    fixture = json.loads(Path("tests/fixtures/fundraising_cohort_regression.json").read_text(encoding="utf-8"))
    report = build_report(fixture)
    assert report["cohort_size"] == 24
    assert report["metrics"]["pfra_industry_binding_confirmed"] == {"count": 3, "denominator": 5}
    assert report["metrics"]["practice_evidence_observed"] == {"count": 12, "denominator": 24}
    assert report["metrics"]["money_observation_available"] == {"count": 14, "denominator": 24}
    assert report["metrics"]["share_or_bounds_available"] == {"count": 0, "denominator": 14}
    assert report["metrics"]["unresolved_or_ambiguous_binding"] == {"count": 4, "denominator": 24}
    assert report["metrics"]["money_coverage"] == {"available": 14, "not_found": 3, "not_processed": 2, "unavailable": 5}
    assert report["metrics"]["smallest_attribution_grain_for_available_money"] == {"campaign": 2, "organisation": 9, "practice": 2, "provider_relationship": 1}
    assert report["review_examples"]["finance_without_method_attribution"] == ["c03", "c04", "c07", "c09", "c14", "c15", "c16", "c18", "c23"]
