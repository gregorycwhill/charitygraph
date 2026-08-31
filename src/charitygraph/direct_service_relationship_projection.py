"""Structural projection of typed direct-service relationships.

This module deliberately consumes already-typed relationship and scope records.
It does not infer roles, entities, or scope ownership from labels or prose.
"""
from __future__ import annotations

from typing import Any, Mapping

from charitygraph.contracts import (
    DirectServiceRelationship,
    LineageEdge,
    Observation,
    PartyRole,
    ScopeRecord,
    deterministic_id,
)


PARTY_ROLE_IN_SCOPE = "persisted_as_party_role"
SUBJECT_TO_SUBJECT = "persisted_as_relationship_statement"
REQUIRES_SUBJECT_PROMOTION = "held_requires_subject_promotion"
ARCHITECTURE_GAP = "held_architecture_gap"


def _scope(scope: ScopeRecord | Mapping[str, object]) -> tuple[str, str]:
    """Return structural owner and kind without inspecting labels."""

    if isinstance(scope, ScopeRecord):
        return scope.subject_id, scope.scope_kind
    return str(scope["subject_id"]), str(scope["scope_kind"])


def classify_relationship(
    relationship: DirectServiceRelationship,
    scopes: Mapping[str, ScopeRecord | Mapping[str, object]],
    *,
    durable_subject_ids: set[str],
) -> str:
    """Classify a typed relationship using only scope/subject structure.

    A same-subject organisation-to-service/program relationship is a contextual
    party role. Distinct durable owners are subject-to-subject relationships.
    A non-durable program/service owner is held for explicit promotion rather
    than being promoted because persistence is convenient.
    """

    source = scopes.get(relationship.source_scope_id)
    target = scopes.get(relationship.target_scope_id)
    if source is None or target is None:
        return ARCHITECTURE_GAP
    source_subject, source_kind = _scope(source)
    target_subject, target_kind = _scope(target)
    if source_subject == target_subject:
        if source_kind == "organisation" and target_kind in {"program", "service"}:
            return PARTY_ROLE_IN_SCOPE
        if source_kind in {"program", "service"} and target_kind in {"program", "service"}:
            return REQUIRES_SUBJECT_PROMOTION if target_subject not in durable_subject_ids else ARCHITECTURE_GAP
        return ARCHITECTURE_GAP
    if source_subject in durable_subject_ids and target_subject in durable_subject_ids:
        return SUBJECT_TO_SUBJECT
    if target_kind in {"program", "service"} and target_subject not in durable_subject_ids:
        return REQUIRES_SUBJECT_PROMOTION
    return ARCHITECTURE_GAP


def build_party_role_projection(
    relationship: DirectServiceRelationship,
    *,
    party_id: str,
    scope_id: str,
    source_record_ids: tuple[str, ...],
    recovery_result_id: str,
    original_task_id: str,
    relationship_index: int,
    created_at,
    producer: dict[str, str],
) -> tuple[Observation, PartyRole]:
    """Build an evidence-bearing Observation and contextual PartyRole.

    The Observation is the reconstructible evidence bridge because PartyRole
    intentionally remains a compact structural primitive.
    """

    identity = {
        "recovery_result_id": recovery_result_id,
        "relationship_index": relationship_index,
        "party_id": party_id,
        "scope_id": scope_id,
        "role": relationship.role,
        "direction": relationship.direction,
    }
    observation_id = deterministic_id("observation:", {"relationship_projection": identity})
    role_id = deterministic_id("partyrole:", {"relationship_projection": identity})
    evidence_ids = tuple(item.locator for item in relationship.evidence)
    observation = Observation(
        record_id=observation_id,
        created_at=created_at,
        producer=producer,
        subject_id=party_id,
        scope_id=scope_id,
        predicate="direct_service.relationship_role",
        value={
            "role": relationship.role,
            "direction": relationship.direction,
            "source_scope_id": relationship.source_scope_id,
            "target_scope_id": relationship.target_scope_id,
            "source_scope_kind": relationship.source_scope_kind,
            "target_scope_kind": relationship.target_scope_kind,
        },
        outcome_state="supported",
        evidence_locator_ids=evidence_ids,
        source_record_ids=source_record_ids,
        observation_time=relationship.observation_time or {"observed_at": created_at},
        method="direct_service_relationship_projection_v1",
        lineage=(
            LineageEdge(edge_type="derived_from", source_artifact_id=observation_id, target_artifact_id=recovery_result_id),
            LineageEdge(edge_type="derived_from", source_artifact_id=observation_id, target_artifact_id=original_task_id),
        ),
    )
    party_role = PartyRole(
        record_id=role_id,
        created_at=created_at,
        producer=producer,
        party_id=party_id,
        role=relationship.role,
        context_record_id=observation_id,
        scope_id=scope_id,
        lineage=(
            LineageEdge(edge_type="derived_from", source_artifact_id=role_id, target_artifact_id=observation_id),
            LineageEdge(edge_type="derived_from", source_artifact_id=role_id, target_artifact_id=recovery_result_id),
        ),
    )
    return observation, party_role


def persist_party_role_projection(catalog: Any, observation: Observation, party_role: PartyRole, *, created_at) -> None:
    """Persist the evidence bridge and role append-only, safely replayable."""

    catalog.record_observation(observation)
    catalog.register_party_role(party_role)
    for edge in party_role.lineage:
        catalog.record_knowledge_lineage(
            edge.source_artifact_id,
            edge.target_artifact_id,
            edge.edge_type,
            material={"projection": "direct_service_relationship_projection_v1"},
            created_at=created_at,
        )


__all__ = [
    "PARTY_ROLE_IN_SCOPE", "SUBJECT_TO_SUBJECT", "REQUIRES_SUBJECT_PROMOTION", "ARCHITECTURE_GAP",
    "classify_relationship", "build_party_role_projection", "persist_party_role_projection",
]
