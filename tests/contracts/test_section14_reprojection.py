from datetime import datetime, timezone

import pytest

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import IntegratedGraph, NORTH_STAR_PROJECTION_V0_1, NORTH_STAR_PROJECTION_VNEXT, project_subject
from charitygraph.section14_reprojection import Section14FundingInput, project_section14_observation, section14_card_evidence, section14_missingness


NOW = datetime(2026, 9, 16, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="test", version="1")
SUBJECT_ID = deterministic_id("subject:", {"abn": "74052124375"})
SCOPE_ID = "scope:" + "e" * 64
SOURCE = "srcrec:retained-eja"


def _subject():
    return SubjectRecord(record_id=deterministic_id("subjectrecord:", {"subject": SUBJECT_ID}), subject_id=SUBJECT_ID,
        subject_kind="organisation", lifecycle_status="active", display_name="Synthetic EJA architecture fixture",
        external_identifiers=({"scheme": "ABN", "value": "74052124375"},),
        identity_authority_refs=(ArtifactRef(artifact_id=SOURCE, content_hash="a" * 64, schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")),), identity_policy_id="test", created_at=NOW, producer=PRODUCER)


def _input(predicate="instrument_observed", **updates):
    values = dict(predicate=predicate, funding_context_id="fundctx:eja-note23", subject_id=SUBJECT_ID, scope_id=SCOPE_ID,
        coverage_state="supported", claim_basis="source_fact", source_role="supporting",
        evidence_locator_ids=("locator:eja-p12",), source_record_ids=(SOURCE,), lineage_ids=("artifact:eja-report",), observation_time=ObservationTime(observed_at=NOW), detail="synthetic architecture fixture")
    values.update(updates)
    return Section14FundingInput(**values)


def test_atomic_funding_observation_projects_only_to_v02_section14():
    subject = _subject()
    scope = ScopeRecord(record_id=SCOPE_ID, subject_id=SUBJECT_ID, scope_kind="organisation", created_at=NOW, producer=PRODUCER)
    item = _input("stage_observed", stage="commitment")
    observation = project_section14_observation(item, record_id="observation:" + "1" * 64, created_at=NOW, producer=PRODUCER)
    evidence = section14_card_evidence(item, observation)
    graph = IntegratedGraph(subjects=(subject,), scopes=(scope,), observations=(observation,), evidence=(evidence,))
    active = project_subject(graph, SUBJECT_ID, projection_contract=NORTH_STAR_PROJECTION_VNEXT)
    historical = project_subject(graph, SUBJECT_ID, projection_contract=NORTH_STAR_PROJECTION_V0_1)
    sections = {x["section_id"]: x for x in active["sections"]}
    assert observation.value["funding_context_id"] == "fundctx:eja-note23"
    assert observation.value["stage"] == "commitment"
    assert sections[14]["observation_ids"] == [observation.record_id]
    assert sections[13]["observation_ids"] == []
    assert all(observation.record_id not in x["observation_ids"] for x in historical["sections"])


def test_measure_and_source_reported_dependency_remain_distinct():
    measure = _input("concentration_measure", claim_basis="deterministic_calculation", value="0.787897", numerator_observation_id="observation:" + "2" * 64, denominator_observation_id="observation:" + "3" * 64, calculation_method="same-period category revenue share")
    dependency = _input("dependency_source_reported", claim_basis="source_interpretation", detail="source-reported reliance")
    assert measure.predicate == "concentration_measure"
    assert dependency.predicate == "dependency_source_reported"
    with pytest.raises(ValueError, match="source-reported"):
        _input("dependency_source_reported", claim_basis="source_fact")


def test_unrelated_observation_and_missingness_cannot_be_negative_dependency():
    item = _input()
    unrelated = project_section14_observation(_input("stage_observed", stage="receipt"), record_id="observation:" + "4" * 64, created_at=NOW, producer=PRODUCER)
    with pytest.raises(ValueError, match="matching projected observation"):
        section14_card_evidence(item, unrelated)
    missing = section14_missingness(subject_id=SUBJECT_ID, coverage_state="not_processed")
    assert missing.state == "NOT_PROCESSED"
    assert missing.basis == "no_domain_result"
