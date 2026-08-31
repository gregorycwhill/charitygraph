from datetime import datetime, timezone

from charitygraph.contracts import DirectServiceRelationship, ScopeRecord
from charitygraph.direct_service_relationship_projection import (
    ARCHITECTURE_GAP,
    PARTY_ROLE_IN_SCOPE,
    REQUIRES_SUBJECT_PROMOTION,
    SUBJECT_TO_SUBJECT,
    build_party_role_projection,
    classify_relationship,
)


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
ORG = "subject:" + "1" * 32
OTHER = "subject:" + "2" * 32
SERVICE = "scope:" + "3" * 32
SERVICE_2 = "scope:" + "4" * 32
ORG_SCOPE = "scope:" + "5" * 32


def _scope(scope_id: str, subject_id: str, kind: str) -> ScopeRecord:
    return ScopeRecord(
        record_id=scope_id,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "fixture"},
        subject_id=subject_id,
        scope_kind=kind,
        label="label is not used for classification",
    )


def _relationship(source_scope_id=ORG_SCOPE, target_scope_id=SERVICE, role="operator") -> DirectServiceRelationship:
    return DirectServiceRelationship(
        source_scope_kind="organisation",
        source_scope_id=source_scope_id,
        source_label="arbitrary source label",
        target_scope_kind="service",
        target_scope_id=target_scope_id,
        target_label="arbitrary target label",
        role=role,
        direction="source_to_target",
        evidence=({"locator": "S001:L0001", "role": "supporting"},),
    )


def test_same_subject_organisation_to_service_is_contextual_party_role():
    relationship = _relationship()
    scopes = {
        ORG_SCOPE: _scope(ORG_SCOPE, ORG, "organisation"),
        SERVICE: _scope(SERVICE, ORG, "service"),
    }
    assert classify_relationship(relationship, scopes, durable_subject_ids={ORG}) == PARTY_ROLE_IN_SCOPE


def test_distinct_durable_subjects_remain_subject_relationships():
    relationship = _relationship()
    scopes = {
        ORG_SCOPE: _scope(ORG_SCOPE, ORG, "organisation"),
        SERVICE: _scope(SERVICE, OTHER, "service"),
    }
    assert classify_relationship(relationship, scopes, durable_subject_ids={ORG, OTHER}) == SUBJECT_TO_SUBJECT


def test_service_scope_is_not_promoted_just_to_persist_a_relationship():
    relationship = _relationship(source_scope_id=SERVICE, target_scope_id=SERVICE_2)
    scopes = {
        SERVICE: _scope(SERVICE, ORG, "service"),
        SERVICE_2: _scope(SERVICE_2, ORG, "service"),
    }
    assert classify_relationship(relationship, scopes, durable_subject_ids=set()) == REQUIRES_SUBJECT_PROMOTION
    assert classify_relationship(relationship, scopes, durable_subject_ids={ORG}) == ARCHITECTURE_GAP


def test_party_role_projection_preserves_typed_role_scope_and_evidence_lineage():
    relationship = _relationship(role="deliverer")
    observation, party_role = build_party_role_projection(
        relationship,
        party_id=ORG,
        scope_id=SERVICE,
        source_record_ids=("srcrec:" + "6" * 32,),
        recovery_result_id="modelresult:" + "7" * 32,
        original_task_id="modeltask:" + "8" * 32,
        relationship_index=0,
        created_at=NOW,
        producer={"kind": "code", "producer_id": "projection"},
    )
    assert party_role.party_id == ORG
    assert party_role.role == "deliverer"
    assert party_role.scope_id == SERVICE
    assert party_role.context_record_id == observation.record_id
    assert observation.evidence_locator_ids == ("S001:L0001",)
    assert {edge.target_artifact_id for edge in observation.lineage} == {
        "modelresult:" + "7" * 32,
        "modeltask:" + "8" * 32,
    }
