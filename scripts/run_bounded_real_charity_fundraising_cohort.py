"""Render the bounded real-charity fundraising cohort audit without acquisition."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def ratio(count: int, denominator: int) -> dict[str, int]:
    return {"count": count, "denominator": denominator}


def build_report(payload: dict) -> dict:
    cohort = payload["cohort"]
    review = json.loads((Path(__file__).resolve().parents[1] / payload["retained_review_fixture"]).read_text(encoding="utf-8"))
    coverage = Counter(item["fundraising_evidence"] for item in cohort)
    finance = Counter(item["finance"] for item in cohort)
    return {
        "report_version": "1.0",
        "mode": "selection_audit_no_acquisition",
        "selection_basis": payload["selection_basis"],
        "cohort_size": len(cohort),
        "metrics": {
            "identity_resolved": ratio(sum(item["identity"] == "resolved" for item in cohort), len(cohort)),
            "fundraising_evidence_coverage": dict(sorted(coverage.items())),
            "structured_finance_coverage": dict(sorted(finance.items())),
            "retained_review_subjects": ratio(len(review["subjects"]), len(review["subjects"])),
            "retained_review_observed_practices": ratio(sum(bool(s["practices"]) for s in review["subjects"]), len(review["subjects"])),
            "retained_review_money_facts": ratio(sum(bool(s["money"]) for s in review["subjects"]), len(review["subjects"])),
        },
        "examples": {
            "real_charity_handles": [item["name"] for item in cohort],
            "retained_review_examples": [subject["display_name"] for subject in review["subjects"]],
        },
        "refusals": [
            "No real-charity handle is promoted to a subject or assigned a fundraising practice.",
            "No F2F lifecycle, provider relationship, campaign, or money attribution is inferred from selection strata.",
            "No financial amount, ROI, cost share, or effectiveness metric is produced.",
        ],
        "boundary": payload["boundary"],
        "next_research_gap": "Rights-cleared, identity-bound source evidence is required before any real-charity observation can be considered; the 287 gate leaves acquisition and production ingestion blocked.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/bounded_real_charity_fundraising_cohort.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(json.loads(args.fixture.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
