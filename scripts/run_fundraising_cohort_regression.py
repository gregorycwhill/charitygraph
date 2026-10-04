"""Reproduce the bounded fundraising measurement regression report.

The input is deliberately a source-adapter fixture.  This runner tests policy
and projection boundaries; it neither retrieves sources nor interprets prose.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from charitygraph.f2f_currentness import F2FSourceEvidence, F2FScope, decide_f2f_currentness


def ratio(numerator: int, denominator: int) -> dict[str, int]:
    return {"count": numerator, "denominator": denominator}


def build_report(fixture: dict) -> dict:
    cases = fixture["cases"]
    decisions: list[tuple[dict, str, bool | None]] = []
    for row in cases:
        coverage = "fixture scoped source inventory" if row["role"] == "scoped_source_inventory" else None
        # The F2F policy applies only to its declared source-role vocabulary.
        # The expanded cohort also carries other fundraising methods; their
        # adapter-supplied status is counted without pretending they are F2F.
        if row["role"] not in {
            "pfra_membership", "agency_client", "first_party_f2f_page",
            "annual_report_statement", "historical_campaign_story",
            "explicit_cessation", "scoped_source_inventory", "other",
        }:
            decisions.append((row, row["currentness"], row["binding"] == "confirmed" and bool(row.get("method"))))
            continue
        evidence = F2FSourceEvidence(
            evidence_id=f"fixture:{row['id']}", source_role=row["role"],
            subject_binding=row["binding"], source_wording=row["note"],
            observed_at=date(2026, 10, 4), scope=F2FScope(kind="organisation"),
            source_currentness=row["currentness"], source_coverage_description=coverage,
        )
        decision = decide_f2f_currentness(evidence)
        decisions.append((row, decision.currentness, decision.practice_observed))
    total = len(cases)
    pfra = [row for row in cases if row["role"] == "pfra_membership"]
    available = [row for row in cases if row["money"] == "available"]
    currentness = Counter(currentness for _, currentness, _ in decisions)
    grains = Counter(row["grain"] for row in available)
    practice = [row for row, _, practice_observed in decisions if practice_observed is True]
    candidates = [row for row in cases if row["grain"] in {"campaign", "provider_relationship"}]
    unresolved = [row for row in cases if row["binding"] != "confirmed"]
    risks = [row for row in cases if row["role"] == "pfra_membership" or (row["grain"] == "organisation" and row["money"] == "available")]
    methods = Counter(
        row.get("method", "unspecified") for row, _, practice_observed in decisions
        if practice_observed is True and row.get("method")
    )
    reviewed = [row for row in cases if row.get("review") == "adjudicated"]
    evidence_described = [row for row in cases if row.get("source_id") and row.get("locator") and row.get("wording")]
    contradictions = [row for row in cases if row.get("control") == "contradiction"]
    provider = [row for row in cases if row.get("provider") == "explicit"]
    campaign = [row for row in cases if row.get("campaign") == "explicit"]
    compatibility_rejects = [row for row in cases if row.get("money") == "incompatible_finance"]
    return {
        "report_version": "2.0",
        "cohort_selection_rule": fixture["cohort_selection_rule"],
        "evidence_universe": fixture["evidence_universe"],
        "cohort_size": total,
        "metrics": {
            "pfra_industry_binding_confirmed": ratio(sum(row["binding"] == "confirmed" for row in pfra), len(pfra)),
            "practice_evidence_observed": ratio(len(practice), total),
            "currentness_distribution": dict(sorted(currentness.items())),
            "campaign_or_provider_candidate": ratio(len(candidates), total),
            "money_observation_available": ratio(len(available), total),
            "money_coverage": dict(sorted(Counter(row["money"] for row in cases).items())),
            "smallest_attribution_grain_for_available_money": dict(sorted(grains.items())),
            "share_or_bounds_available": ratio(0, len(available)),
            "unresolved_or_ambiguous_binding": ratio(len(unresolved), total),
            "false_positive_risk_cases": ratio(len(risks), total),
            "per_method_practice_evidence": dict(sorted(methods.items())),
            "adjudicated_cases": ratio(len(reviewed), total),
            "fixture_evidence_descriptor_complete_cases": ratio(len(evidence_described), total),
            "explicit_provider_relationship": ratio(len(provider), total),
            "explicit_campaign": ratio(len(campaign), total),
            "incompatible_finance": ratio(len(compatibility_rejects), total),
            "contradiction_controls": ratio(len(contradictions), total),
        },
        "review_examples": {
            "pfra_not_practice": [row["id"] for row in cases if row["role"] == "pfra_membership"],
            "finance_without_method_attribution": [row["id"] for row in cases if row["money"] == "available" and row["grain"] == "organisation"],
            "negative_controls": [row["id"] for row in cases if row["binding"] != "confirmed" or row["money"] in {"not_found", "not_processed"}],
            "campaign_or_provider": [row["id"] for row in candidates],
            "contradiction_controls": [row["id"] for row in contradictions],
            "incompatible_finance": [row["id"] for row in compatibility_rejects],
        },
        "residual_gaps": [
            "Fixture cohort exercises typed adapter outputs only; it does not establish real-world prevalence.",
            "No source-supported share or bounds fixture is available, so no share/bounds metric is promoted.",
            "Organisation-level financial observations remain explicitly unattributed to a practice, campaign, or provider.",
        ],
        "runtime_and_cost": {
            "source_retrieval_performed": False,
            "provider_calls": 0,
            "runner_mode": "deterministic local fixture projection",
            "bottleneck": "independent source-rights, identity and review adjudication; not compute cost",
        },
        "promotion_status": fixture.get("promotion_status", "local_review_only"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/fundraising_cohort_regression.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(json.loads(args.fixture.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
