"""Provider-free, single-subject offline packet over the retained T3 cohort.

The packet is a provenance/audit artifact only.  It composes the current T3
source binding and Factory plan, emits no source bytes, and never crosses a
provider or budget boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from .contracts.canonical import canonical_sha256
from .contracts.ids import deterministic_id
from .phase5_governed_real_cohort_rehearsal import (
    REAL_COHORT_SCHEMA,
    build_real_evidence_factory_plan,
)
from .phase5_governed_source_binding import (
    SELECTED_MANIFEST_SHA256,
    SOURCE_EVIDENCE_PROVENANCE_EPOCH,
    SOURCE_EVIDENCE_PROVENANCE_REVISION,
)
from .phase5_provider_processing_policy import (
    PROVIDER_PROCESSING_POLICY_ID,
    PROVIDER_PROCESSING_POLICY_VERSION,
)
from .phase5_semantic_contracts import REGISTRY, resolve_contract
from .runtime.migrations import SUPPORTED_VERSION
from .runtime.rights_governance_record import (
    INTERNAL_PRIVATE_USE_POLICY_ID,
    INTERNAL_PRIVATE_USE_POLICY_VERSION,
    SCHEMA_ID as RIGHTS_RECORD_SCHEMA_ID,
    SCHEMA_VERSION as RIGHTS_RECORD_SCHEMA_VERSION,
)
PACKET_SCHEMA = "charitygraph.gate4.t4a.single-subject-offline-packet/v1"
REPRESENTATION_SCHEMA_ID = "urn:charitygraph:builder:schema:acnc-source-native-representation:1.0"
REPRESENTATION_SCHEMA_VERSION = "1.0"
EXPECTED_BRANCH = "gate3-cg406-remediation"
EXPECTED_HEAD = "372ca4183ee9511d99e3c06bab1a5c17bf0aa4b5"
EXPECTED_FENCE = "v51"
@dataclass(frozen=True)
class OfflinePacketDiagnostic:
    code: str
    reason: str
    details: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "reason": self.reason, "details": list(self.details)}


@dataclass(frozen=True)
class SingleSubjectOfflinePacket:
    document: dict[str, Any]
    packet_sha256: str
    diagnostics: tuple[OfflinePacketDiagnostic, ...]
def _diagnostic(code: str, reason: str, *details: str) -> OfflinePacketDiagnostic:
    return OfflinePacketDiagnostic(code, reason, tuple(details))


def _semantic_contract() -> Any:
    candidates = [
        item for item in REGISTRY
        if item.task_profile == "direct_service_semantics"
        and item.claim_families == ("direct-service-access-v1",)
    ]
    if not candidates:
        raise ValueError("direct-service semantic contract is not registered")
    declared = max(candidates, key=lambda item: item.contract_version)
    # Bind against the registry's actual current values.  This is deliberate:
    # resolve_contract rejects a guessed or stale planner schema version.
    contract = resolve_contract({
        "claim_family_id": declared.claim_families[0],
        "task_profile": declared.task_profile,
        "task_profile_version": declared.task_profile_version,
        "prompt_policy_version": declared.planner_prompt_policy_version,
        "schema_version": declared.planner_schema_version,
    })
    contract.assert_complete()
    return contract
def _contract_identity(contract: Any, evidence_ids: tuple[str, ...]) -> dict[str, Any]:
    return {
        "contract_id": contract.contract_id,
        "contract_version": contract.contract_version,
        "task_profile": contract.task_profile,
        "task_profile_version": contract.task_profile_version,
        "prompt_id": contract.prompt_id,
        "prompt_sha256": contract.prompt_sha256,
        "schema_id": contract.schema_id,
        "schema_version": contract.schema_version,
        "schema_sha256": contract.schema_hash_for_evidence(evidence_ids),
        "identity_sha256": contract.identity_hash(evidence_ids),
        "planner_prompt_policy_version": contract.planner_prompt_policy_version,
        "planner_schema_version": contract.planner_schema_version,
    }


def _source_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ordinal": int(row["ordinal"]),
        "subject_id": row["subject_id"],
        "scope_id": row.get("scope_id"),
        "source_family": row["source_family"],
        "source_role": row.get("source_role"),
        "source_definition_id": row["source_definition_id"],
        "source_record_id": row["source_record_id"],
        "acquisition_receipt_id": row["acquisition_receipt_id"],
        "source_artifact_id": row["source_artifact_id"],
        "source_sha256": row["source_sha256"],
        "representation_artifact_id": row.get("representation_artifact_id"),
        "representation_sha256": row.get("representation_sha256"),
        "evidence_locator_id": row.get("evidence_locator_id"),
        "rights_record_id": row.get("rights_record_id"),
        "status": row.get("status"),
    }
def _validate_rows(rows: list[Mapping[str, Any]], subject_id: str, rights: Mapping[str, Any]) -> list[OfflinePacketDiagnostic]:
    diagnostics: list[OfflinePacketDiagnostic] = []
    if len(rows) != 2 or {row.get("source_family") for row in rows} != {"acnc_register", "acnc_ais_bundle"}:
        diagnostics.append(_diagnostic("source_binding_mismatch", "the requested subject does not have exactly one retained register and AIS record"))
    scopes = {row.get("scope_id") for row in rows}
    if len(scopes) != 1 or None in scopes:
        diagnostics.append(_diagnostic("subject_binding_mismatch", "the exact subject scope binding is missing or inconsistent"))
    for row in rows:
        if row.get("subject_id") != subject_id:
            diagnostics.append(_diagnostic("subject_binding_mismatch", "a retained row is bound to a different subject", str(row.get("source_record_id"))))
        gaps = tuple(str(item) for item in row.get("technical_gaps", ()))
        provider_only_block = row.get("status") == "bound_not_task_eligible" and gaps and all(
            "provider contract" in item or "provider_contract_identity_and_version" in item or "provider rights decision references are absent" in item for item in gaps
        )
        if row.get("status") != "eligible_private_local_retention" and not provider_only_block:
            diagnostics.append(_diagnostic("evidence_unavailable", "retained evidence is not eligible under the current T3 authority", str(row.get("source_record_id"))))
        if not row.get("rights_record_id"):
            diagnostics.append(_diagnostic("rights_unavailable", "the exact retained row has no durable rights record", str(row.get("source_record_id"))))
        if row.get("representation_artifact_id") in (None, row.get("source_artifact_id")):
            diagnostics.append(_diagnostic("representation_mismatch", "the derived representation is missing or relabelled as the source artifact", str(row.get("source_record_id"))))
        if row.get("representation_sha256") != row.get("source_sha256"):
            diagnostics.append(_diagnostic("representation_mismatch", "the source-native representation hash drifted from the retained source hash", str(row.get("source_record_id"))))
        if row.get("rights_policy_id") not in (None, rights.get("id")) or row.get("rights_policy_version") not in (None, rights.get("version")):
            diagnostics.append(_diagnostic("rights_unavailable", "the row rights identity does not match the current T3 policy", str(row.get("source_record_id"))))
    return diagnostics


def build_single_subject_offline_packet(
    *,
    source_archive_root: str | Path,
    work_root: str | Path,
    execution_context: Mapping[str, str],
    subject_id: str,
) -> SingleSubjectOfflinePacket:
    """Build one exact-subject/two-record packet, or a blocked diagnostic."""
    diagnostics: list[OfflinePacketDiagnostic] = []
    context = dict(execution_context)
    if context != {"bridge_fence": EXPECTED_FENCE, "branch": EXPECTED_BRANCH, "head": EXPECTED_HEAD}:
        diagnostics.append(_diagnostic("execution_context_mismatch", "packet context is not the instructed exact branch, HEAD and fence"))

    contract: Any | None = None
    try:
        contract = _semantic_contract()
    except (KeyError, PermissionError, TypeError, ValueError) as exc:
        diagnostics.append(_diagnostic("schema_version_mismatch", "current semantic contract could not be resolved exactly", type(exc).__name__, str(exc)))

    plan = None
    try:
        plan = build_real_evidence_factory_plan(
            source_archive_root=source_archive_root,
            work_root=work_root,
            execution_context=context,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        diagnostics.append(_diagnostic("evidence_unavailable", "retained T3 evidence could not be bound", type(exc).__name__))

    manifest: Mapping[str, Any] = {} if plan is None or plan.manifest is None else plan.manifest
    rows_all = list(manifest.get("rows", ()))
    if plan is None or plan.manifest is None:
        diagnostics.append(_diagnostic("evidence_unavailable", "the exact retained T3 manifest is unavailable"))
    if manifest.get("schema") != "charitygraph.gate4.t3.selected-binding-manifest/v2":
        diagnostics.append(_diagnostic("schema_version_mismatch", "retained manifest schema is not the current T3 v2 contract", str(manifest.get("schema"))))
    if manifest.get("selected_manifest_sha256") != SELECTED_MANIFEST_SHA256:
        diagnostics.append(_diagnostic("source_binding_mismatch", "selected T3 manifest identity is not the retained immutable identity"))
    provenance = manifest.get("source_evidence_provenance") or {}
    if provenance.get("epoch") != SOURCE_EVIDENCE_PROVENANCE_EPOCH or provenance.get("producer_revision") != SOURCE_EVIDENCE_PROVENANCE_REVISION:
        diagnostics.append(_diagnostic("source_binding_mismatch", "source-evidence provenance is not the current immutable T3 authority"))
    if manifest.get("manifest_identity_sha256"):
        core = {key: value for key, value in manifest.items() if key != "manifest_identity_sha256"}
        if canonical_sha256(core) != manifest["manifest_identity_sha256"]:
            diagnostics.append(_diagnostic("source_binding_mismatch", "emitted T3 manifest identity hash does not verify"))

    subjects = {row.get("subject_id") for row in rows_all}
    if len(rows_all) != 10 or len(subjects) != 5:
        diagnostics.append(_diagnostic("source_binding_mismatch", "the Factory input is not the retained five-subject/ten-record cohort"))
    rows = sorted((row for row in rows_all if row.get("subject_id") == subject_id), key=lambda row: int(row["ordinal"]))
    if not rows:
        diagnostics.append(_diagnostic("subject_binding_unavailable", "requested subject is not an exact governed T3 subject", subject_id))
    rights = manifest.get("rights_policy") or {}
    diagnostics.extend(_validate_rows(rows, subject_id, rights))

    tasks = () if plan is None else tuple(task for task in plan.factory_plan.logical_tasks if task.get("subject_id") == subject_id)
    row_records = {str(row.get("source_record_id")) for row in rows}
    task_records = {str(task.get("source_record_ids", (None,))[0]) for task in tasks if task.get("source_record_ids")}
    provider_only_block = bool(rows) and all(
        row.get("status") == "bound_not_task_eligible"
        and tuple(row.get("technical_gaps", ()))
        and all("provider contract" in str(item) or "provider_contract_identity_and_version" in str(item) or "provider rights decision references are absent" in str(item) for item in row.get("technical_gaps", ()))
        for row in rows
    )
    if (len(tasks) != 2 or task_records != row_records) and not provider_only_block:
        diagnostics.append(_diagnostic("factory_binding_mismatch", "exactly two current Factory tasks do not bind the selected records"))

    diagnostics = list(dict.fromkeys(diagnostics))
    evidence_ids = tuple(sorted(str(row["evidence_locator_id"]) for row in rows if row.get("evidence_locator_id")))
    semantic = {} if contract is None else _contract_identity(contract, evidence_ids)
    packet_identity = {
        "schema": PACKET_SCHEMA,
        "subject_id": subject_id,
        "manifest_identity": manifest.get("manifest_identity_sha256"),
        "source_record_ids": sorted(row_records),
        "representation_hashes": sorted(str(row.get("representation_sha256")) for row in rows),
        "semantic_identity": semantic.get("identity_sha256"),
    }
    packet_id = deterministic_id("derivative:", packet_identity)
    core: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "packet_id": packet_id,
        "mode": "offline_internal_no_send",
        "status": "ready" if not diagnostics else "blocked",
        "provenance": {
            "branch": context.get("branch"), "head": context.get("head"), "bridge_fence": context.get("bridge_fence"),
            "source_evidence_epoch": provenance.get("epoch"), "source_evidence_producer_revision": provenance.get("producer_revision"),
            "selected_manifest_sha256": manifest.get("selected_manifest_sha256"),
            "emitted_manifest_identity_sha256": manifest.get("manifest_identity_sha256"),
        },
        "subject": {"subject_id": subject_id, "scope_ids": sorted({row.get("scope_id") for row in rows if row.get("scope_id")}), "source_record_ids": sorted(row_records)},
        "source_records": [_source_identity(row) for row in rows],
        "contracts": {
            "t3_manifest": {"schema": manifest.get("schema")},
            "factory_plan": {"schema": REAL_COHORT_SCHEMA},
            "representation": {"schema_id": REPRESENTATION_SCHEMA_ID, "schema_version": REPRESENTATION_SCHEMA_VERSION},
            "rights_record": {"schema_id": RIGHTS_RECORD_SCHEMA_ID, "schema_version": RIGHTS_RECORD_SCHEMA_VERSION},
            "rights_projection": {"migration_version": SUPPORTED_VERSION},
            "semantic": semantic,
        },
        "rights": {"status": "authorized_for_internal_offline_processing", "policy_id": rights.get("id", INTERNAL_PRIVATE_USE_POLICY_ID), "policy_version": rights.get("version", INTERNAL_PRIVATE_USE_POLICY_VERSION), "rights_record_ids": sorted(str(row.get("rights_record_id")) for row in rows if row.get("rights_record_id")), "public_redistribution": "not_assessed"},
        "provider_processing": {"policy_id": PROVIDER_PROCESSING_POLICY_ID, "policy_version": PROVIDER_PROCESSING_POLICY_VERSION, "status": "blocked", "provider_contract": "unbound", "send_authorization": "not_authorized_for_send"},
        "factory": {"status": "provider_contract_blocked" if provider_only_block else "offline_only", "blocked_reason": None if plan is None else plan.blocked_reason, "logical_task_ids": sorted(str(task["logical_task_id"]) for task in tasks) if not diagnostics else [], "provider_calls": 0, "budget_reservations": 0},
        "missingness": {"provider_contract": "not_authorized_for_send", "semantic_output": "not_attempted", "public_redistribution": "not_assessed", "source_bytes_in_packet": "not_included", "diagnostics": [item.as_dict() for item in diagnostics]},
        "side_effects": {"provider_calls": 0, "transport_requests": 0, "budget_reservations": 0, "cost_entries": 0, "source_acquisitions": 0, "publications": 0},
    }
    packet_sha256 = canonical_sha256(core)
    return SingleSubjectOfflinePacket({**core, "packet_identity_sha256": packet_sha256}, packet_sha256, tuple(diagnostics))

__all__ = ["OfflinePacketDiagnostic", "SingleSubjectOfflinePacket", "build_single_subject_offline_packet"]
