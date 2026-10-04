"""Render a no-acquisition precision and adversarial-review cohort report.

The input deliberately contains reviewed case labels, not prose to classify.
This is aggregation of governed review outcomes, never a lexical detector.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def fraction(count: int, denominator: int) -> dict[str, int | float | None]:
    return {"count": count, "denominator": denominator,
            "rate": round(count / denominator, 4) if denominator else None}


def build_report(payload: dict) -> dict:
    cases = payload["review_cases"]
    outcomes = Counter(case["outcome"] for case in cases)
    evaluated = outcomes["true_positive"] + outcomes["false_positive"]
    negatives = outcomes["true_negative"] + outcomes["false_negative"]
    return {
        "report_version": "1.0",
        "mode": "cached_governed_review_aggregation_no_acquisition",
        "selection_basis": payload["selection_basis"],
        "cohort": {"handles": fraction(len(payload["cohort"]), len(payload["cohort"])),
                   "identity_status": "unresolved_not_joinable_to_review_cases",
                   "examples": [item["name"] for item in payload["cohort"][:5]]},
        "review": {
            "cases": fraction(len(cases), len(cases)),
            "outcomes": dict(sorted(outcomes.items())),
            "precision_oriented": {
                "supported_promotions": fraction(outcomes["true_positive"], evaluated),
                "false_positives": fraction(outcomes["false_positive"], evaluated),
                "false_negatives": fraction(outcomes["false_negative"], negatives),
                "explicit_refusals": fraction(outcomes["refused"] + outcomes["true_negative"], len(cases)),
                "interpretation": "A review-case gate check, not sector prevalence or production precision."
            },
            "method_coverage": dict(sorted(Counter(case["method"] for case in cases).items())),
            "currentness": dict(sorted(Counter(case["currentness"] for case in cases).items())),
            "source_coverage": dict(sorted(Counter(case["source_coverage"] for case in cases).items())),
            "source_roles": dict(sorted(Counter(case["source_role"] for case in cases).items())),
            "finance_coverage": dict(sorted(Counter(case["finance"] for case in cases).items())),
            "attribution_grain": dict(sorted(Counter(case["attribution_grain"] for case in cases).items())),
            "examples": [{key: case[key] for key in ("id", "outcome", "note")} for case in cases],
        },
        "refusals": [
            "Selection handles are not evidence and are never joined to anonymous review cases.",
            "PFRA membership, regulator permission, ambiguous provider evidence, and scoped silence do not assert F2F practice or currentness.",
            "Aggregate or mixed finance is not allocated to methods, campaigns, providers, or revenue performance metrics.",
            "No ROI, cost-to-raise, donor acquisition, lifetime value, profitability, or causal method-revenue claim is emitted.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/fundraising_precision_cohort_v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(json.loads(args.fixture.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
