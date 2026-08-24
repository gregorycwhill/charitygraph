from datetime import datetime, timezone
import sqlite3

import pytest

from charitygraph.contracts import (
    AdjudicationDecision,
    ArtifactRef,
    Assertion,
    EvidenceLocator,
    LineageEdge,
    Observation,
    PartyRole,
    RelationshipStatement,
    SchemaRef,
    ScopeRecord,
    SubjectRecord,
)
from charitygraph.runtime import ConflictError, SQLiteCatalog
from charitygraph.runtime.migrations import MIGRATIONS


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:test:1.0", schema_version="1.0")
AUTHORITY = ArtifactRef(artifact_id="decision:" + "a" * 32, content_hash="b" * 64, schema=SCHEMA)
SUBJECT_A = "subject:" + "1" * 32
SUBJECT_B = "subject:" + "2" * 32


def subject(subject_id: str) -> SubjectRecord:
    return SubjectRecord(
        record_id="subjectrecord:" + subject_id[-32:],
        created_at=NOW,
        producer={"kind": "human", "producer_id": "reviewer"},
        subject_id=subject_id,
        subject_kind="organisation",
        lifecycle_status="active",
        identity_authority_refs=(AUTHORITY,),
        identity_policy_id="identity-v1",
        display_name="Synthetic " + subject_id[-1:],
    )


def open_catalog(tmp_path):
    return SQLiteCatalog(tmp_path / "knowledge.sqlite3").open(initialize=True)


def scope() -> ScopeRecord:
    return ScopeRecord(
        record_id="scope:" + "3" * 32,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "fixture"},
        subject_id=SUBJECT_A,
        scope_kind="program",
        label="Synthetic program",
    )


def observation(record_id: str, *, value="yes", state="resolved", scope_id=None, evidence=()):
    return Observation(
        record_id=record_id,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "fixture"},
        subject_id=SUBJECT_A,
        scope_id=scope_id,
        predicate="offers",
        value=value,
        outcome_state=state,
        evidence_locator_ids=evidence,
        source_record_ids=("srcrec:" + "4" * 32,),
        observation_time={"observed_at": NOW},
        method="fixture",
    )


def assertion(record_id: str, observation_ids=(), *, value="yes", state="resolved", lifecycle="accepted", supersedes=None, scope_id=None):
    lineage = () if supersedes is None else (
        LineageEdge(edge_type="supersedes", source_artifact_id=record_id, target_artifact_id=supersedes),
    )
    return Assertion(
        record_id=record_id,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "reviewer"},
        subject_id=SUBJECT_A,
        scope_id=scope_id,
        predicate="offers",
        value=value,
        outcome_state=state,
        observation_ids=observation_ids,
        assertion_time={"observed_at": NOW},
        method="review",
        lifecycle_status=lifecycle,
        supersedes_assertion_id=supersedes,
        lineage=lineage,
    )


def test_clean_v2_to_v3_migration_and_integrity(tmp_path):
    catalog = open_catalog(tmp_path)
    assert catalog.migrate() == 3
    assert catalog.integrity_check() == "ok"
    catalog.close()
    reopened = SQLiteCatalog(tmp_path / "knowledge.sqlite3").open()
    assert reopened.migrate() == 3
    assert reopened.integrity_check() == "ok"


def test_existing_catalogue_v2_migrates_append_only_to_v3(tmp_path):
    path = tmp_path / "v2.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        for migration in MIGRATIONS[:2]:
            for statement in migration.sql.split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                (migration.version, migration.name, migration.checksum, NOW.isoformat()),
            )
        conn.commit()
    catalog = SQLiteCatalog(path).open()
    assert catalog.migrate() == 3
    assert catalog.get_subject(SUBJECT_A) is None
    assert catalog.integrity_check() == "ok"


def test_subject_external_identifier_scope_and_role_are_idempotent_and_scoped(tmp_path):
    catalog = open_catalog(tmp_path)
    catalog.register_subject(subject(SUBJECT_A))
    catalog.register_subject(subject(SUBJECT_B))
    identifier = {"scheme": "ABN", "value": "12 345 678 901", "issuing_authority": "ACNC"}
    first = catalog.register_external_identifier(SUBJECT_A, identifier)
    assert catalog.register_external_identifier(SUBJECT_A, identifier)["material_hash"] == first["material_hash"]
    with pytest.raises(ConflictError):
        catalog.register_external_identifier(SUBJECT_B, identifier)
    scoped = catalog.register_scope(scope())
    assert scoped["scope_id"] == scope().record_id
    role = PartyRole(
        record_id="partyrole:" + "5" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "reviewer"},
        party_id=SUBJECT_A,
        role="reviewer",
        scope_id=scope().record_id,
    )
    assert catalog.register_party_role(role)["party_role_id"] == role.record_id
    with pytest.raises(ConflictError):
        catalog.register_scope(scope().model_copy(update={"subject_id": SUBJECT_B}))


def test_observation_assertion_history_preserves_edits_contradictions_and_withdrawal(tmp_path):
    catalog = open_catalog(tmp_path)
    catalog.register_subject(subject(SUBJECT_A))
    first = observation("observation:" + "6" * 32)
    second = observation("observation:" + "7" * 32, value="updated")
    catalog.record_observation(first)
    assert catalog.record_observation(first)["observation_id"] == first.record_id
    with pytest.raises(ConflictError):
        catalog.record_observation(first.model_copy(update={"value": "different"}))
    catalog.record_observation(second)
    original = assertion("assertion:" + "8" * 32, (first.record_id,))
    edited = assertion(
        "assertion:" + "9" * 32, (second.record_id,), value="updated",
        lifecycle="superseded", supersedes=original.record_id,
    )
    catalog.record_assertion(original)
    catalog.record_assertion(edited)
    contradiction = assertion(
        "assertion:" + "a" * 32, (first.record_id, second.record_id),
        value="contested", state="contradicted",
    )
    withdrawn = assertion(
        "assertion:" + "b" * 32, (), value=None, state="withheld", lifecycle="withdrawn",
    )
    catalog.record_assertion(contradiction)
    catalog.record_assertion(withdrawn)
    catalog.record_lineage(original.record_id, edited.record_id, "supersedes")
    history = catalog.reconstruct_knowledge_history(SUBJECT_A)
    assert {item["assertion_id"] for item in history["assertions"]} == {
        original.record_id, edited.record_id, contradiction.record_id, withdrawn.record_id,
    }
    assert any(edge["edge_type"] == "supersedes" for edge in history["lineage"])


def test_evidence_to_observation_to_assertion_to_decision_lineage_is_directed(tmp_path):
    catalog = open_catalog(tmp_path)
    catalog.register_subject(subject(SUBJECT_A))
    locator = EvidenceLocator(kind="document", source_record_id="srcrec:" + "4" * 32, page=1)
    locator_row = catalog.register_evidence_locator(locator)
    obs = observation("observation:" + "c" * 32, evidence=(locator_row["evidence_locator_id"],))
    ass = assertion("assertion:" + "d" * 32, (obs.record_id,))
    catalog.record_observation(obs)
    catalog.record_assertion(ass)
    decision = AdjudicationDecision(
        record_id="adjudication:" + "e" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "reviewer"},
        input_record_ids=(obs.record_id, ass.record_id),
        outcome="accepted",
        rationale="Synthetic evidence chain reviewed",
        reviewer_id="reviewer",
        result_record_id=ass.record_id,
        decision_time=NOW,
        review_policy_id="review-v1",
    )
    catalog.record_adjudication(decision)
    catalog.record_lineage(locator_row["evidence_locator_id"], obs.record_id, "proposed_from")
    catalog.record_lineage("candidate:" + "f" * 32, "decision:" + "1" * 32, "reviewed_by")
    catalog.record_lineage("candidate:" + "f" * 32, obs.record_id, "promoted_as")
    catalog.record_lineage(ass.record_id, decision.record_id, "adjudicates")
    edges = catalog.get_knowledge_lineage()
    assert [(edge["source_record_id"], edge["target_record_id"], edge["edge_type"]) for edge in edges] == [
        (locator_row["evidence_locator_id"], obs.record_id, "proposed_from"),
        ("candidate:" + "f" * 32, "decision:" + "1" * 32, "reviewed_by"),
        ("candidate:" + "f" * 32, obs.record_id, "promoted_as"),
        (ass.record_id, decision.record_id, "adjudicates"),
    ]
    with pytest.raises(ConflictError):
        catalog.record_lineage(obs.record_id, ass.record_id, "reviewed_by")
    with pytest.raises(ConflictError):
        catalog.record_lineage(obs.record_id, ass.record_id, "promoted_as")


def test_relationship_direction_and_outcome_states_are_preserved(tmp_path):
    catalog = open_catalog(tmp_path)
    catalog.register_subject(subject(SUBJECT_A))
    catalog.register_subject(subject(SUBJECT_B))
    relationship = RelationshipStatement(
        record_id="relationship:" + "1" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "reviewer"},
        source_subject_id=SUBJECT_A,
        target_subject_id=SUBJECT_B,
        relationship_type="supports",
        status="accepted",
    )
    catalog.record_relationship(relationship)
    assert catalog.get_relationship(relationship.record_id)["source_subject_id"] == SUBJECT_A
    assert catalog.get_relationship(relationship.record_id)["target_subject_id"] == SUBJECT_B
    for index, state in enumerate(("unknown", "not_applicable", "not_attempted", "acquisition_failure", "extraction_failure")):
        item = observation("observation:" + f"{index + 2:x}" * 32, state=state)
        catalog.record_observation(item)
    assert len(catalog.reconstruct_knowledge_history(SUBJECT_A)["observations"]) == 5
