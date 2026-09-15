from datetime import datetime, timezone

import pytest

from charitygraph.contracts.common import ProducerRef
from charitygraph.contracts.knowledge import ObservationTime
from charitygraph.section3_6_11_reprojection import (
    Section3611ProjectionInput, project_section3611_observation, section3611_card_evidence, section3611_missingness,
)

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="section3611-fixture", version="1")
SUBJECT = "subject:" + "1" * 32
SOURCE = "srcrec:" + "2" * 64


def item(predicate="program_or_service_scope_reported", **updates):
    values = dict(predicate=predicate, subject_id=SUBJECT, scope_id="scope:" + "3" * 32, scope_kind="program",
        coverage_state="supported", claim_basis="source_fact", source_role="supporting", evidence_locator_ids=("locator:fixture",),
        source_record_ids=(SOURCE,), lineage_ids=("artifact:fixture",), observation_time=ObservationTime(observed_at=NOW),
        scope_role="program_or_service")
    values.update(updates)
    return Section3611ProjectionInput(**values)


def observation(value):
    return project_section3611_observation(value, record_id="observation:" + "4" * 64, created_at=NOW, producer=PRODUCER)


def test_program_scope_is_v02_section3_only_and_activity_cannot_be_identity():
    value = item()
    evidence = section3611_card_evidence(value, observation(value))
    assert evidence.section_ids == (3,)
    with pytest.raises(ValueError, match="child scope"):
        item(scope_kind="organisation")


def test_participation_opportunity_measure_and_combined_population_remain_distinct():
    opportunity = item("participation_opportunity_reported", scope_kind="organisation", scope_role=None)
    assert section3611_card_evidence(opportunity, observation(opportunity)).section_ids == (6,)
    mixed = item("aggregate_participation_measure_reported", scope_kind="organisation", scope_role=None, value=18450,
        unit="people", participant_population="members_and_volunteers")
    assert observation(mixed).value["participant_population"] == "members_and_volunteers"
    with pytest.raises(ValueError, match="explicit population"):
        item("aggregate_participation_measure_reported", scope_kind="organisation", scope_role=None, value=18450, unit="people")


def test_scheme_recipients_capacity_and_v01_cannot_enter_adapter():
    with pytest.raises(Exception):
        item("scheme_membership")
    with pytest.raises(Exception):
        item("capacity_measure")
    with pytest.raises(Exception):
        item("participation_measure")


def test_scale_is_not_capability_and_capability_is_source_attributed_only():
    scale = item("organisational_scale_measure_reported", scope_kind="organisation", scope_role=None, value=1639, unit="staff")
    assert section3611_card_evidence(scale, observation(scale)).section_ids == (11,)
    claim = item("capability_source_reported", scope_kind="organisation", scope_role=None,
        claim_basis="source_interpretation", detail="source calls its service world-class")
    assert observation(claim).value["claim_basis"] == "source_interpretation"
    with pytest.raises(ValueError, match="source interpretation"):
        item("capability_source_reported", scope_kind="organisation", scope_role=None, detail="capable")


def test_operating_division_and_coordination_do_not_create_ownership_or_scope_leakage():
    division = item("operating_division_reported", scope_kind="other", scope_role="operating_division")
    assert section3611_card_evidence(division, observation(division)).section_ids == (3,)
    coordination = item("coordination_source_reported", scope_kind="service", scope_role="coordination")
    other = observation(coordination).model_copy(update={"scope_id": "scope:" + "5" * 32})
    with pytest.raises(ValueError, match="matching projected"):
        section3611_card_evidence(coordination, other)


def test_missingness_is_non_positive_and_bound_to_one_v02_section():
    missing = section3611_missingness(subject_id=SUBJECT, section_id=11, coverage_state="not_processed")
    assert missing.state == "NOT_PROCESSED"
    assert missing.projection_contract_id == "north-star-v0.2"
