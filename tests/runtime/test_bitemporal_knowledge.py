from datetime import date, datetime, timezone

from charitygraph.contracts import (
    ArtifactRef, Assertion, LineageEdge, Observation, RelationshipStatement,
    SchemaRef, SubjectRecord,
)
from charitygraph.runtime import SQLiteCatalog


SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:bitemporal:1.0", schema_version="1.0")
AUTHORITY = ArtifactRef(artifact_id="decision:" + "a" * 32, content_hash="b" * 64, schema=SCHEMA)
SUBJECT_A = "subject:" + "1" * 32
SUBJECT_B = "subject:" + "2" * 32


def at(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=timezone.utc)


def subject(subject_id: str) -> SubjectRecord:
    return SubjectRecord(
        record_id="subjectrecord:" + subject_id[-32:], created_at=at(1),
        producer={"kind": "human", "producer_id": "reviewer"}, subject_id=subject_id,
        subject_kind="organisation", lifecycle_status="active", identity_authority_refs=(AUTHORITY,),
        identity_policy_id="identity-v1", display_name="Synthetic subject",
    )


def observation(record_id: str, created_at: datetime, *, state: str = "resolved", valid_from: date | None = None, valid_to: date | None = None, supersedes: str | None = None) -> Observation:
    lineage = () if supersedes is None else (LineageEdge(edge_type="supersedes", source_artifact_id=record_id, target_artifact_id=supersedes),)
    return Observation(
        record_id=record_id, created_at=created_at, producer={"kind": "human", "producer_id": "reviewer"},
        subject_id=SUBJECT_A, predicate="first_party_claim" if record_id.endswith("3") else "director_of",
        value="we do not use face-to-face fundraising" if record_id.endswith("3") else "reported",
        outcome_state=state, source_record_ids=("srcrec:" + "c" * 32,),
        observation_time={"effective_from": valid_from, "effective_to": valid_to, "observed_at": created_at},
        method="fixture", lifecycle_status="accepted", lineage=lineage,
        supersedes_observation_id=supersedes,
    )


def test_knowledge_and_valid_time_are_explicitly_separate(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "bitemporal.sqlite3").open(initialize=True)
    catalog.register_subject(subject(SUBJECT_A))
    catalog.register_subject(subject(SUBJECT_B))
    director = RelationshipStatement(
        record_id="relationship:" + "d" * 32, created_at=at(21),
        producer={"kind": "human", "producer_id": "reviewer"}, source_subject_id=SUBJECT_A,
        target_subject_id=SUBJECT_B, relationship_type="governance_relationship", role="partner",
        status="accepted", valid_from=date(2026, 7, 1),
    )
    catalog.record_relationship(director)

    # The relationship was true from 1 July but was not governed knowledge on 20 July.
    assert catalog.knowledge_state_at(SUBJECT_A, knowledge_at=at(20))["relationships"] == []
    assert [row["relationship_id"] for row in catalog.knowledge_state_at(SUBJECT_A, knowledge_at=at(21))["relationships"]] == [director.record_id]
    assert [row["relationship_id"] for row in catalog.current_belief_valid_at(SUBJECT_A, valid_at=date(2026, 7, 1))["relationships"]] == [director.record_id]
    assert catalog.knowledge_state_valid_at(SUBJECT_A, knowledge_at=at(20), valid_at=date(2026, 7, 1))["relationships"] == []
    assert [row["relationship_id"] for row in catalog.knowledge_state_valid_at(SUBJECT_A, knowledge_at=at(21), valid_at=date(2026, 7, 1))["relationships"]] == [director.record_id]


def test_corrections_and_missingness_remain_auditable_without_positive_inference(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "bitemporal.sqlite3").open(initialize=True)
    catalog.register_subject(subject(SUBJECT_A))
    original = observation("observation:" + "1" * 32, at(2), valid_from=date(2026, 7, 1))
    replacement = observation("observation:" + "2" * 32, at(4), valid_from=date(2026, 7, 1), valid_to=date(2026, 7, 3), supersedes=original.record_id)
    missing = observation("observation:" + "3" * 32, at(5), state="unknown")
    catalog.record_observation(original)
    catalog.record_observation(replacement)
    catalog.record_observation(missing)

    before = catalog.knowledge_state_at(SUBJECT_A, knowledge_at=at(3))
    after = catalog.knowledge_state_at(SUBJECT_A, knowledge_at=at(5))
    assert [row["observation_id"] for row in before["observations"]] == [original.record_id]
    assert [row["observation_id"] for row in after["observations"]] == [replacement.record_id]
    assert [row["observation_id"] for row in after["coverage"]] == [missing.record_id]
    assert [row["observation_id"] for row in catalog.current_belief_valid_at(SUBJECT_A, valid_at=date(2026, 7, 2))["observations"]] == [replacement.record_id]
    assert catalog.current_belief_valid_at(SUBJECT_A, valid_at=date(2026, 7, 4))["observations"] == []


def test_first_party_claim_is_not_promoted_by_bitemporal_query(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "bitemporal.sqlite3").open(initialize=True)
    catalog.register_subject(subject(SUBJECT_A))
    claim = observation("observation:" + "3" * 32, at(3), valid_from=date(2026, 7, 1))
    catalog.record_observation(claim)
    result = catalog.current_belief_valid_at(SUBJECT_A, valid_at=date(2026, 7, 2))
    assert result["observations"][0]["predicate"] == "first_party_claim"
    assert result["observations"][0]["value"] == "we do not use face-to-face fundraising"
