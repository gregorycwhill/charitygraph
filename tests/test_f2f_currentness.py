import json
from datetime import date
from pathlib import Path

import pytest

from charitygraph.f2f_currentness import F2FSourceEvidence, decide_f2f_currentness


CASES = json.loads((Path("tests/fixtures/f2f_currentness_cases.json")).read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_representative_lifecycle_fixtures(case):
    evidence = {key: value for key, value in case.items() if key != "name"}
    decision = decide_f2f_currentness(F2FSourceEvidence.model_validate(evidence))
    expected = {
        "current first-party page": "current", "source-declared recent agency evidence": "recent",
        "dated annual report": "historical",
        "explicit cessation": "discontinued", "scoped source silence": "not_found_in_scoped_source",
        "ambiguous binding": "unknown",
    }[case["name"]]
    assert decision.currentness == expected
    assert decision.evidence_ids == (case["evidence_id"],)


def test_pfra_membership_cannot_become_practice_or_delivery_detail():
    decision = decide_f2f_currentness(F2FSourceEvidence(
        evidence_id="E-PFRA", source_role="pfra_membership", subject_binding="confirmed",
        source_wording="Current PFRA charity member", observed_at=date(2026, 9, 30),
        source_currentness="current", setting="street", delivery_agency="Agency X", regular_giving=True,
    ))
    assert decision.currentness == "unknown"
    assert decision.practice_observed is None
    assert decision.setting is decision.delivery_agency is decision.regular_giving is None


def test_annual_report_cannot_be_promoted_to_current():
    evidence = F2FSourceEvidence(
        evidence_id="E-ANNUAL", source_role="annual_report_statement", subject_binding="confirmed",
        source_wording="F2F appeared in FY2024", observed_at=date(2025, 1, 1), source_currentness="current",
    )
    with pytest.raises(ValueError, match="cannot deterministically support"):
        decide_f2f_currentness(evidence)


def test_scoped_silence_requires_coverage_universe():
    with pytest.raises(ValueError, match="coverage universe"):
        F2FSourceEvidence(
            evidence_id="E-SILENCE", source_role="scoped_source_inventory", subject_binding="confirmed",
            source_wording="No result", observed_at=date(2026, 1, 1),
            source_currentness="not_found_in_scoped_source",
        )


def test_scoped_silence_is_not_promoted_to_practice_absence():
    decision = decide_f2f_currentness(F2FSourceEvidence(
        evidence_id="E-SCOPED-NOT-FOUND", source_role="scoped_source_inventory",
        subject_binding="confirmed", source_wording="No matching client record",
        observed_at=date(2026, 9, 30), source_currentness="not_found_in_scoped_source",
        source_coverage_description="2026 public client list; NSW entries only",
    ))
    assert decision.currentness == "not_found_in_scoped_source"
    assert decision.practice_observed is None
    assert decision.coverage_universe == "2026 public client list; NSW entries only"


def test_expired_validity_cannot_be_relabelled_current():
    with pytest.raises(ValueError, match="cannot be current beyond"):
        F2FSourceEvidence(
            evidence_id="E-EXPIRED", source_role="first_party_f2f_page",
            subject_binding="confirmed", source_wording="F2F activity in FY2024",
            observed_at=date(2026, 9, 30), valid_to=date(2025, 6, 30),
            source_currentness="current",
        )


def test_discontinuation_requires_a_temporal_boundary():
    with pytest.raises(ValueError, match="requires a stated cessation date"):
        F2FSourceEvidence(
            evidence_id="E-UNDATED-STOP", source_role="explicit_cessation",
            subject_binding="confirmed", source_wording="We ceased face-to-face activity.",
            observed_at=date(2026, 9, 30), source_currentness="discontinued",
        )
