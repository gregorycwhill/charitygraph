from datetime import date
import json
from pathlib import Path

import pytest

from charitygraph.fundraising_evidence_roles import EvidenceScope, FundraisingEvidence
from charitygraph.fundraising_method_history import MethodHistoryInput, compile_fundraising_method_histories


PROJECTION = json.loads((Path("tests/fixtures/fundraising_method_history_projection.json")).read_text())


def evidence(identifier: str, observed: date, *, role="first_party_practice_page", facets=("practice", "currentness"), coverage="observed", valid_from=None):
    if "currentness" in facets and valid_from is None:
        valid_from = observed
    return FundraisingEvidence(
        evidence_id=identifier, source_id=f"S-{identifier}", source_role=role,
        locator=f"https://example.test/{identifier}", source_wording=f"source wording {identifier}",
        subject_binding="confirmed", binding_basis="verified registry identifier", observed_at=observed,
        valid_from=valid_from, scope=EvidenceScope(kind="organisation", identifier="ABN:1"),
        production_method="direct_extract", review_status="reviewed", coverage=coverage,
        coverage_description="2026 bounded source inventory" if coverage != "observed" else None,
        asserted_facets=facets,
    )


def test_history_retains_current_recent_historical_and_explicit_cessation_without_staleness_rule():
    history = compile_fundraising_method_histories((
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("H", date(2022, 7, 1), role="annual_report_statement", facets=("practice",)), status="historical"),
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("R", date(2024, 7, 1)), status="recent"),
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("C", date(2025, 7, 1)), status="current"),
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("X", date(2026, 7, 1)), status="discontinued", cessation_date=date(2026, 6, 30)),
    ))[0]
    assert [event.status for event in history.events] == PROJECTION["sequence_statuses"]
    assert history.last_evidenced_at.isoformat() == PROJECTION["last_evidenced_at"]
    assert [item.isoformat() for item in history.explicit_cessation_dates] == PROJECTION["explicit_cessation_dates"]
    assert history.review_required is False
    assert "no freshness" in history.summary_basis


def test_unknown_and_scoped_silence_are_retained_without_creating_practice_or_last_evidenced():
    scoped = evidence("SILENCE", date(2026, 7, 1), role="scoped_source_inventory", facets=(), coverage="not_found_in_scoped_source")
    history = compile_fundraising_method_histories((
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("UNKNOWN", date(2025, 7, 1), facets=("practice",)), status="unknown"),
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=scoped, status="not_found_in_scoped_source"),
    ))[0]
    assert history.last_evidenced_at == PROJECTION["unknown_and_scoped_silence"]["last_evidenced_at"]
    assert [event.practice_observed for event in history.events] == PROJECTION["unknown_and_scoped_silence"]["practice_observed"]
    assert history.events[1].coverage_description == "2026 bounded source inventory"


def test_post_cessation_current_assertion_is_exposed_for_review_not_resolved():
    history = compile_fundraising_method_histories((
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("STOP", date(2025, 7, 2)), status="discontinued", cessation_date=date(2025, 7, 1)),
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("LATER", date(2026, 1, 1)), status="current"),
    ))[0]
    assert history.review_required is PROJECTION["post_cessation_contradiction"]["review_required"]
    assert [item.first_evidence_id for item in history.contradictions] + [item.second_evidence_id for item in history.contradictions] == PROJECTION["post_cessation_contradiction"]["evidence_ids"]


def test_discontinuation_and_scoped_silence_require_explicit_source_boundaries():
    with pytest.raises(ValueError, match="cessation_date"):
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("STOP", date(2025, 7, 1)), status="discontinued")
    with pytest.raises(ValueError, match="scoped non-finding"):
        MethodHistoryInput(method_id="fundraising.face_to_face", evidence=evidence("BAD", date(2025, 7, 1)), status="not_found_in_scoped_source")
