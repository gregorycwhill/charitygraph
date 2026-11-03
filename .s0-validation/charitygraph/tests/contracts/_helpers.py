from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from charitygraph.contracts import (
    ArtifactRef, CandidateObservation, CanonicalObservation, DecisionRecord, EvidenceFragment,
    EvidenceInput, HumanAuthority, LineageEdge, ModelTask, ObservationTime, SchemaRef,
    SourceRecord, SubjectRecord, VersionedPolicy, VersionedTool, deterministic_id, model_task_cache_key,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SUBJECT = "subject:" + "1" * 32
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:test-payload:1.0", schema_version="1.0")


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: str


def ref(artifact_id: str = "evidence:" + "2" * 32, content_hash: str = "a" * 64):
    return ArtifactRef(artifact_id=artifact_id, content_hash=content_hash, schema=SCHEMA)


def subject():
    return SubjectRecord(
        record_id="subjectrecord:" + "3" * 32,
        created_at=NOW,
        producer={"kind": "human", "producer_id": "reviewer", "version": "1"},
        subject_id=SUBJECT,
        subject_kind="organisation",
        lifecycle_status="active",
        display_name="Synthetic Organisation",
        identity_authority_refs=(ref("decision:" + "4" * 32),),
        identity_policy_id="identity-v1",
    )


def source():
    identity = {"source_family": "synthetic", "source_version": "1", "source_locator": "fixture:1", "payload_hash": "b" * 64}
    return SourceRecord(
        record_id=deterministic_id("srcrec:", identity), created_at=NOW,
        producer={"kind": "code", "producer_id": "test", "version": "1"},
        source_family="synthetic", source_role="fixture", source_version="1",
        source_locator="fixture:1", observed_at=NOW, payload_ref="fixture-body:1", payload_hash="b" * 64,
    )


def evidence():
    source_record = source()
    identity = {"source_record_id": source_record.record_id, "locator": "p1:1", "fragment_hash": "c" * 64,
                "selection_method": "fixture", "selection_policy_version": "1"}
    return EvidenceFragment(
        record_id=deterministic_id("evidence:", identity), created_at=NOW,
        producer={"kind": "code", "producer_id": "test", "version": "1"}, source_record=ref(source_record.record_id),
        fragment_kind="text", locator="p1:1", content_ref="fixture-body:1", fragment_hash="c" * 64,
        selection_method="fixture", selection_policy_version="1", observed_at=NOW,
    )


def task(subject_id=SUBJECT, evidence_hash="a" * 64, provider="fake", model="model-1"):
    task_schema = SchemaRef(schema_id="urn:charitygraph:builder:schema:model-task:1.0", schema_version="1.0")
    evidence_inputs = (EvidenceInput(evidence_id="evidence:2" + "0" * 31, content_hash=evidence_hash, selection_hash="d" * 64),)
    policies = (VersionedPolicy(policy_id="policy", version="1"),)
    tools = (VersionedTool(tool_id="parser", version="1"),)
    cache = model_task_cache_key(task_type="structured_extraction", task_schema=task_schema, output_schema=SCHEMA,
        evidence_inputs=evidence_inputs, prompt_template_id="prompt", prompt_template_version="1", policy_refs=policies,
        provider_id=provider, model_snapshot=model, parameters={"temperature": Decimal("0")}, material_tool_versions=tools)
    return ModelTask(
        record_id=deterministic_id("modeltask:", {"subject_id": subject_id, "scope_id": None, "task_type": "structured_extraction", "cache_key": cache, "output_schema": SCHEMA}),
        created_at=NOW, producer={"kind": "code", "producer_id": "test", "version": "1"}, subject_id=subject_id,
        task_type="structured_extraction", task_schema=task_schema, output_schema=SCHEMA, evidence_inputs=evidence_inputs,
        prompt_template_id="prompt", prompt_template_version="1", policy_refs=policies, provider_id=provider, model_snapshot=model,
        parameters={"temperature": Decimal("0")}, material_tool_versions=tools, cache_key=cache,
        paid_output_categories=("extraction",),
    )


def candidate(
    *,
    record_id: str = "candidate:" + "5" * 32,
    subject_id: str | None = SUBJECT,
    identity_state: str = "resolved",
    scope_id: str | None = None,
    domain: str = "test",
    payload: Payload = Payload(value="accepted"),
    evidence_refs: tuple[ArtifactRef, ...] = (ref(),),
    claim_basis: str = "direct",
    extraction_method: str = "structured",
    observation_time: ObservationTime = ObservationTime(observed_at=NOW),
    confidence: str | None = None,
    warnings: tuple[str, ...] = (),
):
    return CandidateObservation[Payload](
        record_id=record_id, created_at=NOW,
        producer={"kind": "model", "producer_id": "fake", "version": "1"}, subject_id=subject_id, identity_state=identity_state,
        scope_id=scope_id, domain=domain, payload_schema=SCHEMA, payload=payload, evidence=evidence_refs,
        claim_basis_proposed=claim_basis, extraction_method=extraction_method, observation_time=observation_time,
        confidence_proposed=confidence, warnings=warnings, generation_policy_id="generation-v1",
    )


def decision(cand, *, disposition: str = "accepted", replacement=None, lineage=None):
    record_id = "decision:" + "6" * 32
    if lineage is None:
        lineage = (LineageEdge(edge_type="reviewed_by", source_artifact_id=cand.record_id, target_artifact_id=record_id),)
    return DecisionRecord(
        record_id=record_id, created_at=NOW, producer={"kind": "human", "producer_id": "reviewer", "version": "1"},
        candidate_id=cand.record_id, disposition=disposition,
        authority=HumanAuthority(actor_id="reviewer", role="analyst", authority_policy_id="review-v1"),
        rationale="Synthetic decision", replacement_candidate_id=None if replacement is None else replacement.record_id,
        decided_at=NOW, lineage=lineage,
    )


def observation(cand, dec, *, payload=None, evidence_refs=None, candidate_id=None, lineage=None, qualifications=(), **overrides):
    record_id = "observation:" + "7" * 32
    promoted_id = cand.record_id if candidate_id is None else candidate_id
    if lineage is None:
        lineage = (LineageEdge(edge_type="promoted_as", source_artifact_id=promoted_id, target_artifact_id=record_id),)
    values = {
        "record_id": record_id, "created_at": NOW,
        "producer": {"kind": "code", "producer_id": "canonicaliser", "version": "1"},
        "subject_id": cand.subject_id, "scope_id": cand.scope_id, "domain": cand.domain,
        "payload_schema": cand.payload_schema, "payload": cand.payload if payload is None else payload,
        "candidate_id": promoted_id, "decision_id": dec.record_id,
        "evidence": cand.evidence if evidence_refs is None else evidence_refs,
        "claim_basis": cand.claim_basis_proposed, "extraction_method": cand.extraction_method,
        "observation_time": cand.observation_time, "confidence": cand.confidence_proposed,
        "qualifications": qualifications, "warnings": cand.warnings, "lineage": lineage,
    }
    values.update(overrides)
    return CanonicalObservation[Payload](**values)
