"""Governed promotion of discovered program/service candidates to graph subjects."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .contracts import (
    AdjudicationDecision, ArtifactRef, LineageEdge, ProgramCandidate,
    RelationshipStatement, SubjectRecord, canonical_sha256,
)
from .contracts.ids import deterministic_id, validate_typed_id
from .runtime import CatalogError, ConflictError, SQLiteCatalog


def _decision_id(candidate_id: str, target_subject_id: str, outcome: str) -> str:
    return deterministic_id("adjudication:", {"candidate_id": candidate_id, "target_subject_id": target_subject_id, "outcome": outcome})


def _subject_record_id(subject_id: str) -> str:
    return deterministic_id("subjectrecord:", {"subject_id": subject_id})


def _relationship_id(organisation_id: str, target_subject_id: str) -> str:
    return deterministic_id("relationship:", {"source_subject_id": organisation_id, "target_subject_id": target_subject_id, "relationship_type": "operates"})


def _existing_candidate_decisions(catalog: SQLiteCatalog, candidate_id: str) -> list[dict[str, Any]]:
    with catalog._connection() as conn:
        rows = conn.execute("SELECT * FROM adjudication_decisions ORDER BY created_at, adjudication_id").fetchall()
    result = []
    for row in rows:
        item = catalog._decode_knowledge_row(row) or {}
        if candidate_id in item.get("input_record_ids", []):
            result.append(item)
    return result


def promote_program_candidate(
    catalog: SQLiteCatalog,
    *,
    candidate_id: str,
    reviewer_id: str,
    review_policy_id: str,
    target_subject_id: str,
    decision_time: datetime,
    rationale: str,
    outcome: str = "accepted",
    display_name: str | None = None,
) -> dict[str, Any]:
    """Apply one explicit human/governed identity decision.

    Target identity is always supplied by the caller; no label or fuzzy matching
    participates in subject creation. Exact repeats are idempotent.
    """
    candidate_row = catalog.get_program_candidate(candidate_id)
    if candidate_row is None:
        raise CatalogError(f"unknown program candidate {candidate_id}")
    candidate = ProgramCandidate.model_validate(candidate_row.get("material", candidate_row))
    if candidate.status not in {"candidate", "accepted"}:
        raise ConflictError("candidate is not promotable")
    if outcome not in {"accepted", "rejected"}:
        raise ValueError("promotion outcome must be accepted or rejected")
    if outcome == "accepted" and candidate.candidate_kind not in {"explicit_program", "explicit_service"}:
        raise ConflictError("only explicit program/service candidates are promotable")
    validate_typed_id(target_subject_id, "subject:")
    parent = catalog.get_subject(candidate.subject_id)
    if parent is None:
        raise CatalogError("candidate organisation subject does not exist")
    if parent["subject_kind"] not in {"organisation", "organisation_group", "legal_entity"}:
        raise ConflictError("candidate source subject is not an organisation")
    if outcome == "accepted":
        existing_target = catalog.get_subject(target_subject_id)
        if existing_target is not None and existing_target["subject_kind"] != ("program" if candidate.candidate_kind == "explicit_program" else "service"):
            raise ConflictError("target subject kind is incompatible with candidate kind")
    prior = _existing_candidate_decisions(catalog, candidate_id)
    for decision in prior:
        if decision.get("outcome") == "rejected":
            raise ConflictError("rejected candidate cannot be promoted")
        if decision.get("outcome") == "accepted" and decision.get("result_record_id") != target_subject_id:
            raise ConflictError("candidate is already promoted to a different subject")
    decision_id = _decision_id(candidate_id, target_subject_id, outcome)
    decision = AdjudicationDecision(
        record_id=decision_id, created_at=decision_time,
        producer={"kind": "human", "producer_id": reviewer_id, "version": "1"},
        input_record_ids=(candidate_id,), outcome=outcome, rationale=rationale,
        reviewer_id=reviewer_id, result_record_id=target_subject_id if outcome == "accepted" else None,
        decision_time=decision_time, review_policy_id=review_policy_id,
        lineage=(LineageEdge(edge_type="reviewed_by", source_artifact_id=candidate_id, target_artifact_id=decision_id),),
    )
    catalog.record_adjudication(decision)
    if outcome == "rejected":
        return {"candidate": candidate_row, "decision": catalog.get_adjudication(decision_id), "subject": None, "relationship": None}
    target_kind = "program" if candidate.candidate_kind == "explicit_program" else "service"
    candidate_ref = ArtifactRef(artifact_id=candidate.record_id, content_hash=canonical_sha256(candidate), schema_ref=candidate.schema_ref)
    decision_ref = ArtifactRef(artifact_id=decision_id, content_hash=canonical_sha256(decision), schema_ref=decision.schema_ref)
    subject = SubjectRecord(
        record_id=_subject_record_id(target_subject_id), created_at=decision_time,
        producer={"kind": "human", "producer_id": reviewer_id, "version": "1"},
        subject_id=target_subject_id, subject_kind=target_kind, lifecycle_status="active",
        display_name=display_name or candidate.label, identity_authority_refs=(candidate_ref, decision_ref),
        identity_policy_id="program-subject-promotion-v1",
        lineage=(LineageEdge(edge_type="proposed_from", source_artifact_id=candidate.record_id, target_artifact_id=_subject_record_id(target_subject_id)),),
    )
    existing = catalog.get_subject(target_subject_id)
    if existing is None:
        catalog.register_subject(subject)
    elif existing["subject_kind"] != target_kind:
        raise ConflictError("target subject kind is incompatible with candidate kind")
    relationship = RelationshipStatement(
        record_id=_relationship_id(candidate.subject_id, target_subject_id),
        created_at=decision_time, producer={"kind": "human", "producer_id": reviewer_id, "version": "1"},
        source_subject_id=candidate.subject_id, target_subject_id=target_subject_id,
        relationship_type="operates", source_role="operator", target_role=target_kind,
        evidence_locator_ids=candidate.evidence_ids, status="accepted",
        lineage=(LineageEdge(edge_type="derived_from", source_artifact_id=candidate.record_id, target_artifact_id=_relationship_id(candidate.subject_id, target_subject_id)),),
    )
    existing_rel = catalog.get_relationship(relationship.record_id)
    if existing_rel is None:
        catalog.record_relationship(relationship)
    return {"candidate": candidate_row, "decision": catalog.get_adjudication(decision_id), "subject": catalog.get_subject(target_subject_id), "relationship": catalog.get_relationship(relationship.record_id)}
