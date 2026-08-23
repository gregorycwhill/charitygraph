from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from charitygraph.contracts import (
    ArtifactRef, CandidateObservation, CanonicalObservation, DecisionRecord, EvidenceFragment,
    EvidenceInput, HumanAuthority, LineageEdge, ModelTask, ObservationTime, SchemaRef,
    SourceRecord, SubjectRecord, VersionedPolicy, VersionedTool, canonical_sha256,
    deterministic_id, model_task_cache_key,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SUBJECT = "subject:" + "1" * 32
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:test-payload:1.0", schema_version="1.0")

class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: str


def ref(artifact_id="evidence:" + "2" * 32):
    return ArtifactRef(artifact_id=artifact_id, content_hash="a" * 64, schema=SCHEMA)


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
    identity={"source_family":"synthetic","source_version":"1","source_locator":"fixture:1","payload_hash":"b"*64}
    return SourceRecord(
        record_id=deterministic_id("srcrec:", identity), created_at=NOW,
        producer={"kind":"code","producer_id":"test","version":"1"},
        source_family="synthetic", source_role="fixture", source_version="1",
        source_locator="fixture:1", observed_at=NOW, payload_ref="fixture-body:1", payload_hash="b"*64,
    )


def evidence():
    source_record=source()
    identity={"source_record_id": source_record.record_id, "locator":"p1:1", "fragment_hash":"c"*64,
              "selection_method":"fixture", "selection_policy_version":"1"}
    return EvidenceFragment(
        record_id=deterministic_id("evidence:", identity), created_at=NOW,
        producer={"kind":"code","producer_id":"test","version":"1"}, source_record=ref(source_record.record_id),
        fragment_kind="text", locator="p1:1", content_ref="fixture-body:1", fragment_hash="c"*64,
        selection_method="fixture", selection_policy_version="1", observed_at=NOW,
    )


def task(subject_id=SUBJECT, evidence_hash="a"*64, provider="fake", model="model-1"):
    task_schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:model-task:1.0", schema_version="1.0")
    output_schema=SCHEMA
    evidence_inputs=(EvidenceInput(evidence_id="evidence:2"+"0"*31, content_hash=evidence_hash, selection_hash="d"*64),)
    policies=(VersionedPolicy(policy_id="policy", version="1"),)
    tools=(VersionedTool(tool_id="parser", version="1"),)
    cache=model_task_cache_key(task_type="structured_extraction", task_schema=task_schema, output_schema=output_schema,
        evidence_inputs=evidence_inputs, prompt_template_id="prompt", prompt_template_version="1", policy_refs=policies,
        provider_id=provider, model_snapshot=model, parameters={"temperature": Decimal("0")}, material_tool_versions=tools)
    return ModelTask(
        record_id=deterministic_id("modeltask:", {"subject_id":subject_id,"scope_id":None,"task_type":"structured_extraction","cache_key":cache,"output_schema":output_schema}),
        created_at=NOW, producer={"kind":"code","producer_id":"test","version":"1"}, subject_id=subject_id,
        task_type="structured_extraction", task_schema=task_schema, output_schema=output_schema, evidence_inputs=evidence_inputs,
        prompt_template_id="prompt", prompt_template_version="1", policy_refs=policies, provider_id=provider, model_snapshot=model,
        parameters={"temperature": Decimal("0")}, material_tool_versions=tools, cache_key=cache,
        paid_output_categories=("extraction",),
    )


def candidate():
    return CandidateObservation[Payload](
        record_id="candidate:" + "5" * 32, created_at=NOW,
        producer={"kind":"model","producer_id":"fake","version":"1"}, subject_id=SUBJECT, identity_state="resolved",
        domain="test", payload_schema=SCHEMA, payload=Payload(value="accepted"), evidence=(ref(),),
        claim_basis_proposed="direct", extraction_method="structured", observation_time=ObservationTime(observed_at=NOW),
        generation_policy_id="generation-v1",
    )


def decision(cand):
    rid="decision:" + "6" * 32
    return DecisionRecord(
        record_id=rid, created_at=NOW, producer={"kind":"human","producer_id":"reviewer","version":"1"},
        candidate_id=cand.record_id, disposition="accepted", authority=HumanAuthority(actor_id="reviewer", role="analyst", authority_policy_id="review-v1"),
        rationale="Synthetic acceptance", decided_at=NOW,
        lineage=(LineageEdge(edge_type="reviewed_by", source_artifact_id=cand.record_id, target_artifact_id=rid),),
    )


def observation(cand, dec):
    rid="observation:" + "7" * 32
    return CanonicalObservation[Payload](
        record_id=rid, created_at=NOW, producer={"kind":"code","producer_id":"canonicaliser","version":"1"},
        subject_id=SUBJECT, domain="test", payload_schema=SCHEMA, payload=Payload(value="accepted"), candidate_id=cand.record_id,
        decision_id=dec.record_id, evidence=(ref(),), claim_basis="direct", extraction_method="structured",
        observation_time=ObservationTime(observed_at=NOW), lineage=(LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id=rid),),
    )
