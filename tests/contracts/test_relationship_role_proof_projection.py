from datetime import datetime, timezone

from charitygraph.contracts.common import ArtifactRef, ProducerRef, SchemaRef
from charitygraph.contracts.ids import deterministic_id
from charitygraph.contracts.knowledge import RelationshipStatement, ScopeRecord, SubjectRecord
from charitygraph.integrated_card import CardEvidence, IntegratedGraph, project_subject


NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0")


def _subject(subject_id: str, name: str, kind: str = "organisation") -> SubjectRecord:
    return SubjectRecord(
        record_id=deterministic_id("subjectrecord:", {"subject_id": subject_id}), subject_id=subject_id,
        subject_kind=kind, lifecycle_status="active", display_name=name,
        identity_authority_refs=(ArtifactRef(artifact_id="srcrec:" + "1" * 64, content_hash="a" * 64, schema=SCHEMA),),
        identity_policy_id="retained-evidence-identity-v1", created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="relationship-proof", version="1"),
    )


def test_real_shape_projects_relationship_id_into_section_12_without_copying_relationship_state():
    source = _subject("subject:" + "1" * 32, "Australian Red Cross Society")
    target = _subject("subject:" + "2" * 32, "Telecross and Telechat", "service")
    scope = ScopeRecord(record_id="scope:" + "3" * 32, subject_id=source.subject_id, scope_kind="service", label="Telecross and Telechat", created_at=NOW, producer=ProducerRef(kind="code", producer_id="relationship-proof", version="1"))
    relation = RelationshipStatement(
        record_id=deterministic_id("relationship:", {"source": source.subject_id, "target": target.subject_id, "role": "operator"}),
        source_subject_id=source.subject_id, target_subject_id=target.subject_id,
        relationship_type="operator", role="operator", source_role="operator", target_role="service",
        scope_id=scope.record_id, status="candidate", created_at=NOW,
        producer=ProducerRef(kind="code", producer_id="relationship-proof", version="1"),
    )
    graph = IntegratedGraph(subjects=(source, target), scopes=(scope,), observations=(), relationships=(relation,), evidence=())
    card = project_subject(graph, source.subject_id)
    section12 = card["sections"][11]
    assert section12["relationship_ids"] == [relation.record_id]
    assert "relationship_type" not in section12
