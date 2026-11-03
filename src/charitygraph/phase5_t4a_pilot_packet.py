"""Immutable, provider-free Gate 4 T4A2a semantic task packet.

This module composes the accepted T3 retained-cohort binding with the
accepted T3-T2 Factory plan.  It does not acquire, interpret, price, batch,
send, or persist provider work.  Source bodies and prompt text are excluded;
the packet carries only typed identities, hashes, and policy state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts.canonical import canonical_sha256
from .contracts.ids import deterministic_id
from .phase5_governed_real_cohort_rehearsal import build_real_evidence_factory_plan
from .phase5_governed_source_binding import (
    SELECTED_MANIFEST_SHA256,
    SOURCE_EVIDENCE_PROVENANCE_EPOCH,
    SOURCE_EVIDENCE_PROVENANCE_REVISION,
    ExclusionEvidence,
)
from .phase5_provider_processing_policy import (
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
)
from .phase5_semantic_contracts import resolve_contract


PACKET_SCHEMA = "charitygraph.gate4.t4a.real-pilot-packet/v1"
SEMANTIC_TASK_TYPE = "direct_service_semantics"
SEMANTIC_TASK_PROFILE = "direct_service_semantics"
SEMANTIC_TASK_PROFILE_VERSION = "1"
SEMANTIC_PROMPT_POLICY_VERSION = "direct-service-access-v1:prompt-policy:v2"
SEMANTIC_PLANNER_SCHEMA_VERSION = "urn:charitygraph:phase5:planned:direct_service_semantics:v1"
RIGHTS_POLICY_ID = "CG_INTERNAL_PRIVATE_USE_RIGHTS_POLICY_V1"
RIGHTS_POLICY_VERSION = "1.0.0"


@dataclass(frozen=True)
class PacketProvenance:
    requested_source_epoch: str
    source_epoch: str
    source_producer_revision: str
    selected_manifest_sha256: str
    bridge_fence: str
    branch: str
    head: str

    def as_dict(self) -> dict[str, str]:
        return {
            "requested_source_evidence_epoch": self.requested_source_epoch,
            "source_evidence_epoch": self.source_epoch,
            "source_evidence_producer_revision": self.source_producer_revision,
            "selected_manifest_sha256": self.selected_manifest_sha256,
            "bridge_execution_epoch": self.bridge_fence,
            "bridge_branch": self.branch,
            "bridge_head": self.head,
        }


@dataclass(frozen=True)
class SourceBinding:
    ordinal: int
    subject_id: str
    scope_id: str | None
    source_family: str
    source_definition_id: str
    source_record_id: str
    acquisition_receipt_id: str
    source_artifact_id: str
    source_sha256: str
    representation_artifact_id: str | None
    representation_sha256: str | None
    evidence_locator_id: str | None
    rights_record_id: str | None
    status: str
    provider_processing_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_family": self.source_family,
            "source_definition_id": self.source_definition_id,
            "source_record_id": self.source_record_id,
            "acquisition_receipt_id": self.acquisition_receipt_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "representation_artifact_id": self.representation_artifact_id,
            "representation_sha256": self.representation_sha256,
            "evidence_locator_id": self.evidence_locator_id,
            "rights_record_id": self.rights_record_id,
            "status": self.status,
            "provider_processing_status": self.provider_processing_status,
        }


@dataclass(frozen=True)
class SemanticContractReference:
    contract_id: str
    contract_version: str
    task_profile: str
    task_profile_version: str
    prompt_id: str
    prompt_sha256: str
    schema_id: str
    schema_version: str
    schema_sha256: str
    identity_sha256: str
    planner_schema_version: str

    def as_dict(self) -> dict[str, str]:
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "task_profile": self.task_profile,
            "task_profile_version": self.task_profile_version,
            "prompt_id": self.prompt_id,
            "prompt_sha256": self.prompt_sha256,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "schema_sha256": self.schema_sha256,
            "identity_sha256": self.identity_sha256,
            "planner_schema_version": self.planner_schema_version,
        }


@dataclass(frozen=True)
class TaskLineage:
    source_definition_ids: tuple[str, ...]
    acquisition_receipt_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    evidence_locator_ids: tuple[str, ...]
    representation_artifact_ids: tuple[str, ...]
    representation_hashes: tuple[tuple[str, str], ...]
    rights_record_ids: tuple[str, ...]
    rights_policy_ids: tuple[str, ...]
    rights_roles: tuple[str, ...]
    governed_reference_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_definition_ids": list(self.source_definition_ids),
            "acquisition_receipt_ids": list(self.acquisition_receipt_ids),
            "source_record_ids": list(self.source_record_ids),
            "evidence_locator_ids": list(self.evidence_locator_ids),
            "representation_artifact_ids": list(self.representation_artifact_ids),
            "representation_hashes": {key: value for key, value in self.representation_hashes},
            "rights_record_ids": list(self.rights_record_ids),
            "rights_policy_ids": list(self.rights_policy_ids),
            "rights_roles": list(self.rights_roles),
            "governed_reference_hash": self.governed_reference_hash,
        }


@dataclass(frozen=True)
class SemanticTask:
    semantic_task_id: str
    idempotency_key: str
    factory_logical_task_id: str
    model_task_id: str
    subject_id: str
    scope_id: str | None
    source_family: str
    task_type: str
    task_profile: str
    task_profile_version: str
    task_schema_version: str
    semantic_contract_hash: str
    lineage: TaskLineage

    def as_dict(self) -> dict[str, Any]:
        return {
            "semantic_task_id": self.semantic_task_id,
            "idempotency_key": self.idempotency_key,
            "factory_logical_task_id": self.factory_logical_task_id,
            "model_task_id": self.model_task_id,
            "subject_id": self.subject_id,
            "scope_id": self.scope_id,
            "source_family": self.source_family,
            "task_type": self.task_type,
            "task_profile": self.task_profile,
            "task_profile_version": self.task_profile_version,
            "task_schema_version": self.task_schema_version,
            "semantic_contract_hash": self.semantic_contract_hash,
            "rights": {
                "status": "authorized_for_private_use",
                "policy_ids": list(self.lineage.rights_policy_ids),
                "record_ids": list(self.lineage.rights_record_ids),
                "roles": list(self.lineage.rights_roles),
            },
            "provider_processing": {
                "status": "blocked",
                "reason": "provider_contract_unbound",
                "policy_id": PROVIDER_PROCESSING_POLICY_ID,
                "policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
            },
            "lineage": self.lineage.as_dict(),
        }


@dataclass(frozen=True)
class PilotPacket:
    packet_id: str
    packet_sha256: str
    provenance: PacketProvenance
    cohort_id: str
    cohort_plan_sha256: str
    semantic_contract: SemanticContractReference
    subject_ids: tuple[str, ...]
    source_bindings: tuple[SourceBinding, ...]
    task_keys: tuple[tuple[str, str], ...]
    tasks: tuple[SemanticTask, ...]
    factory_status: str
    blocked_reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rows = tuple(self.source_bindings)
        source_statuses = {row.status for row in rows}
        rights_accepted = bool(rows) and all(
            row.status in {"eligible_private_local_retention", "bound_not_task_eligible"}
            for row in rows
        )
        core = {
            "schema": PACKET_SCHEMA,
            "packet_id": self.packet_id,
            "mode": "no_send",
            "provenance": self.provenance.as_dict(),
            "cohort": {
                "cohort_id": self.cohort_id,
                "cohort_plan_sha256": self.cohort_plan_sha256,
                "subject_ids": list(self.subject_ids),
                "subject_count": len(self.subject_ids),
                "source_record_count": len(rows),
                "task_count": len(self.tasks),
                "task_key_count": len(self.task_keys),
                "expected_subject_count": 5,
                "expected_source_record_count": 10,
            },
            "semantic_contract": self.semantic_contract.as_dict(),
            "rights": {
                "status": "accepted" if rights_accepted else "blocked",
                "policy_id": RIGHTS_POLICY_ID,
                "policy_version": RIGHTS_POLICY_VERSION,
                "source_families": ["acnc_register", "acnc_ais_bundle"],
                "public_redistribution": "not_assessed",
            },
            "provider_processing": {
                "status": "blocked",
                "eligibility": "not_eligible_without_bound_contract",
                "policy_id": PROVIDER_PROCESSING_POLICY_ID,
                "policy_version": PROVIDER_PROCESSING_POLICY_VERSION,
            },
            "provider_contract": {
                "status": "unbound",
                "contract_id": None,
                "project_id": None,
                "service": None,
                "model": None,
                "version": None,
            },
            "factory": {
                "status": self.factory_status,
                "accepted_task_count": len(self.tasks),
                "source_statuses": sorted(source_statuses),
            },
            "tasks": [task.as_dict() for task in self.tasks],
            "task_keys": [{"semantic_task_id": key, "idempotency_key": value} for key, value in self.task_keys],
            "source_bindings": [row.as_dict() for row in rows],
            "preflight": {
                "status": "blocked",
                "reasons": list(self.blocked_reasons),
                "send": {
                    "status": "blocked",
                    "reason": "no_send_tranche_and_provider_contract_unbound",
                },
                "side_effects": {
                    "provider_calls": 0,
                    "model_outputs": 0,
                    "reservations": 0,
                    "cost_entries": 0,
                    "acquisitions": 0,
                    "publications": 0,
                },
            },
        }
        return {**core, "packet_identity_sha256": canonical_sha256(core)}


def _contract_identity(contract: Any, evidence_ids: tuple[str, ...]) -> dict[str, Any]:
    """Expose contract identity and hashes, never prompt or schema bodies."""

    return {
        "contract_id": contract.contract_id,
        "contract_version": contract.contract_version,
        "task_profile": contract.task_profile,
        "task_profile_version": contract.task_profile_version,
        "claim_families": list(contract.claim_families),
        "prompt_id": contract.prompt_id,
        "prompt_sha256": contract.prompt_sha256,
        "schema_id": contract.schema_id,
        "schema_version": contract.schema_version,
        "schema_sha256": contract.schema_hash_for_evidence(evidence_ids),
        "identity_sha256": contract.identity_hash(evidence_ids),
        "route_class": contract.route_class,
        "reasoning_policy": contract.reasoning_policy,
        "authority_state": contract.authority_state,
        "planner_prompt_policy_version": contract.planner_prompt_policy_version,
        "planner_schema_version": contract.planner_schema_version,
        "provider_schema_name": contract.provider_schema_name,
    }


def _contract_reference() -> SemanticContractReference:
    contract = resolve_contract({
        "claim_family_id": "direct-service-access-v1",
        "task_profile": SEMANTIC_TASK_PROFILE,
        "task_profile_version": SEMANTIC_TASK_PROFILE_VERSION,
        "prompt_policy_version": SEMANTIC_PROMPT_POLICY_VERSION,
        "schema_version": SEMANTIC_PLANNER_SCHEMA_VERSION,
    })
    contract.assert_complete()
    return SemanticContractReference(
        contract_id=contract.contract_id,
        contract_version=contract.contract_version,
        task_profile=contract.task_profile,
        task_profile_version=contract.task_profile_version,
        prompt_id=contract.prompt_id,
        prompt_sha256=contract.prompt_sha256,
        schema_id=contract.schema_id,
        schema_version=contract.schema_version,
        schema_sha256=contract.schema_hash_for_evidence(()),
        identity_sha256=contract.identity_hash(()),
        planner_schema_version=contract.planner_schema_version,
    )


def _source_binding(row: Mapping[str, Any]) -> SourceBinding:
    return SourceBinding(
        ordinal=int(row["ordinal"]),
        subject_id=str(row["subject_id"]),
        scope_id=row.get("scope_id"),
        source_family=str(row["source_family"]),
        source_definition_id=str(row["source_definition_id"]),
        source_record_id=str(row["source_record_id"]),
        acquisition_receipt_id=str(row["acquisition_receipt_id"]),
        source_artifact_id=str(row["source_artifact_id"]),
        source_sha256=str(row["source_sha256"]),
        representation_artifact_id=row.get("representation_artifact_id"),
        representation_sha256=row.get("representation_sha256"),
        evidence_locator_id=row.get("evidence_locator_id"),
        rights_record_id=row.get("rights_record_id"),
        status=str(row.get("status", "blocked")),
        provider_processing_status=str(row.get("provider_processing_status", "blocked")),
    )


def _provenance(
    execution_context: Mapping[str, str],
    manifest: Mapping[str, Any] | None,
    requested_source_epoch: str,
) -> PacketProvenance:
    source = {} if manifest is None else dict(manifest.get("source_evidence_provenance") or {})
    bridge = dict(execution_context)
    if manifest is not None:
        bridge = dict(manifest.get("bridge_execution_context") or bridge)
    return PacketProvenance(
        requested_source_epoch=requested_source_epoch,
        source_epoch=str(source.get("epoch", SOURCE_EVIDENCE_PROVENANCE_EPOCH)),
        source_producer_revision=str(source.get("producer_revision", SOURCE_EVIDENCE_PROVENANCE_REVISION)),
        selected_manifest_sha256=str(source.get("selected_manifest_sha256", SELECTED_MANIFEST_SHA256)),
        bridge_fence=str(bridge.get("bridge_fence", "unbound")),
        branch=str(bridge.get("branch", "unbound")),
        head=str(bridge.get("head", "unbound")),
    )


def _build_tasks(
    factory_tasks: tuple[Mapping[str, Any], ...],
    rows: tuple[SourceBinding, ...],
) -> tuple[SemanticTask, ...]:
    contract = resolve_contract({
        "claim_family_id": "direct-service-access-v1",
        "task_profile": SEMANTIC_TASK_PROFILE,
        "task_profile_version": SEMANTIC_TASK_PROFILE_VERSION,
        "prompt_policy_version": SEMANTIC_PROMPT_POLICY_VERSION,
        "schema_version": SEMANTIC_PLANNER_SCHEMA_VERSION,
    })
    contract.assert_complete()
    row_by_record = {row.source_record_id: row for row in rows}
    built: list[SemanticTask] = []
    for base in factory_tasks:
        source_record_ids = tuple(base.get("source_record_ids", ()))
        if len(source_record_ids) != 1 or source_record_ids[0] not in row_by_record:
            raise ValueError("Factory task does not bind exactly one retained source row")
        row = row_by_record[source_record_ids[0]]
        evidence_ids = tuple(base.get("evidence_locator_ids", ()))
        contract_hash = contract.identity_hash(evidence_ids)
        identity = {
            "factory_logical_task_id": base["logical_task_id"],
            "subject_id": base["subject_id"],
            "scope_id": base.get("scope_id"),
            "source_record_ids": source_record_ids,
            "representation_hashes": base.get("representation_hashes", ()),
            "semantic_contract_hash": contract_hash,
        }
        semantic_id = deterministic_id("semtask:", identity)
        idempotency_key = "idempotency:" + canonical_sha256({"semantic_task_id": semantic_id, "identity": identity})
        representation_hashes = tuple(sorted((str(key), str(value)) for key, value in dict(base.get("representation_hashes", {})).items()))
        lineage = TaskLineage(
            source_definition_ids=tuple(base.get("source_definition_ids", ())),
            acquisition_receipt_ids=tuple(base.get("acquisition_receipt_ids", ())),
            source_record_ids=source_record_ids,
            evidence_locator_ids=evidence_ids,
            representation_artifact_ids=tuple(base.get("representation_artifact_ids", ())),
            representation_hashes=representation_hashes,
            rights_record_ids=(str(row.rights_record_id),) if row.rights_record_id else (),
            rights_policy_ids=tuple(base.get("rights_policy_ids", ())),
            rights_roles=tuple(base.get("rights_roles", ())),
            governed_reference_hash=str(base.get("governed_reference_hash", "")),
        )
        built.append(SemanticTask(
            semantic_task_id=semantic_id,
            idempotency_key=idempotency_key,
            factory_logical_task_id=str(base["logical_task_id"]),
            model_task_id=str(base.get("record_id", "")),
            subject_id=str(base["subject_id"]),
            scope_id=base.get("scope_id"),
            source_family=row.source_family,
            task_type=SEMANTIC_TASK_TYPE,
            task_profile=contract.task_profile,
            task_profile_version=contract.task_profile_version,
            task_schema_version=contract.planner_schema_version,
            semantic_contract_hash=contract_hash,
            lineage=lineage,
        ))
    return tuple(sorted(built, key=lambda task: task.semantic_task_id))


def build_t4a_pilot_packet(
    *,
    source_archive_root: str | Path,
    work_root: str | Path,
    execution_context: Mapping[str, str],
    source_evidence_epoch: str = SOURCE_EVIDENCE_PROVENANCE_EPOCH,
    exclusions: Mapping[int, ExclusionEvidence] | None = None,
) -> PilotPacket:
    """Build a deterministic no-send packet, failing closed on any seam."""

    manifest: Mapping[str, Any] | None = None
    factory_tasks: tuple[Mapping[str, Any], ...] = ()
    factory_blocked = True
    reasons: list[str] = ["provider contract ID/project/service/model is unbound"]
    try:
        plan = build_real_evidence_factory_plan(
            source_archive_root=source_archive_root,
            work_root=work_root,
            execution_context=execution_context,
            source_evidence_epoch=source_evidence_epoch,
            exclusions=exclusions,
        )
        manifest = plan.manifest
        factory_tasks = tuple(plan.factory_plan.logical_tasks)
        factory_blocked = plan.blocked_reason is not None
        if plan.blocked_reason is not None:
            reasons.insert(0, plan.blocked_reason)
    except (KeyError, OSError, RuntimeError, ValueError, TypeError) as exc:
        reasons.insert(0, f"retained cohort constructor failed closed: {type(exc).__name__}")

    rows = tuple(sorted((_source_binding(row) for row in (manifest or {}).get("rows", ())), key=lambda row: row.ordinal))
    subject_ids = tuple(sorted({row.subject_id for row in rows}))
    tasks: tuple[SemanticTask, ...] = ()
    factory_status = "blocked"
    if factory_blocked and not any("failed closed" in reason or "not eligible" in reason or "outside" in reason or "blocked" in reason for reason in reasons):
        reasons.insert(0, "retained cohort plan is unavailable")
    if not any("blocked" in reason or "unbound" in reason for reason in reasons):
        reasons.insert(0, "no-send guard is active")
    if not factory_blocked and not any(row.status != "eligible_private_local_retention" for row in rows) and len(rows) == 10 and len(subject_ids) == 5 and len(factory_tasks) == 10:
        try:
            tasks = _build_tasks(factory_tasks, rows)
            factory_status = "accepted"
        except (KeyError, ValueError, TypeError) as exc:
            reasons.insert(0, f"semantic task lowering failed closed: {type(exc).__name__}")
    if len(rows) != 10:
        reasons.append(f"retained source count is {len(rows)}; expected 10")
    if len(subject_ids) != 5:
        reasons.append(f"retained subject count is {len(subject_ids)}; expected 5")
    if len(factory_tasks) != 10 and rows:
        reasons.append(f"Factory task count is {len(factory_tasks)}; expected 10")
    if any(row.status != "eligible_private_local_retention" for row in rows):
        reasons.append("one or more retained source rows are not eligible")
    reasons = list(dict.fromkeys(reasons))
    provenance = _provenance(execution_context, manifest, source_evidence_epoch)
    semantic_contract = _contract_reference()
    cohort_id = "unbound"
    cohort_plan_sha256 = canonical_sha256({"manifest": provenance.selected_manifest_sha256, "subjects": subject_ids, "tasks": [task.factory_logical_task_id for task in tasks]})
    if manifest is not None:
        cohort_id = str(plan.cohort_id)
        cohort_plan_sha256 = str(plan.cohort_plan_sha256)
    task_keys: list[tuple[str, str]] = []
    if tasks:
        task_keys = [(task.semantic_task_id, task.idempotency_key) for task in tasks]
    elif rows:
        for row in rows:
            key_identity = {
                "route": PACKET_SCHEMA,
                "subject_id": row.subject_id,
                "scope_id": row.scope_id,
                "source_record_id": row.source_record_id,
                "source_sha256": row.source_sha256,
            }
            semantic_key = deterministic_id("semtask:", key_identity)
            idempotency_key = "idempotency:" + canonical_sha256(key_identity)
            task_keys.append((semantic_key, idempotency_key))
    task_keys = sorted(task_keys)
    packet_id = deterministic_id("semtask:", {
        "schema": PACKET_SCHEMA,
        "cohort_id": cohort_id,
        "cohort_plan_sha256": cohort_plan_sha256,
        "task_ids": [key for key, _ in task_keys],
        "source_manifest_sha256": provenance.selected_manifest_sha256,
    })
    provisional = PilotPacket(
        packet_id=packet_id,
        packet_sha256="",
        provenance=provenance,
        cohort_id=cohort_id,
        cohort_plan_sha256=cohort_plan_sha256,
        semantic_contract=semantic_contract,
        subject_ids=subject_ids,
        source_bindings=rows,
        task_keys=tuple(task_keys),
        tasks=tasks,
        factory_status=factory_status,
        blocked_reasons=tuple(reasons),
    )
    packet_hash = canonical_sha256({key: value for key, value in provisional.as_dict().items() if key != "packet_identity_sha256"})
    return PilotPacket(
        packet_id=provisional.packet_id,
        packet_sha256=packet_hash,
        provenance=provisional.provenance,
        cohort_id=provisional.cohort_id,
        cohort_plan_sha256=provisional.cohort_plan_sha256,
        semantic_contract=provisional.semantic_contract,
        subject_ids=provisional.subject_ids,
        source_bindings=provisional.source_bindings,
        task_keys=provisional.task_keys,
        tasks=provisional.tasks,
        factory_status=provisional.factory_status,
        blocked_reasons=provisional.blocked_reasons,
    )


__all__ = ["PACKET_SCHEMA", "PilotPacket", "SemanticContractReference", "SemanticTask", "SourceBinding", "build_t4a_pilot_packet"]
