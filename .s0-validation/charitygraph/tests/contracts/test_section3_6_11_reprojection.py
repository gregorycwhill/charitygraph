from datetime import datetime, timezone
from decimal import Decimal

import pytest

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import Observation, ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import IntegratedGraph, NORTH_STAR_PROJECTION_V0_1, NORTH_STAR_PROJECTION_VNEXT, project_subject
from charitygraph.section3_6_11_reprojection import (
    Section3611ProjectionInput, project_section3611_observation, section3611_card_evidence, section3611_missingness,
)

NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="section3611-fixture", version="1")
SUBJECT = "subject:" + "1" * 32
SOURCE = "srcrec:" + "2" * 64
SCOPE = "scope:" + "3" * 32


def item(predicate="program_or_service_scope_reported", **updates):
    values = dict(predicate=predicate, subject_id=SUBJECT, scope_id=SCOPE, scope_kind="program",
        coverage_state="supported", claim_basis="source_fact", source_role="supporting", evidence_locator_ids=("locator:fixture",),
        source_record_ids=(SOURCE,), lineage_ids=("artifact:fixture",), observation_time=ObservationTime(observed_at=NOW),
        scope_role="program_or_service", detail="retained substantive fixture")
    values.update(updates)
    return Section3611ProjectionInput(**values)


def observation(value, suffix="4"):
    return project_section3611_observation(value, record_id="observation:" + suffix * 64, created_at=NOW, producer=PRODUCER)


def subject():
    return SubjectRecord(record_id=deterministic_id("subjectrecord:", {"subject": SUBJECT}), subject_id=SUBJECT,
        subject_kind="organisation", lifecycle_status="active", display_name="Synthetic C3 architecture fixture",
        external_identifiers=({"scheme": "ABN", "value": "12345678901"},),
        identity_authority_refs=(ArtifactRef(artifact_id=SOURCE, content_hash="a" * 64,
            schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),),
        identity_policy_id="test", created_at=NOW, producer=PRODUCER)


def graph(item_value, extra_observations=(), extra_scopes=()):
    observed = observation(item_value)
    scope = ScopeRecord(record_id=item_value.scope_id, subject_id=SUBJECT, scope_kind=item_value.scope_kind,
        created_at=NOW, producer=PRODUCER)
    return observed, IntegratedGraph(subjects=(subject(),), scopes=(scope,) + tuple(extra_scopes),
        observations=(observed,) + tuple(extra_observations), evidence=(section3611_card_evidence(item_value, observed),))


def sections(graph_value, contract):
    return {row["section_id"]: row for row in project_subject(graph_value, SUBJECT, projection_contract=contract)["sections"]}


def assert_provenance(observed, value):
    assert observed.subject_id == SUBJECT
    assert observed.about_subject_ids == (SUBJECT,)
    assert observed.scope_id == value.scope_id
    assert observed.source_record_ids == (SOURCE,)
    assert observed.evidence_locator_ids == ("locator:fixture",)
    assert observed.observation_time == ObservationTime(observed_at=NOW)
    assert observed.value["source_role"] == "supporting"
    assert tuple(edge.target_artifact_id for edge in observed.lineage) == ("artifact:fixture",)


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
    for bad in (None, "1639", True):
        with pytest.raises(ValueError, match="numeric value and unit"):
            item("organisational_scale_measure_reported", scope_kind="organisation", scope_role=None, value=bad, unit="staff")
    with pytest.raises(ValueError, match="numeric value and unit"):
        item("organisational_scale_measure_reported", scope_kind="organisation", scope_role=None, value=1639, unit=None)
    assert item("organisational_scale_measure_reported", scope_kind="organisation", scope_role=None, value=Decimal("162.97"), unit="FTE").value == Decimal("162.97")


def test_operating_division_is_outside_c3_and_coordination_does_not_create_ownership_or_scope_leakage():
    with pytest.raises(Exception):
        item("operating_division_reported", scope_kind="other", scope_role="operating_division")
    coordination = item("coordination_source_reported", scope_kind="service", scope_role="coordination")
    other = observation(coordination).model_copy(update={"scope_id": "scope:" + "5" * 32})
    with pytest.raises(ValueError, match="matching projected"):
        section3611_card_evidence(coordination, other)


def test_missingness_is_non_positive_and_bound_to_one_v02_section():
    missing = section3611_missingness(subject_id=SUBJECT, section_id=11, coverage_state="not_processed")
    assert missing.state == "NOT_PROCESSED"
    assert missing.projection_contract_id == "north-star-v0.2"
    assert section3611_missingness(subject_id=SUBJECT, section_id=6, coverage_state="processing_failed").state == "PROCESSING_FAILED"
    assert section3611_missingness(subject_id=SUBJECT, section_id=3, coverage_state="not_attempted").state == "NOT_ATTEMPTED"
    for state in ("asserted_none", "observed_absent"):
        with pytest.raises(ValueError, match="non-positive"):
            section3611_missingness(subject_id=SUBJECT, section_id=3, coverage_state=state)
        with pytest.raises(ValueError, match="separately authorised"):
            item(coverage_state=state)


def test_section3_integrated_projection_isolation_and_division_control():
    value = item()
    division_scope = ScopeRecord(record_id="scope:" + "6" * 32, subject_id=SUBJECT, scope_kind="other", created_at=NOW, producer=PRODUCER)
    division = Observation(record_id="observation:" + "7" * 64, created_at=NOW, producer=PRODUCER,
        about_subject_ids=(SUBJECT,), subject_id=SUBJECT, scope_id=division_scope.record_id,
        predicate="source_reported.operating_division", value={"detail": "synthetic Lifeblood adverse control"},
        outcome_state="supported", evidence_locator_ids=("locator:division-control",), source_record_ids=(SOURCE,),
        observation_time=ObservationTime(observed_at=NOW), method="synthetic_c3_control")
    observed, graph_value = graph(value, (division,), (division_scope,))
    active, historical = sections(graph_value, NORTH_STAR_PROJECTION_VNEXT), sections(graph_value, NORTH_STAR_PROJECTION_V0_1)
    assert active[3]["observation_ids"] == [observed.record_id]
    assert active[6]["observation_ids"] == [] and active[11]["observation_ids"] == []
    assert division.record_id not in active[3]["observation_ids"]
    assert all(observed.record_id not in row["observation_ids"] for row in historical.values())
    assert_provenance(observed, value)


def test_section6_integrated_projection_retains_mixed_population_only():
    opportunity = item("participation_opportunity_reported", scope_kind="organisation", scope_role=None)
    aggregate = item("aggregate_participation_measure_reported", scope_kind="organisation", scope_role=None, value=18450,
        unit="people", participant_population="members_and_volunteers")
    opportunity_observed, opportunity_graph = graph(opportunity)
    aggregate_observed = observation(aggregate, "8")
    aggregate_evidence = section3611_card_evidence(aggregate, aggregate_observed)
    graph_value = opportunity_graph.model_copy(update={"observations": (opportunity_observed, aggregate_observed), "evidence": (section3611_card_evidence(opportunity, opportunity_observed), aggregate_evidence)})
    active, historical = sections(graph_value, NORTH_STAR_PROJECTION_VNEXT), sections(graph_value, NORTH_STAR_PROJECTION_V0_1)
    assert active[6]["observation_ids"] == [opportunity_observed.record_id, aggregate_observed.record_id]
    assert active[3]["observation_ids"] == [] and active[11]["observation_ids"] == []
    assert aggregate_observed.value["participant_population"] == "members_and_volunteers"
    assert all(aggregate_observed.record_id not in row["observation_ids"] for row in historical.values())
    assert_provenance(opportunity_observed, opportunity)
    assert_provenance(aggregate_observed, aggregate)


def test_section11_integrated_projection_is_not_capacity_or_historical_assignment():
    scale = item("organisational_scale_measure_reported", scope_kind="organisation", scope_role=None, value=1639, unit="staff")
    claim = item("capability_source_reported", scope_kind="organisation", scope_role=None, claim_basis="source_interpretation", detail="source calls itself capable")
    scale_observed, graph_value = graph(scale)
    claim_observed = observation(claim, "9")
    graph_value = graph_value.model_copy(update={"observations": (scale_observed, claim_observed), "evidence": (section3611_card_evidence(scale, scale_observed), section3611_card_evidence(claim, claim_observed))})
    active, historical = sections(graph_value, NORTH_STAR_PROJECTION_VNEXT), sections(graph_value, NORTH_STAR_PROJECTION_V0_1)
    assert active[11]["observation_ids"] == [scale_observed.record_id, claim_observed.record_id]
    assert active[7]["observation_ids"] == []
    assert claim_observed.value["claim_basis"] == "source_interpretation"
    assert all(scale_observed.record_id not in row["observation_ids"] and claim_observed.record_id not in row["observation_ids"] for row in historical.values())
    assert_provenance(scale_observed, scale)
    assert_provenance(claim_observed, claim)
