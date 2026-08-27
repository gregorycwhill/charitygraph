from datetime import datetime, timezone
from pathlib import Path

import pytest

from charitygraph.contracts import ArtifactRef, ProgramCandidate, SchemaRef, SourceRecord, SubjectRecord, deterministic_id
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.program_subject_promotion import promote_program_candidate
from charitygraph.runtime import ConflictError, SQLiteCatalog

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:test:1.0", schema_version="1.0")


def setup_catalog(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    store = ContentAddressedArtifactStore(tmp_path / "objects", catalog=catalog)
    artifact = store.put(b"bounded evidence")
    source_id = deterministic_id("srcrec:", {"source_family": "synthetic", "source_version": "1", "source_locator": "fixture:promotion", "payload_hash": artifact.content_hash})
    source = SourceRecord(record_id=source_id, created_at=NOW, producer={"kind": "code", "producer_id": "test", "version": "1"}, source_family="synthetic", source_role="fixture", source_version="1", source_locator="fixture:promotion", observed_at=NOW, payload_ref=artifact.artifact_id, payload_hash=artifact.content_hash)
    catalog.register_source_record(source)
    evidence_id = "evidence:promotion"
    locator = catalog.register_evidence_locator({"artifact_id": artifact.artifact_id, "kind": "document", "locator": "fixture:promotion"}, evidence_locator_id=evidence_id, now=NOW)
    ref = ArtifactRef(artifact_id="decision:" + "a" * 32, content_hash="a" * 64, schema_ref=SCHEMA)
    organisation = SubjectRecord(record_id="subjectrecord:" + "1" * 32, created_at=NOW, producer={"kind": "human", "producer_id": "seed", "version": "1"}, subject_id="subject:" + "1" * 32, subject_kind="organisation", lifecycle_status="active", display_name="Example Org", identity_authority_refs=(ref,), identity_policy_id="seed-v1")
    catalog.register_subject(organisation)
    return catalog, source.record_id, evidence_id, organisation.subject_id


def candidate(source_id, evidence_id, kind, suffix):
    return ProgramCandidate(record_id="programcandidate:" + suffix * 32, created_at=NOW, producer={"kind": "code", "producer_id": "test", "version": "1"}, subject_id="subject:" + "1" * 32, source_record_id=source_id, evidence_ids=(evidence_id,), label=f"{kind.title()} offering", candidate_kind=kind, extraction_method="structured", status="candidate")


def test_promotes_program_service_and_rejection_without_duplicate_relationship(tmp_path):
    catalog, source_id, evidence_id, organisation = setup_catalog(tmp_path)
    program = candidate(source_id, evidence_id, "explicit_program", "2")
    service = candidate(source_id, evidence_id, "explicit_service", "3")
    rejected = candidate(source_id, evidence_id, "ambiguous", "4")
    for item in (program, service, rejected): catalog.register_program_candidate(item)
    p = promote_program_candidate(catalog, candidate_id=program.record_id, reviewer_id="reviewer", review_policy_id="promotion-v1", target_subject_id="subject:" + "a" * 32, decision_time=NOW, rationale="Evidence identifies the program")
    s = promote_program_candidate(catalog, candidate_id=service.record_id, reviewer_id="reviewer", review_policy_id="promotion-v1", target_subject_id="subject:" + "b" * 32, decision_time=NOW, rationale="Evidence identifies the service")
    r = promote_program_candidate(catalog, candidate_id=rejected.record_id, reviewer_id="reviewer", review_policy_id="promotion-v1", target_subject_id="subject:" + "c" * 32, decision_time=NOW, rationale="Insufficient identity", outcome="rejected")
    assert p["subject"]["subject_kind"] == "program" and p["relationship"]["relationship_type"] == "operates"
    assert s["subject"]["subject_kind"] == "service" and s["relationship"]["relationship_type"] == "operates"
    assert r["subject"] is None and r["relationship"] is None
    assert catalog.get_subject("subject:" + "c" * 32) is None
    assert len(catalog.reconstruct_knowledge_history(organisation)["relationships"]) == 2


def test_same_subject_rediscovery_is_idempotent_and_different_target_conflicts(tmp_path):
    catalog, source_id, evidence_id, _ = setup_catalog(tmp_path)
    first = candidate(source_id, evidence_id, "explicit_program", "5")
    second = candidate(source_id, evidence_id, "explicit_program", "6")
    catalog.register_program_candidate(first); catalog.register_program_candidate(second)
    target = "subject:" + "d" * 32
    one = promote_program_candidate(catalog, candidate_id=first.record_id, reviewer_id="reviewer", review_policy_id="promotion-v1", target_subject_id=target, decision_time=NOW, rationale="same program")
    two = promote_program_candidate(catalog, candidate_id=second.record_id, reviewer_id="reviewer", review_policy_id="promotion-v1", target_subject_id=target, decision_time=NOW, rationale="same known program")
    assert one["subject"]["subject_id"] == two["subject"]["subject_id"]
    assert len(catalog.reconstruct_knowledge_history("subject:" + "1" * 32)["relationships"]) == 1
    with pytest.raises(ConflictError):
        promote_program_candidate(catalog, candidate_id=first.record_id, reviewer_id="reviewer", review_policy_id="promotion-v1", target_subject_id="subject:" + "e" * 32, decision_time=NOW, rationale="different target")