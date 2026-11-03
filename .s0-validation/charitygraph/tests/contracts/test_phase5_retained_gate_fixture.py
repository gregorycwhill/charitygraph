"""Literal retained-cohort fixture for the Phase 5 completion gate.

The fixture is deliberately offline and deterministic.  Its positive rows are
transcriptions of the named C1--C9 retained controls; every other card cell is
an explicit coverage record.  It does not extract, infer, or promote anything.
"""
from datetime import datetime, timezone

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import Observation, ObservationTime, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import CardEvidence, CoverageInput, IntegratedGraph, NORTH_STAR_PROJECTION_VNEXT, compile_matrix, project_subject

NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")
# These are the fixed, retained gate subjects.  Lifeblood is a scope of ARC.
COHORT = (
    ("Australian Red Cross Society", "50169561394", "ARC FY2022-23 retained annual-report control"),
    ("Environmental Justice Australia", "74052124375", "EJA FY2024-25 retained financial-report control"),
    ("Fitted for Work", "78126256862", "Fitted for Work FY2023-24 retained report control"),
    ("APNIC Foundation Limited", "24646643156", "APNIC FY2025 retained report control"),
    ("World Vision Australia", "28004540170", "World Vision retained SDG/outcomes control"),
    ("Tweed", "retained:tweed", "Tweed retained CLASSIE control"),
    ("Local Buying", "retained:local-buying", "Local Buying retained activity control"),
)


def _id(prefix, payload):
    return deterministic_id(prefix, payload)


def _subject(name, identifier):
    subject_id = _id("subject:", {"retained_gate_identifier": identifier})
    source_id = _id("srcrec:", {"source_family": "retained-gate", "source_version": "2026-09-17", "source_locator": identifier, "payload_hash": "a" * 64})
    return SubjectRecord(
        record_id=_id("subjectrecord:", {"subject_id": subject_id}), subject_id=subject_id,
        subject_kind="organisation", lifecycle_status="active", display_name=name,
        identity_authority_refs=(ArtifactRef(artifact_id=source_id, content_hash="a" * 64, schema=SCHEMA),),
        identity_policy_id="phase5.retained-gate-fixture.v1", created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="phase5-retained-gate-fixture", version="1"),
    )


def retained_gate_graph():
    subjects = tuple(_subject(name, identifier) for name, identifier, _ in COHORT)
    organisation_scopes = tuple(ScopeRecord(
        record_id=_id("scope:", {"subject_id": subject.subject_id, "scope": "organisation"}), subject_id=subject.subject_id,
        scope_kind="organisation", label=subject.display_name, created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="phase5-retained-gate-fixture", version="1"),
    ) for subject in subjects)
    lifeblood_scope = ScopeRecord(
        record_id=_id("scope:", {"subject_id": subjects[0].subject_id, "scope": "lifeblood-operating-division"}),
        subject_id=subjects[0].subject_id, scope_kind="other", label="Lifeblood operating division",
        created_at=NOW, producer=ProducerRef(kind="code", producer_id="phase5-retained-gate-fixture", version="1"),
    )
    scopes = organisation_scopes + (lifeblood_scope,)
    observations = []
    evidence = []
    for subject, scope, (_, identifier, retained_basis) in zip(subjects, organisation_scopes, COHORT):
        source_id = _id("srcrec:", {"source_family": "retained-gate", "source_version": "2026-09-17", "source_locator": identifier, "payload_hash": "a" * 64})
        observation = Observation(
            record_id=_id("observation:", {"subject_id": subject.subject_id, "retained_basis": retained_basis}),
            subject_id=subject.subject_id, scope_id=scope.record_id,
            predicate="north_star_v02.retained_gate_transcription",
            value={"retained_basis": retained_basis, "transcription": "C1-C9 retained control; semantics unchanged"},
            outcome_state="supported", evidence_locator_ids=(f"[retained:{identifier}]",), source_record_ids=(source_id,),
            observation_time=ObservationTime(observed_at=NOW), method="phase5_retained_gate_transcription",
            lifecycle_status="held", created_at=NOW,
            producer=ProducerRef(kind="code", producer_id="phase5-retained-gate-fixture", version="1"),
        )
        observations.append(observation)
        # Each retained positive is deliberately scoped to its documented control section.
        section = 4 if identifier == "28004540170" else 2
        evidence.append(CardEvidence(observation_id=observation.record_id, disposition="REUSABLE_GOVERNED", section_ids=(section,), projection_contract_id="north-star-v0.2", note="deterministic transcription of retained C1-C9 proof"))
    coverage = tuple(
        CoverageInput(subject_id=subject.subject_id, section_id=section, projection_contract_id="north-star-v0.2", state="NOT_REVIEWED", basis="not_reviewed", note="retained gate fixture has no positive item for this subject-section")
        for subject in subjects for section in range(1, 21)
        if section not in ({4} if subject.display_name == "World Vision Australia" else {2})
    )
    return IntegratedGraph(subjects=subjects, scopes=scopes, observations=tuple(observations), evidence=tuple(evidence), coverage_inputs=coverage)


def test_fixed_retained_cohort_compiles_seven_literal_v02_cards_and_140_explicit_states():
    graph = retained_gate_graph()
    assert tuple(subject.display_name for subject in graph.subjects) == tuple(item[0] for item in COHORT)
    assert any(scope.label == "Lifeblood operating division" and scope.subject_id == graph.subjects[0].subject_id for scope in graph.scopes)
    cards = tuple(project_subject(graph, subject.subject_id, projection_contract=NORTH_STAR_PROJECTION_VNEXT) for subject in graph.subjects)
    assert len(cards) == 7
    assert all(len(card["sections"]) == 20 for card in cards)
    matrix = compile_matrix(graph, projection_contract=NORTH_STAR_PROJECTION_VNEXT)
    assert len(matrix) == 20 and sum(len(row["cells"]) for row in matrix) == 140
    assert sum(cell["observation_count"] for row in matrix for cell in row["cells"]) == 7
    assert sum(cell["status"] == "NOT_REVIEWED" for row in matrix for cell in row["cells"]) == 133
