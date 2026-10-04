import json
from pathlib import Path

from scripts.run_bounded_real_charity_fundraising_cohort import build_report


FIXTURE = Path(__file__).parent / "fixtures" / "bounded_real_charity_fundraising_cohort.json"


def test_bounded_cohort_is_reproducible_and_explicitly_sparse():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report = build_report(payload)
    assert report == build_report(payload)
    assert report["cohort_size"] == 10
    assert report["metrics"]["identity_resolved"] == {"count": 0, "denominator": 10}
    assert report["metrics"]["fundraising_evidence_coverage"] == {"not_processed": 10}
    assert report["metrics"]["structured_finance_coverage"] == {"not_processed": 10}
    assert len(report["examples"]["real_charity_handles"]) == 10


def test_real_handles_and_anonymous_review_fixture_cannot_be_conflated():
    report = build_report(json.loads(FIXTURE.read_text(encoding="utf-8")))
    rendered = json.dumps(report).lower()
    assert "no real-charity handle is promoted" in rendered
    assert "roi" in rendered  # refusal wording, not a metric
    assert report["metrics"]["retained_review_subjects"] == {"count": 4, "denominator": 4}
