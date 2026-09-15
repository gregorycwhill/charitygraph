from datetime import datetime, timezone

import pytest

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.direct_service import DirectServiceEvidenceRef, DirectServiceProposition
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import (
    CardEvidence, IntegratedGraph, NORTH_STAR_PROJECTION_V0_1,
    NORTH_STAR_PROJECTION_VNEXT, project_subject,
)
from charitygraph.section7_reprojection import (
    Section7V02ProjectionInput, reproject_section7, reproject_section7_v02,
    section7_missingness,
)


NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")
PRODUCER = ProducerRef(kind="code", producer_id="test", version="1")
RETAINED_SERVICE_OFFER_SCOPE = "scope:4a5ff8981562c2626b83fbd0dfd772b8dd0cd96c7acb1f316f798432056b71b1"
RETAINED_SERVICE_OFFER_LOCATOR = "locator:c6dd10a3ccd39d7a9e16bec2feda7facc8b1d92c15cb17073b6f23c29cc255eb"
RETAINED_UNTIMED_AVAILABILITY_SCOPE = "scope:046eb592e030f4657d7d76245a962e6b9734f2ccc889a927a44f1cb94e7106e2"
RETAINED_UNTIMED_AVAILABILITY_LOCATOR = "locator:f7780f635edfaa67a01f5f70421371b0d1e0834c4363b7b8c25d9fbc30da0e76"
SOURCE = "srcrec:retained-section7"


def _subject() -> SubjectRecord:
    subject_id = deterministic_id("subject:", {"abn": "12345678901"})
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": subject_id}),
        subject_id=subject_id,
        subject_kind="organisation",
        lifecycle_status="active",
        display_name="Retained Section 7 Fixture",
        external_identifiers=({"scheme": "ABN", "value": "12345678901"},),
        identity_authority_refs=(ArtifactRef(artifact_id=SOURCE, content_hash="a" * 64, schema=SCHEMA),),
        identity_policy_id="test.identity.v1",
        created_at=NOW,
        producer=PRODUCER,
    )


def _scope(subject: SubjectRecord) -> ScopeRecord:
    return ScopeRecord(
        record_id=RETAINED_SERVICE_OFFER_SCOPE,
        subject_id=subject.subject_id,
        scope_kind="organisation",
        label="Retained organisation scope",
        created_at=NOW,
        producer=PRODUCER,
    )


def _proposition(kind: str = "service_offer", **updates) -> DirectServiceProposition:
    value = {
        "proposition_type": kind,
        "scope_id": RETAINED_SERVICE_OFFER_SCOPE,
        "scope_kind": "organisation",
        "coverage_state": "supported",
        "value": "retained fact",
        "evidence": (DirectServiceEvidenceRef(locator=RETAINED_SERVICE_OFFER_LOCATOR, role="supporting"),),
    }
    value.update(updates)
    return DirectServiceProposition(**value)


def test_section7_reprojection_is_explicitly_v02_and_never_section11():
    subject = _subject()
    scope = _scope(subject)
    replay = reproject_section7(_proposition())
    observation = __import__("charitygraph.contracts.direct_service", fromlist=["project_observation"]).project_observation(
        replay.proposition,
        record_id="observation:" + "2" * 64,
        subject_id=subject.subject_id,
        scope_id=scope.record_id,
        source_record_ids=(SOURCE,),
        created_at=NOW,
        producer=PRODUCER,
        method="retained_section7_reprojection",
    )
    graph = IntegratedGraph(
        subjects=(subject,),
        scopes=(scope,),
        observations=(observation,),
        evidence=(replay.card_evidence(observation.record_id),),
    )
    active = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_VNEXT)
    historical = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_V0_1)
    sections = {item["section_id"]: item for item in active["sections"]}
    assert active["projection_contract_id"] == "north-star-v0.2"
    assert sections[7]["observation_ids"] == [observation.record_id]
    assert sections[11]["observation_ids"] == []
    assert observation.scope_id == scope.record_id
    assert observation.evidence_locator_ids == (RETAINED_SERVICE_OFFER_LOCATOR,)
    assert observation.source_record_ids == (SOURCE,)
    assert historical["sections"][6]["observation_ids"] == []


def test_service_offer_cannot_become_availability_or_capacity():
    replay = reproject_section7(_proposition("service_offer"))
    assert replay.proposition.proposition_type == "service_offer"
    assert replay.section_ids == (7,)


def test_eligibility_and_access_remain_independent():
    eligibility = reproject_section7(_proposition("eligibility"))
    access = reproject_section7(_proposition("access_pathway"))
    assert eligibility.proposition.proposition_type == "eligibility"
    assert access.proposition.proposition_type == "access_pathway"


def test_retained_untimed_current_availability_cannot_be_projected_as_positive():
    availability = DirectServiceProposition(
        proposition_type="current_availability",
        scope_id=RETAINED_UNTIMED_AVAILABILITY_SCOPE,
        scope_kind="organisation",
        coverage_state="supported",
        value="reported available",
        evidence=(DirectServiceEvidenceRef(locator=RETAINED_UNTIMED_AVAILABILITY_LOCATOR, role="supporting"),),
    )
    with pytest.raises(ValueError, match="explicit retained time"):
        reproject_section7(availability)


def test_positive_capacity_requires_retained_time():
    with pytest.raises(ValueError, match="explicit retained time"):
        reproject_section7(_proposition("capacity_measure", unit="places", value=24, observation_time=None))


def test_positive_capacity_requires_value_and_unit_even_with_time():
    time = ObservationTime(observed_at=NOW)
    with pytest.raises(ValueError, match="value and unit"):
        reproject_section7(_proposition("capacity_measure", value=None, unit="places", observation_time=time))


def test_not_processed_survives_as_v02_coverage_without_negative_assertion():
    subject = _subject()
    coverage = section7_missingness(
        subject_id=subject.subject_id,
        coverage_state="not_processed",
        note="retained finite evidence universe did not process service capacity",
    )
    graph = IntegratedGraph(subjects=(subject,), scopes=(), observations=(), evidence=(), coverage_inputs=(coverage,))
    section = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_VNEXT)["sections"][6]
    assert section["missingness"] == "NOT_PROCESSED"
    assert section["basis"] == "no_domain_result"
    assert section["observation_ids"] == []


def test_non_service_direct_service_types_cannot_project_to_section7():
    with pytest.raises(ValueError, match="only direct-service"):
        reproject_section7(_proposition("scheme_membership", scheme_id="scheme:x"))


def _v02(predicate: str, **updates) -> Section7V02ProjectionInput:
    """Synthetic architecture fixture; it asserts no retained empirical fact."""
    value = {
        "predicate": predicate,
        "subject_id": _subject().subject_id,
        "scope_id": RETAINED_SERVICE_OFFER_SCOPE,
        "scope_kind": "organisation",
        "coverage_state": "supported",
        "source_role": "supporting",
        "evidence_locator_ids": ("locator:architecture-fixture",),
        "source_record_ids": (SOURCE,),
        "lineage_ids": ("lineage:architecture-fixture",),
        "observation_time": ObservationTime(observed_at=NOW),
    }
    value.update(updates)
    return Section7V02ProjectionInput(**value)


def test_v02_advertised_availability_is_not_current_availability_and_never_claims_freshness():
    item = _v02("advertised_availability", availability_status="available")
    replay = reproject_section7_v02(item)
    assert replay.projection.predicate == "advertised_availability"
    assert replay.projection.freshness_state == "unassessed"
    with pytest.raises(ValueError, match="freshness policy"):
        _v02("advertised_availability", availability_status="available", freshness_state="fresh")


def test_v02_operating_hours_is_not_current_availability():
    item = _v02("operating_hours", detail="09:00-17:00 weekdays")
    assert reproject_section7_v02(item).projection.predicate == "operating_hours"


def test_v02_throughput_is_not_capacity_measure():
    item = _v02("throughput", value=18, unit="appointments per week")
    assert reproject_section7_v02(item).projection.predicate == "throughput"


def test_v02_waitlist_is_not_capacity_merely_by_existing():
    item = _v02("waitlist", detail="waitlist reported")
    assert reproject_section7_v02(item).projection.predicate == "waitlist"


@pytest.mark.parametrize("predicate", ["staffing_constraint", "resource_constraint"])
def test_v02_constraints_are_not_positive_capacity_measures(predicate):
    item = _v02(predicate, detail="constraint reported")
    assert reproject_section7_v02(item).projection.predicate == predicate


def test_v02_delivery_evidence_is_not_a_generic_service_offer():
    item = _v02("delivery_evidence", detail="delivery event reported")
    assert reproject_section7_v02(item).projection.predicate == "delivery_evidence"


@pytest.mark.parametrize("predicate, updates", [
    ("advertised_availability", {"availability_status": "available", "observation_time": None}),
    ("operating_hours", {"detail": "09:00-17:00", "observation_time": None}),
    ("throughput", {"value": 2, "unit": "people/day", "observation_time": None}),
    ("waitlist", {"detail": "reported", "observation_time": None}),
])
def test_v02_supported_time_sensitive_predicates_require_time(predicate, updates):
    with pytest.raises(ValueError, match="require observation_time"):
        _v02(predicate, **updates)


def test_v02_predicate_assigns_only_active_section7():
    replay = reproject_section7_v02(_v02("delivery_evidence", detail="delivery event reported"))
    observation = replay.observation(record_id="observation:" + "3" * 64, created_at=NOW, producer=PRODUCER)
    evidence = replay.card_evidence(observation)
    assert evidence.projection_contract_id == "north-star-v0.2"
    assert evidence.section_ids == (7,)
    assert "section-11" in evidence.note


@pytest.mark.parametrize("predicate, updates, identifier", [
    ("advertised_availability", {"availability_status": "available"}, "5"),
    ("throughput", {"value": 18, "unit": "appointments per week"}, "6"),
    ("staffing_constraint", {"detail": "staff vacancy reported"}, "7"),
    ("delivery_evidence", {"detail": "delivery event reported"}, "8"),
])
def test_v02_predicates_survive_governed_observation_and_integrated_projection(predicate, updates, identifier):
    """Synthetic architecture fixture; it asserts no retained empirical fact."""
    subject = _subject()
    scope = _scope(subject)
    replay = reproject_section7_v02(_v02(predicate, **updates))
    observation = replay.observation(
        record_id="observation:" + identifier * 64,
        created_at=NOW,
        producer=PRODUCER,
    )
    evidence = replay.card_evidence(observation)
    graph = IntegratedGraph(
        subjects=(subject,), scopes=(scope,), observations=(observation,), evidence=(evidence,),
    )
    active = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_VNEXT)
    historical = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_V0_1)
    active_sections = {item["section_id"]: item for item in active["sections"]}
    assert observation.predicate == f"north_star_v02.section7.{predicate}"
    assert observation.value["section7_predicate"] == predicate
    assert observation.subject_id == subject.subject_id
    assert observation.scope_id == scope.record_id
    assert observation.observation_time == ObservationTime(observed_at=NOW)
    assert observation.evidence_locator_ids == ("locator:architecture-fixture",)
    assert observation.source_record_ids == (SOURCE,)
    assert observation.lineage[0].target_artifact_id == "lineage:architecture-fixture"
    assert active_sections[7]["observation_ids"] == [observation.record_id]
    assert active_sections[11]["observation_ids"] == []
    assert all(observation.record_id not in item["observation_ids"] for item in historical["sections"])


def test_v02_card_evidence_rejects_an_unrelated_observation():
    advertised = reproject_section7_v02(_v02("advertised_availability", availability_status="available"))
    unrelated = reproject_section7_v02(_v02("delivery_evidence", detail="delivery event reported")).observation(
        record_id="observation:" + "4" * 64, created_at=NOW, producer=PRODUCER,
    )
    with pytest.raises(ValueError, match="matching projected observation"):
        advertised.card_evidence(unrelated)
