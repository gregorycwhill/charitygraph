from datetime import date, datetime, timezone

import pytest

from charitygraph.ethos_history import EthosObservation, NotableEvent, notable_event_candidate_id, project_ethos_observation, project_notable_event, v03_missingness
from charitygraph.s0_ethos_notability_routing import route_domain


def test_source_native_observation_routes_to_private_v03_projection_without_inference():
    subject, scope = "subject:" + "a" * 64, "scope:" + "b" * 64
    ethos = EthosObservation(subject_id=subject, scope_id=scope, epistemic_role="self_described", descriptor="stated commitment", source_role="supporting", evidence_locator_ids=("evidence:" + "c" * 64,), source_record_ids=("srcrec:" + "d" * 64,), lineage_ids=("lineage:" + "e" * 64,), observation_time={"observed_at":"2026-01-01T00:00:00Z"})
    obs = project_ethos_observation(ethos, record_id="observation:" + "f" * 64, created_at=datetime.now(timezone.utc), producer={"kind":"code", "producer_id":"test"})
    route = route_domain(section_id=15, risk_family="source_native", source_native=True)
    assert route.disposition == "PRIVATE_PROJECTION"
    assert obs.predicate == "north_star_v03.section15.ethos.self_described"
    assert obs.scope_id == scope and len(obs.source_record_ids) == 1
    assert "quality" not in obs.value and "current_ethos" not in obs.value


def test_history_keeps_date_scope_qualification_and_section_boundary():
    subject, scope = "subject:" + "a" * 64, "scope:" + "b" * 64
    candidate = notable_event_candidate_id(subject_id=subject, scope_id=scope, event_family="public_inquiry_or_review", event_date=date(2020, 1, 2), statement="inquiry reported", related_subject_id=None)
    event = NotableEvent(candidate_id=candidate, subject_id=subject, scope_id=scope, event_family="public_inquiry_or_review", statement="inquiry reported", event_date=date(2020, 1, 2), source_roles=("supporting",), evidence_locator_ids=("evidence:" + "c" * 64,), source_record_ids=("srcrec:" + "d" * 64,), lineage_ids=("lineage:" + "e" * 64,), procedural_status="reported", observation_time={"observed_at":"2026-01-01T00:00:00Z"})
    obs = project_notable_event(event, record_id="observation:" + "f" * 64, created_at=datetime.now(timezone.utc), producer={"kind":"code", "producer_id":"test"})
    assert route_domain(section_id=17, risk_family="historical_temporal", source_native=True).section_id == 17
    assert "event_date" in obs.value
    with pytest.raises(ValueError): route_domain(section_id=16, risk_family="finding")


def test_uncertified_ambiguity_is_disabled_and_missingness_is_explicit():
    assert route_domain(section_id=17, risk_family="identity_scope_lineage", unresolved=True).disposition == "DISABLED"
    assert v03_missingness(subject_id="subject:" + "a" * 64, section_id=17, state="not_found").state == "NOT_FOUND"
