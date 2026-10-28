"""Synthetic, provider-free Gate 4 T2 governed cohort rehearsal helpers.

This module is deliberately a thin fixture-and-observation layer.  It creates
TEST-only subjects and durable records, then delegates rights validation,
planning, execution, accounting, and task identity to the committed Phase 5
machinery.  It does not acquire evidence, interpret prose, or create a second
rights or Factory authority.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from .contracts import (
    AcquisitionReceipt,
    ArtifactRef,
    PropositionAuthorityRole,
    ProducerRef,
    SchemaRef,
    ScopeRecord,
    SourceDefinition,
    SourceRecord,
    StructuredFieldLocator,
    SubjectRecord,
)
from .contracts.ids import deterministic_id
from .evidence_store import ContentAddressedArtifactStore
from .phase5_factory import RehearsalFakeProvider
from .phase5_governed_rights_preflight import (
    RightsPreflightReference,
    preflight_governed_rights,
)
from .phase5_run_diagnostics import DiagnosticProjection, project_run_diagnostics
from .runtime import SQLiteCatalog
from .runtime.rights_governance_projection import RightsGovernanceProjection
from .runtime.rights_governance_record import (
    RightsAxis,
    RightsGovernanceRecord,
    RightsGovernanceStore,
)


NOW = datetime(2026, 10, 29, 0, 0, 0, tzinfo=timezone.utc)
_PRODUCER = ProducerRef(kind="code", producer_id="g4-t2-test-fixture", version="1")
_SCHEMA = SchemaRef(
    schema_id="urn:charitygraph:builder:schema:g4-t2-test-fixture:1",
    schema_version="1",
)


def _stable_id(prefix: str, seed: str) -> str:
    return prefix + hashlib.sha256(seed.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TestMaterial:
    subject_id: str
    scope_id: str
    source_definition_id: str
    source_record_id: str
    source_artifact_id: str
    representation_artifact_id: str
    representation_bytes: bytes
    receipt_id: str
    evidence_locator_id: str
    rights_record: RightsGovernanceRecord
    request: RightsPreflightReference


@dataclass
class TestCohortFixture:
    catalog: SQLiteCatalog
    artifacts: ContentAddressedArtifactStore
    rights_store: RightsGovernanceStore
    projection: RightsGovernanceProjection
    materials: tuple[TestMaterial, ...]
    now: datetime = NOW

    def close(self) -> None:
        self.projection.close()
        self.catalog.close()


def build_test_fixture(tmp_path: Path, suffixes: tuple[str, ...] = ("one",)) -> TestCohortFixture:
    """Create only synthetic TEST material in caller-provided temporary state."""

    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    artifacts = ContentAddressedArtifactStore(tmp_path / "objects", catalog=catalog)
    rights_store = RightsGovernanceStore(tmp_path / "rights")
    materials: list[TestMaterial] = []

    for suffix in suffixes:
        subject_id = _stable_id("subject:", f"g4-t2:{suffix}")
        scope_id = _stable_id("scope:", f"g4-t2:{suffix}")
        source_definition_id = f"srcdef:g4-t2-{suffix}"
        source_url = f"https://example.invalid/g4-t2/{suffix}"
        source_bytes = f"TEST source bytes {suffix}".encode("utf-8")
        representation_bytes = f"TEST governed representation bytes {suffix}".encode("utf-8")

        catalog.register_subject(SubjectRecord(
            record_id=_stable_id("subjectrecord:", subject_id),
            created_at=NOW,
            producer=_PRODUCER,
            subject_id=subject_id,
            subject_kind="organisation",
            lifecycle_status="active",
            identity_authority_refs=(ArtifactRef(
                artifact_id=_stable_id("authority:", subject_id),
                content_hash="a" * 64,
                schema=_SCHEMA,
            ),),
            identity_policy_id="g4-t2-test-identity-v1",
            display_name=f"TEST fixture organisation {suffix}",
        ))
        catalog.register_scope(ScopeRecord(
            record_id=scope_id,
            created_at=NOW,
            producer=_PRODUCER,
            subject_id=subject_id,
            scope_kind="program",
            label=f"TEST fixture scope {suffix}",
        ))
        definition = SourceDefinition(
            record_id=source_definition_id,
            created_at=NOW,
            producer=_PRODUCER,
            publisher="TEST fixture publisher",
            source_class="official_website",
            authority_roles=(PropositionAuthorityRole(
                proposition="source", role="source-native"
            ),),
            acquisition_locator=source_url,
            temporal_semantics="retrieval snapshot",
            publication_eligibility="private review only",
            steward="builder",
            rights_policy_id="CC_BY_4_0_V1",
        )
        catalog.register_source_definition(definition)
        source_artifact = artifacts.put(source_bytes)
        representation = artifacts.put_derived(
            representation_bytes,
            input_artifact_ids=(source_artifact.artifact_id,),
        )
        receipt = AcquisitionReceipt(
            record_id=f"acq:g4-t2-{suffix}",
            created_at=NOW,
            producer=_PRODUCER,
            source_definition_id=source_definition_id,
            requested_locator=source_url,
            resolved_locator=source_url,
            retrieved_at=NOW,
            outcome="available",
            content_hash=source_artifact.content_hash,
            byte_size=source_artifact.byte_size,
            artifact_id=source_artifact.artifact_id,
        )
        catalog.record_acquisition_receipt(receipt)
        source_record = SourceRecord(
            record_id=deterministic_id("srcrec:", {
                "source_family": "official_website",
                "source_version": None,
                "source_locator": source_url,
                "payload_hash": source_artifact.content_hash,
            }),
            created_at=NOW,
            producer=_PRODUCER,
            about_subject_ids=(subject_id,),
            source_family="official_website",
            source_role="source-native",
            source_locator=source_url,
            observed_at=NOW,
            payload_ref=source_artifact.artifact_id,
            payload_hash=source_artifact.content_hash,
            rights_policy_id="CC_BY_4_0_V1",
        )
        catalog.register_source_record(source_record)
        locator = catalog.register_evidence_locator(StructuredFieldLocator(
            artifact_id=representation.artifact_id,
            field_path="g4_t2_test_fixture.field",
        ))
        record = RightsGovernanceRecord(
            decision_id=f"rights:g4-t2-{suffix}",
            source_artifact_id=source_artifact.artifact_id,
            source_record_id=source_record.record_id,
            subject_id=subject_id,
            source_origin_url=source_url,
            source_role="source-native",
            acquisition_lineage_ids=(receipt.record_id,),
            representation_artifact_id=representation.artifact_id,
            representation_sha256=representation.content_hash,
            rights_basis="explicit_open_license",
            rights_policy_id="CC_BY_4_0_V1",
            rights_policy_version="1.0.0",
            purpose="semantic_analysis",
            scope=scope_id,
            evidence_locator=source_url,
            evidence_sha256=source_artifact.content_hash,
            assessed_on=NOW.date(),
            local_retention=RightsAxis(
                status="authorized",
                policy_id="CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1",
                policy_version="1.0.0",
                decision_id=f"rights:g4-t2-{suffix}:retention",
            ),
            provider_transmission=RightsAxis(status="blocked"),
            public_redistribution=RightsAxis(status="blocked"),
            status="authorized",
            review_status="current",
            actor_kind="human",
            actor_id=f"actor:g4-t2-{suffix}",
            recorded_at=NOW,
            representation_class="structured_factual",
            factual_representation_only=True,
            lawful_access_confirmed=True,
            circumvention_used=False,
            one_source_native_entity_record=True,
            retention_lifecycle_status="active_until_review",
            retention_review_due_on=date(2027, 10, 29),
        )
        rights_store.put_record(record)
        materials.append(TestMaterial(
            subject_id=subject_id,
            scope_id=scope_id,
            source_definition_id=source_definition_id,
            source_record_id=source_record.record_id,
            source_artifact_id=source_artifact.artifact_id,
            representation_artifact_id=representation.artifact_id,
            representation_bytes=representation_bytes,
            receipt_id=receipt.record_id,
            evidence_locator_id=locator["evidence_locator_id"],
            rights_record=record,
            request=RightsPreflightReference(
                reference_id=f"governed-rights-ref:g4-t2-{suffix}",
                rights_record_id=record.content_hash,
                source_family="official_website",
                source_definition_id=source_definition_id,
                evidence_locator_ids=(locator["evidence_locator_id"],),
                claim_family_id="g4-t2-test-claim-family-v1",
                task_profile="g4_t2_test_governed_task",
                difficulty="lower_cost_constrained_semantic",
                physical_bundle_opportunity="g4-t2-test-bundle",
            ),
        ))

    projection = RightsGovernanceProjection(catalog.path).open()
    projection.rebuild_from_store(rights_store, as_of=NOW.date())
    return TestCohortFixture(catalog, artifacts, rights_store, projection, tuple(materials))


class CountingFakeProvider(RehearsalFakeProvider):
    """Existing fake receipt seam with observable send/reconciliation counts."""

    def __init__(self) -> None:
        self.send_calls = 0
        self.reconciliation_calls = 0
        self._inside_send = False

    def execute_package(self, package_id: str, *, delivery_mode: str):
        self.send_calls += 1
        self._inside_send = True
        try:
            return super().execute_package(package_id, delivery_mode=delivery_mode)
        finally:
            self._inside_send = False

    def receipt_for_package(self, package_id: str, *, delivery_mode: str):
        if not self._inside_send:
            self.reconciliation_calls += 1
        return super().receipt_for_package(package_id, delivery_mode=delivery_mode)


def register_test_run(catalog: SQLiteCatalog, *, suffix: str = "one", now: datetime = NOW) -> tuple[str, str]:
    cohort_id = _stable_id("cohort:", f"g4-t2:{suffix}")
    run_id = _stable_id("run:", f"g4-t2:{suffix}")
    catalog.register_cohort({
        "record_id": cohort_id,
        "cohort_code": "G4-T2-TEST",
        "definition_version": "1",
        "membership_hash": "b" * 64,
        "budget_cap": {"amount": "100", "currency": "AUD"},
        "created_at": now,
    })
    catalog.register_run({
        "record_id": run_id,
        "cohort_id": cohort_id,
        "run_kind": "g4_t2_provider_free_test_rehearsal",
        "status": "planned",
        "configuration_hash": "c" * 64,
        "created_at": now,
    })
    return cohort_id, run_id


def persisted_diagnostic(catalog: SQLiteCatalog, run_id: str) -> DiagnosticProjection:
    """Project only allowlisted committed SQLite identities and accounting."""

    with catalog._connection() as conn:
        run = dict(conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
        tasks = [dict(row) for row in conn.execute(
            "SELECT * FROM tasks WHERE run_id=? ORDER BY model_task_id", (run_id,)
        )]
        attempts = [dict(row) for row in conn.execute(
            "SELECT * FROM task_attempts WHERE model_task_id IN "
            "(SELECT model_task_id FROM tasks WHERE run_id=?) ORDER BY task_run_id", (run_id,)
        )]
        reservations = [dict(row) for row in conn.execute(
            "SELECT * FROM budget_reservations WHERE run_id=? ORDER BY reservation_id", (run_id,)
        )]
        costs = [dict(row) for row in conn.execute(
            "SELECT * FROM cost_entries WHERE run_id=? ORDER BY entry_key", (run_id,)
        )]
        receipts = [dict(row) for row in conn.execute(
            "SELECT pr.* FROM provider_receipts pr JOIN physical_attempts pa "
            "ON pa.physical_attempt_id=pr.physical_attempt_id WHERE pa.run_id=? "
            "ORDER BY provider_receipt_id", (run_id,)
        )]
        member_rows = [dict(row) for row in conn.execute(
            "SELECT pam.model_task_id, pam.physical_attempt_id FROM physical_attempt_members pam "
            "JOIN physical_attempts pa ON pa.physical_attempt_id=pam.physical_attempt_id "
            "WHERE pa.run_id=?", (run_id,)
        )]

    receipt_tasks = {
        member["model_task_id"]
        for member in member_rows
        if any(receipt["physical_attempt_id"] == member["physical_attempt_id"] for receipt in receipts)
    }
    results = [
        {
            "item_id": task["model_task_id"],
            "subject_id": task["subject_id"],
            "scope_id": task["scope_id"] or "scope:not-applicable",
            "status": "completed" if task["status"] == "succeeded" else task["status"],
            "provider_posts": int(task["model_task_id"] in receipt_tasks),
            "stop_campaign": False,
        }
        for task in tasks
    ]
    ledger = {
        "tasks": [{"task_id": row["model_task_id"], "status": row["status"]} for row in tasks],
        "attempts": [{"attempt_id": row["task_run_id"], "task_id": row["model_task_id"], "status": row["status"]} for row in attempts],
        "receipts": [{"receipt_id": row["provider_receipt_id"], "physical_attempt_id": row["physical_attempt_id"]} for row in receipts],
        "reservations": [{
            "reservation_id": row["reservation_id"],
            "reserved_aud": {"amount": row["reserved_amount"], "currency": row["accounting_currency"]},
            "status": row["status"],
        } for row in reservations],
        "cost_entries": [{
            "entry_key": row["entry_key"],
            "reservation_id": row["reservation_id"],
            "entry_type": row["entry_type"],
            "accounting_amount": row["accounting_amount"],
            "accounting_currency": row["accounting_currency"],
        } for row in costs],
    }
    return project_run_diagnostics(
        {
            "run_id": run_id,
            "provenance": {
                "run_record_ref": f"sqlite:{catalog.path}:run:{run_id}",
                "ledger_snapshot_ref": f"sqlite:{catalog.path}:ledger:{run_id}",
            },
            "results": results,
            "planned_item_count": len(tasks),
            "provider_posts": sum(item["provider_posts"] for item in results),
            "stop": {"campaign_stopped": False, "classification": "none"},
        },
        ledger,
    )


def table_counts(catalog: SQLiteCatalog) -> tuple[int, ...]:
    with catalog._connection() as conn:
        return tuple(
            int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in (
                "tasks", "task_attempts", "physical_attempts",
                "budget_reservations", "provider_receipts", "cost_entries",
            )
        )


__all__ = [
    "CountingFakeProvider", "NOW", "TestCohortFixture", "TestMaterial",
    "build_test_fixture", "persisted_diagnostic", "register_test_run",
    "table_counts",
]
