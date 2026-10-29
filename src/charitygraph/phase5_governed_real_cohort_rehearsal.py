"""Provider-free integration of the retained T3 cohort with the clean Factory.

The source binding remains the authority for real evidence and rights identity.
This module only composes that binding, clean rights preflight, and the existing
Factory control plane in disposable caller-owned state.  It never acquires
sources, interprets prose, or sends a provider request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts.canonical import canonical_sha256
from .contracts.ids import deterministic_id
from .evidence_store import ContentAddressedArtifactStore
from .phase5_factory import FactoryPlan, ReferenceFactory, RehearsalFakeProvider
from .phase5_governed_cohort_rehearsal import persisted_diagnostic
from .phase5_governed_rights_preflight import (
    GovernedRightsFactoryPreflight,
    RightsPreflightReference,
    preflight_governed_rights,
)
from .phase5_governed_source_binding import (
    AS_OF,
    SELECTED_MANIFEST_SHA256,
    SOURCE_EVIDENCE_PROVENANCE_EPOCH,
    BindingBuildResult,
    ExclusionEvidence,
    build_selected_binding_manifest,
)
from .runtime import SQLiteCatalog
from .runtime.rights_governance_projection import RightsGovernanceProjection
from .runtime.rights_governance_record import RightsGovernanceStore


NOW = datetime(2026, 10, 29, tzinfo=timezone.utc)
REAL_COHORT_SCHEMA = "charitygraph.gate4.t3.real-evidence-factory-plan/v1"


@dataclass(frozen=True)
class RealCohortFactoryPlan:
    """The real-evidence plan plus its content-addressed control-plane view."""

    binding: BindingBuildResult | None
    preflight: GovernedRightsFactoryPreflight
    factory_plan: FactoryPlan
    manifest: Mapping[str, Any] | None
    cohort_id: str
    cohort_plan: dict[str, Any]
    cohort_plan_sha256: str
    blocked_reason: str | None = None

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(item["logical_task_id"] for item in self.factory_plan.logical_tasks)


@dataclass(frozen=True)
class RealCohortExecution:
    cohort_id: str
    run_id: str
    completed_tasks: int
    task_count: int
    attempt_count: int
    fake_send_calls: int
    diagnostic_sha256: str
    aud_actual: str
    aud_released: str


def _task_identity(task: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the stable task contract, excluding the in-memory ModelTask object."""

    keys = (
        "logical_task_id", "record_id", "subject_id", "scope_id", "difficulty",
        "source_definition_ids", "acquisition_receipt_ids", "source_record_ids",
        "evidence_locator_ids", "representation_artifact_ids", "representation_hashes",
        "rights_policy_ids", "rights_roles", "governed_reference_hash",
    )
    return {key: task.get(key) for key in keys if key in task}


def _coverage(manifest: Mapping[str, Any], task_count: int) -> dict[str, Any]:
    rows = list(manifest.get("rows", ()))
    statuses = {str(row.get("status")) for row in rows}
    return {
        "candidate_rows": len(rows),
        "admitted_subject_count": len({row.get("subject_id") for row in rows}),
        "admitted_source_count": len(rows),
        "eligible_rows": sum(row.get("status") == "eligible_private_local_retention" for row in rows),
        "task_count": task_count,
        "missingness": {
            "missing": sum(row.get("status") == "missing" for row in rows),
            "mismatched": sum(row.get("status") == "mismatched" for row in rows),
            "excluded": sum(row.get("status") == "excluded" for row in rows),
            "not_task_eligible": sum(row.get("status") == "bound_not_task_eligible" for row in rows),
            "other_statuses": sorted(statuses - {"eligible_private_local_retention", "missing", "mismatched", "excluded", "bound_not_task_eligible"}),
        },
    }


def _empty_preflight() -> GovernedRightsFactoryPreflight:
    return GovernedRightsFactoryPreflight(tasks=(), diagnostics=())


def _blocked_plan(
    *,
    execution_context: Mapping[str, str],
    reason: str,
    manifest: Mapping[str, Any] | None = None,
) -> RealCohortFactoryPlan:
    coverage = _coverage(manifest or {"rows": ()}, 0)
    cohort_plan = {
        "schema": REAL_COHORT_SCHEMA,
        "selected_manifest_sha256": SELECTED_MANIFEST_SHA256,
        "source_evidence_provenance_epoch": SOURCE_EVIDENCE_PROVENANCE_EPOCH,
        "bridge_execution_context": dict(sorted(execution_context.items())),
        "task_identities": [],
        "coverage": coverage,
        "blocked_reason": reason,
    }
    plan_hash = canonical_sha256(cohort_plan)
    cohort_id = deterministic_id("cohort:", {"plan_sha256": plan_hash})
    return RealCohortFactoryPlan(
        binding=None,
        preflight=_empty_preflight(),
        factory_plan=FactoryPlan.from_manifest([]),
        manifest=manifest,
        cohort_id=cohort_id,
        cohort_plan=cohort_plan,
        cohort_plan_sha256=plan_hash,
        blocked_reason=reason,
    )


def _references(manifest: Mapping[str, Any]) -> tuple[RightsPreflightReference, ...]:
    references: list[RightsPreflightReference] = []
    for row in manifest["rows"]:
        references.append(RightsPreflightReference(
            reference_id=f"g4-t3-binding:{int(row['ordinal']):02d}",
            rights_record_id=row["rights_record_id"],
            source_family=row["source_family"],
            source_definition_id=row["source_definition_id"],
            evidence_locator_ids=(row["evidence_locator_id"],),
            claim_family_id="g4-t3-source-binding-v1",
            task_profile="g4_t3_private_source_binding",
            task_profile_version="1",
            schema_version="1",
            difficulty="deterministic",
        ))
    return tuple(references)


def build_real_evidence_factory_plan(
    *,
    source_archive_root: str | Path,
    work_root: str | Path,
    execution_context: Mapping[str, str],
    selected_manifest_sha256: str = SELECTED_MANIFEST_SHA256,
    source_evidence_epoch: str = SOURCE_EVIDENCE_PROVENANCE_EPOCH,
    exclusions: Mapping[int, ExclusionEvidence] | None = None,
) -> RealCohortFactoryPlan:
    """Build the exact real cohort plan, or an empty fail-closed plan."""

    if source_evidence_epoch != SOURCE_EVIDENCE_PROVENANCE_EPOCH:
        return _blocked_plan(execution_context=execution_context, reason="source evidence epoch is not the retained immutable epoch")
    if selected_manifest_sha256 != SELECTED_MANIFEST_SHA256:
        return _blocked_plan(execution_context=execution_context, reason="selected manifest identity is outside the retained cohort")

    try:
        binding = build_selected_binding_manifest(
            source_archive_root=source_archive_root,
            work_root=work_root,
            execution_context=execution_context,
            selected_manifest_sha256=selected_manifest_sha256,
            as_of=AS_OF,
            exclusions=exclusions,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        return _blocked_plan(execution_context=execution_context, reason=f"real binding failed closed: {type(exc).__name__}")

    manifest = binding.manifest
    rows = manifest["rows"]
    if any(row.get("status") != "eligible_private_local_retention" for row in rows):
        return _blocked_plan(
            execution_context=execution_context,
            reason="one or more retained rows are not eligible for the real cohort plan",
            manifest=manifest,
        )

    catalog = SQLiteCatalog(Path(work_root).resolve() / "catalog.sqlite3").open(initialize=True)
    projection = RightsGovernanceProjection(catalog.path).open()
    rights_store = RightsGovernanceStore(Path(work_root).resolve() / "rights")
    artifacts = ContentAddressedArtifactStore(Path(work_root).resolve() / "representations", catalog=catalog)
    try:
        preflight = preflight_governed_rights(
            _references(manifest),
            store=rights_store,
            projection=projection,
            catalog=catalog,
            as_of=AS_OF,
            retained_bytes=artifacts.read,
        )
    finally:
        projection.close()
        catalog.close()

    if preflight.diagnostics or preflight.accepted_count != len(rows):
        return _blocked_plan(
            execution_context=execution_context,
            reason="clean rights preflight did not accept the complete real cohort",
            manifest=manifest,
        )

    factory_plan = preflight.factory_plan
    task_identities = [_task_identity(task) for task in factory_plan.logical_tasks]
    coverage = _coverage(manifest, len(task_identities))
    cohort_plan = {
        "schema": REAL_COHORT_SCHEMA,
        "selected_manifest_sha256": manifest["selected_manifest_sha256"],
        "source_evidence_provenance": manifest["source_evidence_provenance"],
        "bridge_execution_context": manifest["bridge_execution_context"],
        "task_identities": task_identities,
        "coverage": coverage,
    }
    plan_hash = canonical_sha256(cohort_plan)
    cohort_id = deterministic_id("cohort:", {"plan_sha256": plan_hash})
    return RealCohortFactoryPlan(
        binding=binding,
        preflight=preflight,
        factory_plan=factory_plan,
        manifest=manifest,
        cohort_id=cohort_id,
        cohort_plan=cohort_plan,
        cohort_plan_sha256=plan_hash,
    )


def execute_real_evidence_factory_plan(
    plan: RealCohortFactoryPlan,
    *,
    work_root: str | Path,
    provider: RehearsalFakeProvider | None = None,
    now: datetime = NOW,
) -> RealCohortExecution:
    """Seed and run deterministic real-evidence tasks through ReferenceFactory."""

    if plan.blocked_reason is not None:
        raise ValueError("blocked real-evidence plans cannot be executed")
    root = Path(work_root).resolve()
    catalog = SQLiteCatalog(root / "catalog.sqlite3").open(initialize=True)
    try:
        run_id = deterministic_id("run:", {"cohort_id": plan.cohort_id, "plan_sha256": plan.cohort_plan_sha256})
        catalog.register_cohort({
            "record_id": plan.cohort_id,
            "cohort_code": "G4-T3-REAL-PRIVATE",
            "definition_version": "1",
            "membership_hash": plan.cohort_plan_sha256,
            "budget_cap": {"amount": "0", "currency": "AUD"},
            "created_at": now,
        })
        catalog.register_run({
            "record_id": run_id,
            "cohort_id": plan.cohort_id,
            "run_kind": "g4_t3_real_evidence_provider_free_rehearsal",
            "status": "planned",
            "configuration_hash": plan.cohort_plan_sha256,
            "created_at": now,
        })
        fake = provider or RehearsalFakeProvider()
        runner = ReferenceFactory(
            catalog,
            plan.factory_plan,
            cohort_id=plan.cohort_id,
            run_id=run_id,
            provider=fake,
            delivery_mode="standard",
        )
        tasks = runner.seed(now)
        completed = runner.run(now)
        diagnostic = persisted_diagnostic(catalog, run_id)
        with catalog._connection() as conn:
            attempt_count = int(conn.execute(
                "SELECT COUNT(*) FROM task_attempts WHERE model_task_id IN (SELECT model_task_id FROM tasks WHERE run_id=?)",
                (run_id,),
            ).fetchone()[0])
            actual = conn.execute(
                "SELECT COALESCE(SUM(accounting_amount), '0') FROM cost_entries WHERE run_id=? AND entry_type='actual'",
                (run_id,),
            ).fetchone()[0]
            released = conn.execute(
                "SELECT COALESCE(SUM(accounting_amount), '0') FROM cost_entries WHERE run_id=? AND entry_type='reservation_release'",
                (run_id,),
            ).fetchone()[0]
        return RealCohortExecution(
            cohort_id=plan.cohort_id,
            run_id=run_id,
            completed_tasks=completed,
            task_count=len(tasks),
            attempt_count=attempt_count,
            fake_send_calls=int(getattr(fake, "send_calls", 0)),
            diagnostic_sha256=diagnostic.sha256,
            aud_actual=str(actual),
            aud_released=str(released),
        )
    finally:
        catalog.close()


__all__ = [
    "NOW", "REAL_COHORT_SCHEMA", "RealCohortExecution", "RealCohortFactoryPlan",
    "build_real_evidence_factory_plan", "execute_real_evidence_factory_plan",
]
