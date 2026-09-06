from datetime import datetime, timezone

import pytest

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import Observation, ObservationTime, RelationshipStatement, SubjectRecord
from charitygraph.integrated_card import CardEvidence, CoverageInput, IntegratedGraph, SECTION_TITLES, compile_coverage, compile_matrix, project_subject


NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")


def test_canonical_north_star_sections_are_pinned():
    assert SECTION_TITLES == {
        1: "Identity & regulatory status", 2: "Purpose, mandate & cause", 3: "Programs, services, projects & campaigns",
        4: "Populations & beneficiaries", 5: "Geography", 6: "Participation", 7: "Fundraising & resource mobilisation",
        8: "Finance & resource flows", 9: "Governance", 10: "Workforce", 11: "Capability, capacity, access & availability",
        12: "Relationships & ecosystem", 13: "Memberships, schemes, registrations & accreditations", 14: "Ethos & institutional identity",
        15: "Positions, commitments & implementation", 16: "Conduct, adverse matters & compliance", 17: "Notable context & institutional history",
        18: "Outcomes, impact & evaluation", 19: "Classifications & semantic lenses", 20: "Evidence, coverage, freshness & corrections",
    }


def _subject(name: str, abn: str) -> SubjectRecord:
    subject_id = deterministic_id("subject:", {"abn": abn})
    source_id = deterministic_id("srcrec:", {"source_family": "test", "source_version": None, "source_locator": abn, "payload_hash": "a" * 64})
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": subject_id}),
        subject_id=subject_id, subject_kind="organisation", lifecycle_status="active", display_name=name,
        external_identifiers=({"scheme": "ABN", "value": abn},),
        identity_authority_refs=(ArtifactRef(artifact_id=source_id, content_hash="a" * 64, schema=SCHEMA),),
        identity_policy_id="test.identity.v1", created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="test", version="1"),
    )


def _observation(subject_id: str, proposition: str) -> Observation:
    return Observation(
        record_id=deterministic_id("observation:", {"subject_id": subject_id, "proposition": proposition}),
        subject_id=subject_id, predicate="test.proposition", value={"proposition": proposition},
        outcome_state="supported", observation_time=ObservationTime(observed_at=NOW),
        method="retained_fixture", lifecycle_status="held", created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="test", version="1"),
    )


def test_one_observation_can_project_to_multiple_sections_without_duplication():
    subject = _subject("Example Charity", "12345678901")
    observation = _observation(subject.subject_id, "one retained proposition")
    graph = IntegratedGraph(
        subjects=(subject,), scopes=(), observations=(observation,),
        evidence=(CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_GOVERNED", section_ids=(1, 2)),),
    )
    card = project_subject(graph, subject.subject_id)
    sections = {item["section_id"]: item for item in card["sections"]}
    assert sections[1]["observation_ids"] == sections[2]["observation_ids"] == [observation.record_id]
    assert card["observation_ids"] == (observation.record_id,)


def test_experimental_and_missingness_are_distinct_and_empty_is_not_absence():
    subject = _subject("Example Charity", "12345678901")
    observation = _observation(subject.subject_id, "experimental proposition")
    graph = IntegratedGraph(
        subjects=(subject,), scopes=(), observations=(observation,),
        evidence=(CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(18,)),),
        coverage_inputs=(CoverageInput(subject_id=subject.subject_id, section_id=19, state="NOT_PROCESSED", basis="no_domain_result"),),
    )
    coverage = {item.section_id: item for item in compile_coverage(graph)}
    assert coverage[18].missingness == "EXPERIMENTAL_REVIEW"
    assert coverage[19].missingness == "NOT_PROCESSED"
    assert coverage[19].observation_ids == ()


def test_explicit_coverage_states_are_not_negative_assertions():
    subject = _subject("Example Charity", "12345678901")
    states = (
        (2, "SOURCE_SILENT", "processed_source_silent"), (3, "UNKNOWN", "unknown_history"),
        (4, "SOURCE_UNAVAILABLE", "source_unavailable"), (5, "NOT_ACQUIRED", "not_acquired"),
        (6, "NOT_REVIEWED", "not_reviewed"), (7, "NOT_APPLICABLE", "not_applicable"),
        (8, "WITHHELD", "withheld"),
    )
    graph = IntegratedGraph(subjects=(subject,), scopes=(), observations=(), evidence=(), coverage_inputs=tuple(
        CoverageInput(subject_id=subject.subject_id, section_id=section, state=state, basis=basis) for section, state, basis in states
    ))
    coverage = {item.section_id: item for item in compile_coverage(graph)}
    assert [coverage[section].missingness for section, _, _ in states] == [state for _, state, _ in states]
    assert all(not coverage[section].observation_ids for section, _, _ in states)


def test_subject_matrix_is_twenty_rows_by_three_subject_cells():
    subjects = tuple(_subject(name, abn) for name, abn in (("A", "12345678901"), ("B", "12345678902"), ("C", "12345678903")))
    graph = IntegratedGraph(subjects=subjects, scopes=(), observations=(), evidence=(), coverage_inputs=tuple(
        CoverageInput(subject_id=item.subject_id, section_id=1, state="NOT_PROCESSED", basis="no_domain_result") for item in subjects
    ))
    matrix = compile_matrix(graph)
    assert len(matrix) == 20
    assert all(len(row["cells"]) == 3 for row in matrix)


def test_unresolved_historical_assignment_cannot_project_by_numeric_coincidence():
    with pytest.raises(ValueError):
        CardEvidence(observation_id="observation:held", disposition="REUSABLE_EXPERIMENTAL_INPUT", section_ids=(18,), assignment_contract="UNRESOLVED")


def test_directed_relationship_role_survives_graph_and_projection():
    first = _subject("First Charity", "12345678901")
    second = _subject("Partner Charity", "12345678902")
    relation = RelationshipStatement(
        record_id=deterministic_id("relationship:", {"source": first.subject_id, "target": second.subject_id, "role": "funder"}),
        source_subject_id=first.subject_id, target_subject_id=second.subject_id,
        relationship_type="activity_relationship", role="funder", source_role="funder", target_role="deliverer",
        status="candidate", created_at=NOW, producer=ProducerRef(kind="code", producer_id="test", version="1"),
    )
    graph = IntegratedGraph(subjects=(first, second), scopes=(), observations=(), relationships=(relation,), evidence=())
    assert project_subject(graph, first.subject_id)["relationship_ids"] == (relation.record_id,)
    assert graph.relationships[0].role == "funder"
