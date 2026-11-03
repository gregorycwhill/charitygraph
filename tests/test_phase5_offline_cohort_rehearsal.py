from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from charitygraph.contracts import (
    AcquisitionReceipt,
    ArtifactRef,
    ProducerRef,
    PropositionAuthorityRole,
    SchemaRef,
    ScopeRecord,
    SourceDefinition,
    SourceRecord,
    StructuredFieldLocator,
    SubjectRecord,
    deterministic_id,
)
from charitygraph.evidence_store import ContentAddressedArtifactStore
from charitygraph.phase5_offline_cohort_rehearsal import run_offline_cohort_rehearsal
from charitygraph.phase5_governed_rights_preflight import (
    RightsPreflightReference,
    preflight_governed_rights,
)
from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.rights_governance_projection import RightsGovernanceProjection
from charitygraph.runtime.rights_governance_record import (
    RightsAxis,
    RightsGovernanceRecord,
    RightsGovernanceStore,
)


NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
PRODUCER = ProducerRef(kind="code", producer_id="g4-t2-test-fixture", version="1")
SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:g4-t2-fixture:1", schema_version="1")


def _fixture_cohort(tmp_path):
    from charitygraph.phase5_governed_factory_integration import GovernedReference

    if "rights_decision_ids" in GovernedReference.model_fields:
        pytest.skip("clean rehearsal is isolated from the pre-existing dirty rights prototype")
    catalog = SQLiteCatalog(tmp_path / "authority.sqlite3").open(initialize=True)
    artifacts = ContentAddressedArtifactStore(tmp_path / "objects", catalog=catalog)
    store = RightsGovernanceStore(tmp_path / "private-rights")
    requests = []
    for index in range(5):
        token = f"{index + 1:x}" * 32
        subject_id = "subject:" + token
        scope_id = "scope:" + f"{index + 11:x}" * 32
        definition_id = f"srcdef:g4-t2-test-{index}"
        source_url = f"https://example.invalid/g4-t2-test/{index}"
        catalog.register_subject(SubjectRecord(
            record_id="subjectrecord:" + token,
            created_at=NOW,
            producer=PRODUCER,
            subject_id=subject_id,
            subject_kind="organisation",
            lifecycle_status="active",
            identity_authority_refs=(ArtifactRef(artifact_id=f"authority:g4-t2:{index}", content_hash="a" * 64, schema=SCHEMA),),
            identity_policy_id="fixture-identity-v1",
            display_name=f"TEST FIXTURE organisation {index}",
        ))
        catalog.register_scope(ScopeRecord(
            record_id=scope_id,
            created_at=NOW,
            producer=PRODUCER,
            subject_id=subject_id,
            scope_kind="program",
            label=f"TEST FIXTURE scope {index}",
        ))
        catalog.register_source_definition(SourceDefinition(
            record_id=definition_id,
            created_at=NOW,
            producer=PRODUCER,
            publisher="TEST FIXTURE publisher",
            source_class="official_website",
            authority_roles=(PropositionAuthorityRole(proposition="source", role="source-native"),),
            acquisition_locator=source_url,
            temporal_semantics="retrieval snapshot",
            publication_eligibility="private review only",
            steward="builder",
            rights_policy_id="CC_BY_4_0_V1",
        ))
        source_artifact = artifacts.put(f"TEST FIXTURE source bytes {index}".encode())
        representation = artifacts.put_derived(
            f"TEST FIXTURE representation bytes {index}".encode(),
            input_artifact_ids=(source_artifact.artifact_id,),
        )
        receipt = AcquisitionReceipt(
            record_id=f"acq:g4-t2-test-{index}",
            created_at=NOW,
            producer=PRODUCER,
            source_definition_id=definition_id,
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
            producer=PRODUCER,
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
            field_path="fixture.g4_t2_field",
        ))
        record = RightsGovernanceRecord(
            decision_id=f"rights:g4-t2-test-{index}",
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
            local_retention=RightsAxis(status="authorized", policy_id="CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1", policy_version="1.0.0", decision_id=f"rights:g4-t2-test:{index}:retention"),
            provider_transmission=RightsAxis(status="blocked"),
            public_redistribution=RightsAxis(status="blocked"),
            status="authorized",
            review_status="current",
            actor_kind="human",
            actor_id="actor:g4-t2-test",
            recorded_at=NOW,
            representation_class="structured_factual",
            factual_representation_only=True,
            lawful_access_confirmed=True,
            circumvention_used=False,
            one_source_native_entity_record=True,
            retention_lifecycle_status="active_until_review",
            retention_review_due_on=date(2027, 10, 28),
        )
        store.put_record(record)
        requests.append(RightsPreflightReference(
            reference_id=f"governed-rights-ref:g4-t2-test-{index}",
            rights_record_id=record.content_hash,
            source_family="official_website",
            source_definition_id=definition_id,
            evidence_locator_ids=(locator["evidence_locator_id"],),
            claim_family_id="fixture-claim-family-v1",
            task_profile="fixture-governed-rights-task",
            difficulty="lower_cost_constrained_semantic",
            physical_bundle_opportunity=f"fixture-g4-t2-bundle-{index}",
        ))
    projection = RightsGovernanceProjection(catalog.path).open()
    projection.rebuild_from_store(store, as_of=NOW.date())
    preflight = preflight_governed_rights(
        requests,
        store=store,
        projection=projection,
        catalog=catalog,
        as_of=NOW.date(),
        retained_bytes=lambda artifact_id: artifacts.read(artifact_id),
    )
    assert not preflight.diagnostics
    assert preflight.accepted_count == 5
    return catalog, preflight


def test_offline_cohort_rehearsal_is_durable_replayable_and_batch_plannable(tmp_path):
    authority_catalog, preflight = _fixture_cohort(tmp_path / "authority")
    tasks = preflight.factory_plan.runtime_tasks(cohort_id="cohort:" + "1" * 32)
    failed = {tasks[1]["logical_task_id"]}
    result = run_offline_cohort_rehearsal(
        preflight,
        database_path=authority_catalog.path,
        cohort_id="cohort:" + "1" * 32,
        run_id="run:" + "2" * 32,
        now=NOW,
        failed_reference_ids=failed,
        max_concurrency=2,
    )
    assert result.task_count == 5
    assert result.completed_count == 4
    assert result.failed_count == 1
    assert result.held_count == 0
    assert result.standard_request_items == 5
    assert result.batch_request_items == 5
    assert result.batch_jobs == 1
    assert result.configured_concurrency == 2
    assert result.observed_concurrency == 1
    assert result.new_provider_calls == 4
    assert result.restart_no_resend is True
    assert result.accounting_reconciliation == "RECONCILED"
    assert result.residual_active_reservations == 0

    replay = run_offline_cohort_rehearsal(
        preflight,
        database_path=authority_catalog.path,
        cohort_id="cohort:" + "1" * 32,
        run_id="run:" + "2" * 32,
        now=NOW,
    )
    assert replay.new_provider_calls == 0
    assert replay.diagnostic_sha256 == result.diagnostic_sha256
    authority_catalog.close()


def test_offline_cohort_rehearsal_holds_ambiguous_send_and_leaves_residual_guard(tmp_path):
    authority_catalog, preflight = _fixture_cohort(tmp_path / "authority")
    tasks = preflight.factory_plan.runtime_tasks(cohort_id="cohort:" + "3" * 32)
    result = run_offline_cohort_rehearsal(
        preflight,
        database_path=authority_catalog.path,
        cohort_id="cohort:" + "3" * 32,
        run_id="run:" + "4" * 32,
        now=NOW,
        ambiguous_reference_ids={tasks[0]["logical_task_id"]},
        max_concurrency=2,
    )
    assert result.completed_count == 4
    assert result.held_count == 1
    assert result.new_provider_calls == 5
    assert result.residual_active_reservations == 1
    authority_catalog.close()
