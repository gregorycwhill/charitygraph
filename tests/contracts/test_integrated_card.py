from datetime import datetime, timezone

import pytest

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import Observation, ObservationTime, RelationshipStatement, SubjectRecord
from charitygraph.integrated_card import (
    CardEvidence, CoverageInput, IntegratedGraph, NORTH_STAR_PROJECTION_V0_1,
    NORTH_STAR_PROJECTION_VNEXT, NorthStarProjectionContract,
    SECTION_TITLES_V0_1, SECTION_TITLES_VNEXT,
    compile_coverage, compile_matrix, project_subject,
)
from charitygraph.north_star_projection import LENS_SCHEMA, LENS_SCHEMA_VNEXT, NorthStarLensOutput, NorthStarLensOutputVNext


NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")


def test_versioned_north_star_section_maps_are_pinned():
    assert dict(SECTION_TITLES_V0_1) == {
        1: "Identity & regulatory status", 2: "Purpose, mandate & cause", 3: "Programs, services, projects & campaigns",
        4: "Populations & beneficiaries", 5: "Geography", 6: "Participation", 7: "Fundraising & resource mobilisation",
        8: "Finance & resource flows", 9: "Governance", 10: "Workforce", 11: "Capability, capacity, access & availability",
        12: "Relationships & ecosystem", 13: "Memberships, schemes, registrations & accreditations", 14: "Ethos & institutional identity",
        15: "Positions, commitments & implementation", 16: "Conduct, adverse matters & compliance", 17: "Notable context & institutional history",
        18: "Outcomes, impact & evaluation", 19: "Classifications & semantic lenses", 20: "Evidence, coverage, freshness & corrections",
    }
    assert dict(SECTION_TITLES_VNEXT) == {
        1: "Identity / regulatory", 2: "Purpose / cause", 3: "Programs / services",
        4: "Activities / SDGs", 5: "Geography / beneficiaries", 6: "Participation",
        7: "Direct service / capacity", 8: "Fundraising", 9: "Governance / leadership",
        10: "People / workforce", 11: "Scale / capability", 12: "Relationships",
        13: "Finances", 14: "Funding / dependencies", 15: "Ethos / values",
        16: "Conduct / adverse", 17: "Notable history", 18: "Evaluation / outcomes",
        19: "Classification / search / AI discovery",
        20: "Evidence / coverage / freshness / corrections",
    }
    assert SECTION_TITLES_V0_1[7] == "Fundraising & resource mobilisation"
    assert SECTION_TITLES_VNEXT[7] == "Direct service / capacity"


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
    card = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_V0_1)
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
    coverage = {item.section_id: item for item in compile_coverage(graph, projection_contract=NORTH_STAR_PROJECTION_V0_1)}
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
    coverage = {item.section_id: item for item in compile_coverage(graph, projection_contract=NORTH_STAR_PROJECTION_V0_1)}
    assert [coverage[section].missingness for section, _, _ in states] == [state for _, state, _ in states]
    assert all(not coverage[section].observation_ids for section, _, _ in states)


def test_subject_matrix_is_twenty_rows_by_three_subject_cells():
    subjects = tuple(_subject(name, abn) for name, abn in (("A", "12345678901"), ("B", "12345678902"), ("C", "12345678903")))
    graph = IntegratedGraph(subjects=subjects, scopes=(), observations=(), evidence=(), coverage_inputs=tuple(
        CoverageInput(subject_id=item.subject_id, section_id=1, state="NOT_PROCESSED", basis="no_domain_result") for item in subjects
    ))
    matrix = compile_matrix(graph, projection_contract=NORTH_STAR_PROJECTION_V0_1)
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
    assert project_subject(graph, first.subject_id, projection_contract=NORTH_STAR_PROJECTION_V0_1)["relationship_ids"] == (relation.record_id,)
    assert graph.relationships[0].role == "funder"


def test_old_numeric_assignments_are_bound_to_v01_and_never_remapped():
    subject = _subject("Example Charity", "12345678901")
    observation = _observation(subject.subject_id, "historical fundraising observation")
    # This models a retained pre-versioned record. Its compatibility adapter
    # binds it to v0.1; section 7 remains historical fundraising.
    old_assignment = CardEvidence(
        observation_id=observation.record_id,
        disposition="REUSABLE_GOVERNED",
        section_ids=(7,),
    )
    graph = IntegratedGraph(
        subjects=(subject,), scopes=(), observations=(observation,),
        evidence=(old_assignment,),
    )
    old_card = project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_V0_1)
    old_section_7 = old_card["sections"][6]
    assert old_assignment.projection_contract_id == "north-star-v0.1"
    assert old_section_7["title"] == "Fundraising & resource mobilisation"
    assert old_section_7["observation_ids"] == [observation.record_id]

    # The same governed observation can be reused by a separately versioned
    # vNext assignment without changing the observation identity or old map.
    next_assignment = CardEvidence(
        observation_id=observation.record_id,
        disposition="REUSABLE_GOVERNED",
        section_ids=(7,),
        projection_contract_id="north-star-vNext",
    )
    graph_with_both = IntegratedGraph(
        subjects=(subject,), scopes=(), observations=(observation,),
        evidence=(old_assignment, next_assignment),
    )
    next_card = project_subject(graph_with_both, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_VNEXT)
    next_section_7 = next_card["sections"][6]
    assert next_card["projection_contract_id"] == "north-star-vNext"
    assert next_section_7["title"] == "Direct service / capacity"
    assert next_section_7["observation_ids"] == [observation.record_id]
    assert graph_with_both.observations[0].record_id == observation.record_id


def test_projection_calls_require_explicit_contract_and_lens_outputs_are_versioned():
    assert NorthStarLensOutput.projection_contract_id == "north-star-v0.1"
    assert "projection_contract_id" not in LENS_SCHEMA["properties"]
    assert LENS_SCHEMA_VNEXT["properties"]["projection_contract_id"]["const"] == "north-star-vNext"
    assert "projection_contract_id" in LENS_SCHEMA_VNEXT["required"]
    with pytest.raises(TypeError):
        compile_coverage(IntegratedGraph(subjects=(), scopes=(), observations=(), evidence=()))
    forged = NorthStarProjectionContract(
        projection_contract_id="north-star-vNext",
        section_titles={**dict(SECTION_TITLES_VNEXT), 7: "Fundraising"},
        relationship_section_id=12,
    )
    with pytest.raises(ValueError):
        compile_coverage(
            IntegratedGraph(subjects=(), scopes=(), observations=(), evidence=()),
            projection_contract=forged,
        )
    old = NorthStarLensOutput.model_validate({"assignments": [{"observation_key": "O001", "section_ids": [7]}]})
    assert old.projection_contract_id == "north-star-v0.1"
    with pytest.raises(ValueError):
        NorthStarLensOutputVNext.model_validate({"assignments": [{"observation_key": "O001", "section_ids": [7]}]})
    active = NorthStarLensOutputVNext.model_validate({
        "projection_contract_id": "north-star-vNext",
        "assignments": [{"observation_key": "O001", "section_ids": [7]}],
    })
    assert active.projection_contract_id == "north-star-vNext"
    with pytest.raises(ValueError):
        NorthStarLensOutputVNext.model_validate({
            "projection_contract_id": "north-star-vNext",
            "assignments": [{"observation_key": "O001", "section_ids": [21]}],
        })


def test_explicit_missingness_survives_active_projection_contract():
    subject = _subject("Example Charity", "12345678901")
    coverage_input = CoverageInput(
        subject_id=subject.subject_id, section_id=14,
        projection_contract_id="north-star-vNext", state="SOURCE_SILENT",
        basis="processed_source_silent",
    )
    graph = IntegratedGraph(
        subjects=(subject,), scopes=(), observations=(), evidence=(),
        coverage_inputs=(coverage_input,),
    )
    coverage = compile_coverage(graph, projection_contract=NORTH_STAR_PROJECTION_VNEXT)
    section_14 = coverage[13]
    assert section_14.title == "Funding / dependencies"
    assert section_14.projection_contract_id == "north-star-vNext"
    assert section_14.missingness == "SOURCE_SILENT"
